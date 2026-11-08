"""RSA signers and a JWKS document for the Access JWT tests (keys generated in-test).

Ported from homelab-sre/sre-agent/tests/upgrades_access_helpers.py, with the `type` claim that
Cloudflare Access puts on application tokens.
"""

import json
import time
from collections.abc import Callable
from functools import cache
from typing import Any

import httpx2
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm

TEAM = "team.example.cloudflareaccess.com"
AUD = "0123456789abcdef" * 4
ISSUER = f"https://{TEAM}"
CERTS_URL = f"https://{TEAM}/cdn-cgi/access/certs"
EMAIL = "admin@example.com"


@cache
def _private_key(kid: str) -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


class Signer:
    """Signs Access-shaped JWTs with a per-`kid` RSA key (cached across tests)."""

    def __init__(self, kid: str) -> None:
        self.kid = kid
        self.key = _private_key(kid)

    def jwk(self) -> dict[str, Any]:
        data: dict[str, Any] = json.loads(RSAAlgorithm.to_jwk(self.key.public_key()))
        data.update(kid=self.kid, alg="RS256", use="sig")
        return data

    def claims(self, **overrides: Any) -> dict[str, Any]:
        now = int(time.time())
        claims: dict[str, Any] = {
            "aud": [AUD],
            "iss": ISSUER,
            "email": EMAIL,
            "sub": "user-1",
            "type": "app",
            "iat": now,
            "nbf": now,
            "exp": now + 600,
        }
        claims.update(overrides)
        return {k: v for k, v in claims.items() if v is not None}

    def token(self, **overrides: Any) -> str:
        return jwt.encode(
            self.claims(**overrides), self.key, algorithm="RS256", headers={"kid": self.kid}
        )


def jwks(*signers: Signer) -> dict[str, Any]:
    return {"keys": [s.jwk() for s in signers]}


class FakeCerts:
    """The team's certs endpoint as an httpx2 transport: counts calls, serves a scripted answer."""

    def __init__(self, *signers: Signer) -> None:
        # Scripted answers, used once each in order, then the default (fresh objects each call).
        self.responses: list[Callable[[], httpx2.Response]] = []
        self.default: Callable[[], httpx2.Response] = self._keys(*signers)
        self.calls: list[str] = []
        self.error: Exception | None = None

    @staticmethod
    def _keys(*signers: Signer) -> Callable[[], httpx2.Response]:
        body = jwks(*signers)
        return lambda: httpx2.Response(200, json=body)

    def serve(self, *signers: Signer) -> None:
        self.default = self._keys(*signers)

    def then_serve(self, *signers: Signer) -> None:
        self.responses.append(self._keys(*signers))

    def handler(self, request: httpx2.Request) -> httpx2.Response:
        self.calls.append(str(request.url))
        if self.error is not None:
            raise self.error
        if self.responses:
            return self.responses.pop(0)()
        return self.default()

    def transport(self) -> httpx2.MockTransport:
        return httpx2.MockTransport(self.handler)
