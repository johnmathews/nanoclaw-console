"""Verify the Cloudflare Access JWT (`Cf-Access-Jwt-Assertion`) on every request (§4.2).

Ported from homelab-sre/sre-agent/src/upgrades/access.py, plus the `type == "app"` check and the
console's own email allowlist. The console does not trust that Cloudflare sits in front of it:
every request but `/healthz` must carry a JWT signed (RS256) by one of the team's Access keys, for
this application's audience, issued by the team domain, of type `app`, for an allowlisted email.
Anything else is refused. Log lines and exception messages name the reason only, never the token,
its claims or the email.
"""

import asyncio
import json
import logging
import re
import time
from collections.abc import Callable
from typing import Any

import httpx2
import jwt
from starlette.types import ASGIApp, Receive, Scope, Send

logger = logging.getLogger(__name__)

ALGORITHM = "RS256"
JWKS_TTL_SECONDS = 3600.0
# Any fetch (expiry or an unknown kid) happens at most this often, counted from the last attempt.
JWKS_MIN_REFETCH_SECONDS = 60.0
# A failed refresh keeps the last good keys this long after they were fetched (B40).
JWKS_STALE_GRACE_SECONDS = 24 * 3600.0
JWKS_TIMEOUT_SECONDS = 10.0
JWKS_MAX_BYTES = 256 * 1024
LEEWAY_SECONDS = 60
MAX_TOKEN_CHARS = 16 * 1024
MAX_EMAIL_CHARS = 320
HEADER = "cf-access-jwt-assertion"
OPEN_PATHS = frozenset({"/healthz"})
# A bare hostname (lowercase labels, no scheme, port, path or userinfo) under cloudflareaccess.com.
_TEAM_DOMAIN_RE = re.compile(r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+cloudflareaccess\.com")


class AccessDenied(Exception):
    """The request carries no acceptable Access JWT. The message is a reason, never token text."""


class _TooLarge(Exception):
    pass


class AccessVerifier:
    """Checks one token at a time; holds the team's keys for an hour."""

    def __init__(
        self,
        *,
        team_domain: str,
        audience: str,
        allowed_emails: frozenset[str],
        transport: httpx2.AsyncBaseTransport | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._team = team_domain
        self._audience = audience
        self._emails = frozenset(e.lower() for e in allowed_emails)
        self._transport = transport
        self._clock = clock
        self._keys: dict[str, jwt.PyJWK] = {}
        self._fetched_at: float | None = None
        self._last_attempt = float("-inf")
        self._fetch_lock = asyncio.Lock()
        self._fetches = 0  # completed fetch attempts, so a waiter can tell one finished
        self._logged_config_errors: set[str] = set()

    async def verify(self, token: str | None) -> str:
        """Return the verified email (lower case), or raise `AccessDenied`."""
        try:
            return await self._verify(token)
        except AccessDenied as exc:
            logger.warning("Access JWT refused: %s", exc)
            raise

    def _config_error(self, reason: str) -> AccessDenied:
        """A misconfiguration refuses every request; logged at error level once per reason."""
        if reason not in self._logged_config_errors:
            self._logged_config_errors.add(reason)
            logger.error("Access check misconfigured (%s); every request is refused", reason)
        return AccessDenied(reason)

    def _check_config(self) -> None:
        if not self._team:
            raise self._config_error("ACCESS_TEAM_DOMAIN is empty")
        if len(self._team) > 253 or not _TEAM_DOMAIN_RE.fullmatch(self._team):
            raise self._config_error(
                "ACCESS_TEAM_DOMAIN is not a bare *.cloudflareaccess.com hostname"
            )
        if not self._audience:
            raise self._config_error("ACCESS_AUD is empty")
        if not self._emails:
            raise self._config_error("ALLOWED_EMAILS is empty")

    async def _verify(self, token: str | None) -> str:
        self._check_config()  # first, so a misconfiguration is logged on the first request
        if not token:
            raise AccessDenied("missing Cf-Access-Jwt-Assertion header")
        if len(token) > MAX_TOKEN_CHARS:
            raise AccessDenied("token too long")
        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError as exc:
            raise AccessDenied(f"unreadable token header ({type(exc).__name__})") from None
        if header.get("alg") != ALGORITHM:
            raise AccessDenied("token algorithm is not RS256")
        kid = header.get("kid")
        if not isinstance(kid, str) or not kid:
            raise AccessDenied("token has no key id")
        key = await self._key_for(kid)
        try:
            claims: dict[str, Any] = jwt.decode(
                token,
                key=key.key,
                algorithms=[ALGORITHM],
                audience=self._audience,
                issuer=f"https://{self._team}",
                leeway=LEEWAY_SECONDS,
                options={"require": ["exp", "iat", "iss", "aud"]},
            )
        except jwt.PyJWTError as exc:
            raise AccessDenied(f"token rejected ({type(exc).__name__})") from None
        if claims.get("type") != "app":
            raise AccessDenied("token type is not app")
        email = claims.get("email")
        if not isinstance(email, str) or not email or len(email) > MAX_EMAIL_CHARS:
            raise AccessDenied("token has no usable email claim")
        email = email.lower()
        if email not in self._emails:
            raise AccessDenied("email not on the allowlist")
        return email

    async def _key_for(self, kid: str) -> jwt.PyJWK:
        """The key for `kid`: from the 1 h cache, else a fetch. An expired cache or an unknown
        `kid` (key rotation) fetches at most once per JWKS_MIN_REFETCH_SECONDS since the last
        attempt, and one fetch at a time, so neither forged kids nor a Cloudflare blip make every
        request call out."""
        expired = self._fetched_at is None or self._clock() - self._fetched_at >= JWKS_TTL_SECONDS
        if expired and self._may_fetch():
            await self._refresh()
        if kid not in self._keys and self._may_fetch():
            await self._refresh()
        if kid not in self._keys:
            raise AccessDenied("unknown key id")
        return self._keys[kid]

    def _may_fetch(self) -> bool:
        """A fetch is due by the throttle, or one is in flight (wait for its keys)."""
        in_flight = self._fetch_lock.locked()
        return in_flight or self._clock() - self._last_attempt >= JWKS_MIN_REFETCH_SECONDS

    async def _refresh(self) -> None:
        """Fetch the keys. A failure keeps the last good keys while they are under
        JWKS_STALE_GRACE_SECONDS old; past that, or with none, the keys go and it raises."""
        seen = self._fetches
        async with self._fetch_lock:
            if self._fetches != seen:
                return  # another request fetched while this one waited: use its keys
            self._last_attempt = self._clock()
            try:
                keys = await self._fetch_keys()
            except AccessDenied as exc:
                self._fetches += 1
                age = None if self._fetched_at is None else self._clock() - self._fetched_at
                if self._keys and age is not None and age < JWKS_STALE_GRACE_SECONDS:
                    logger.warning("%s; keeping the keys fetched %d s ago", exc, age)
                    return
                self._keys = {}
                raise
            self._fetches += 1
            self._keys = keys
            self._fetched_at = self._clock()

    async def _fetch_keys(self) -> dict[str, jwt.PyJWK]:
        """The team's signing keys; only RSA keys usable with RS256 and carrying a `kid`."""
        url = f"https://{self._team}/cdn-cgi/access/certs"
        try:
            async with httpx2.AsyncClient(
                transport=self._transport, timeout=JWKS_TIMEOUT_SECONDS, follow_redirects=False
            ) as client:
                status, body = await _bounded_get(client, url, JWKS_MAX_BYTES)
        except (httpx2.HTTPError, httpx2.InvalidURL, _TooLarge) as exc:
            name = "ResponseTooLarge" if isinstance(exc, _TooLarge) else type(exc).__name__
            raise AccessDenied(f"JWKS fetch failed ({name})") from None
        if not 200 <= status < 300:
            raise AccessDenied(f"JWKS fetch returned HTTP {status}")
        try:
            data: Any = json.loads(body)
            if not isinstance(data, dict):
                raise AccessDenied("JWKS is not a JSON object")
            keyset = jwt.PyJWKSet.from_dict(data)
        except (ValueError, jwt.PyJWTError) as exc:
            raise AccessDenied(f"JWKS unreadable ({type(exc).__name__})") from None
        keys = {
            k.key_id: k
            for k in keyset.keys
            if k.key_id and k.key_type == "RSA" and k.algorithm_name == ALGORITHM
        }
        if not keys:
            raise AccessDenied("JWKS has no RS256 keys")
        return keys


async def _bounded_get(client: httpx2.AsyncClient, url: str, max_bytes: int) -> tuple[int, bytes]:
    """GET `url`, reading at most `max_bytes` of the body (checked before and while reading)."""
    async with client.stream("GET", url) as response:
        declared = response.headers.get("content-length")
        if declared is not None and declared.isdigit() and int(declared) > max_bytes:
            raise _TooLarge
        chunks: list[bytes] = []
        total = 0
        async for chunk in response.aiter_bytes():
            total += len(chunk)
            if total > max_bytes:
                raise _TooLarge
            chunks.append(chunk)
        return response.status_code, b"".join(chunks)


class AccessMiddleware:
    """Refuses every HTTP request without an acceptable JWT, except the open paths.

    A refusal is a bare 403 (no body, `Cache-Control: no-store`), whatever the reason, so it says
    nothing about the console or why. The verified email goes on `request.state.access_email`.
    """

    def __init__(self, app: ASGIApp, verifier: AccessVerifier) -> None:
        self.app = app
        self.verifier = verifier

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "lifespan":
            await self.app(scope, receive, send)
            return
        if scope["type"] == "http" and scope["path"] in OPEN_PATHS:
            await self.app(scope, receive, send)
            return
        token = _header(scope, HEADER)
        try:
            email = await self.verifier.verify(token)
        except AccessDenied:
            await _refuse(scope, send)
            return
        except Exception:  # a bug in the check must not open the door
            logger.exception("Access check failed unexpectedly; request refused")
            await _refuse(scope, send)
            return
        scope.setdefault("state", {})["access_email"] = email
        await self.app(scope, receive, send)


def _header(scope: Scope, name: str) -> str | None:
    wanted = name.encode("latin-1")
    for key, value in scope.get("headers", []):
        if key.lower() == wanted:
            return str(value.decode("latin-1"))
    return None


async def _refuse(scope: Scope, send: Send) -> None:
    if scope["type"] == "websocket":
        await send({"type": "websocket.close", "code": 1008})
        return
    await send(
        {
            "type": "http.response.start",
            "status": 403,
            "headers": [(b"content-length", b"0"), (b"cache-control", b"no-store")],
        }
    )
    await send({"type": "http.response.body", "body": b""})
