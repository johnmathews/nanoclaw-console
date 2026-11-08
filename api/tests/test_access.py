"""The Access JWT verifier (docs/architecture.md §4.2), ported from the SRE agent's tests.

Keys are generated in-test; the team's certs endpoint is an httpx2 MockTransport.
"""

import json
import logging
import time

import httpx2
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from jwt.algorithms import ECAlgorithm

from nanoclaw_console.access import AccessDenied, AccessVerifier
from tests.jwt_helpers import AUD, CERTS_URL, EMAIL, TEAM, FakeCerts, Signer

pytestmark = pytest.mark.anyio

K1 = Signer("k1")
K2 = Signer("k2")


class Clock:
    def __init__(self, now: float = 1000.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


def make(
    certs: FakeCerts,
    clock: Clock | None = None,
    *,
    team: str = TEAM,
    aud: str = AUD,
    emails: frozenset[str] = frozenset({EMAIL}),
) -> AccessVerifier:
    return AccessVerifier(
        team_domain=team,
        audience=aud,
        allowed_emails=emails,
        transport=certs.transport(),
        clock=clock or Clock(),
    )


@pytest.fixture
def certs() -> FakeCerts:
    return FakeCerts(K1)


async def test_valid_token_returns_email(certs: FakeCerts) -> None:
    assert await make(certs).verify(K1.token()) == EMAIL
    assert certs.calls == [CERTS_URL]


async def test_wrong_audience_denied(certs: FakeCerts) -> None:
    with pytest.raises(AccessDenied):
        await make(certs).verify(K1.token(aud=["some-other-app"]))


async def test_aud_as_plain_string(certs: FakeCerts) -> None:
    verifier = make(certs)
    assert await verifier.verify(K1.token(aud=AUD)) == EMAIL
    with pytest.raises(AccessDenied):
        await verifier.verify(K1.token(aud="some-other-app"))


async def test_wrong_issuer_denied(certs: FakeCerts) -> None:
    with pytest.raises(AccessDenied):
        await make(certs).verify(K1.token(iss="https://evil.cloudflareaccess.com"))


async def test_expired_beyond_leeway_denied(certs: FakeCerts) -> None:
    now = int(time.time())
    with pytest.raises(AccessDenied):
        await make(certs).verify(K1.token(iat=now - 3600, nbf=now - 3600, exp=now - 120))


async def test_expired_within_leeway_accepted(certs: FakeCerts) -> None:
    now = int(time.time())
    token = K1.token(iat=now - 3600, nbf=now - 3600, exp=now - 30)
    assert await make(certs).verify(token) == EMAIL


async def test_iat_in_the_future_beyond_leeway_denied(certs: FakeCerts) -> None:
    now = int(time.time())
    verifier = make(certs)
    with pytest.raises(AccessDenied):
        await verifier.verify(K1.token(iat=now + 300, nbf=None, exp=now + 900))
    assert await verifier.verify(K1.token(iat=now + 30, nbf=None, exp=now + 900)) == EMAIL


@pytest.mark.parametrize("missing", ["exp", "iat", "iss", "aud", "email", "type"])
async def test_missing_required_claim_denied(certs: FakeCerts, missing: str) -> None:
    with pytest.raises(AccessDenied):
        await make(certs).verify(K1.token(**{missing: None}))


@pytest.mark.parametrize("token_type", ["org", "APP", "", "service"])
async def test_type_other_than_app_denied(certs: FakeCerts, token_type: str) -> None:
    """Access's team-domain `org` token is not an application token for this console."""
    with pytest.raises(AccessDenied, match="type"):
        await make(certs).verify(K1.token(type=token_type))


async def test_email_not_allowlisted_denied(certs: FakeCerts) -> None:
    with pytest.raises(AccessDenied, match="allowlist"):
        await make(certs).verify(K1.token(email="someone-else@example.com"))


async def test_email_compared_case_insensitively(certs: FakeCerts) -> None:
    verifier = make(certs, emails=frozenset({"admin@example.com"}))
    assert await verifier.verify(K1.token(email="Admin@Example.COM")) == "admin@example.com"


async def test_service_token_without_email_denied(certs: FakeCerts) -> None:
    token = K1.token(email=None, common_name="abc.access")
    with pytest.raises(AccessDenied):
        await make(certs).verify(token)


@pytest.mark.parametrize("token", [None, ""])
async def test_missing_token_denied_without_fetching_keys(
    certs: FakeCerts, token: str | None
) -> None:
    with pytest.raises(AccessDenied):
        await make(certs).verify(token)
    assert certs.calls == []


async def test_too_long_token_denied_without_fetching_keys(certs: FakeCerts) -> None:
    with pytest.raises(AccessDenied):
        await make(certs).verify("a" * (16 * 1024 + 1))
    assert certs.calls == []


async def test_alg_none_denied_without_fetching_keys(certs: FakeCerts) -> None:
    token = jwt.encode(K1.claims(), key=None, algorithm="none", headers={"kid": "k1"})  # type: ignore[arg-type]
    with pytest.raises(AccessDenied):
        await make(certs).verify(token)
    assert certs.calls == []


async def test_hs256_denied_even_with_public_key_material_as_secret(certs: FakeCerts) -> None:
    secret = K1.jwk()["n"]  # anything a forger could know about the public key
    token = jwt.encode(K1.claims(), key=secret, algorithm="HS256", headers={"kid": "k1"})
    with pytest.raises(AccessDenied):
        await make(certs).verify(token)


async def test_bad_signature_denied(certs: FakeCerts) -> None:
    forged = jwt.encode(K1.claims(), K2.key, algorithm="RS256", headers={"kid": "k1"})
    with pytest.raises(AccessDenied):
        await make(certs).verify(forged)


async def test_garbage_token_denied(certs: FakeCerts) -> None:
    with pytest.raises(AccessDenied):
        await make(certs).verify("not.a.jwt")


async def test_token_without_kid_denied_without_fetching_keys(certs: FakeCerts) -> None:
    token = jwt.encode(K1.claims(), K1.key, algorithm="RS256")
    with pytest.raises(AccessDenied):
        await make(certs).verify(token)
    assert certs.calls == []


async def test_keys_are_cached(certs: FakeCerts) -> None:
    verifier = make(certs)
    await verifier.verify(K1.token())
    await verifier.verify(K1.token())
    assert len(certs.calls) == 1


async def test_cache_expires_after_an_hour(certs: FakeCerts) -> None:
    clock = Clock(1000.0)
    verifier = make(certs, clock)
    await verifier.verify(K1.token())
    clock.now = 1000.0 + 3599
    await verifier.verify(K1.token())
    assert len(certs.calls) == 1
    clock.now = 1000.0 + 3601
    await verifier.verify(K1.token())
    assert len(certs.calls) == 2


async def test_unknown_kid_refetches_once_and_succeeds(certs: FakeCerts) -> None:
    clock = Clock(1000.0)
    verifier = make(certs, clock)
    assert await verifier.verify(K1.token()) == EMAIL
    certs.serve(K1, K2)  # Cloudflare rotated in a new key
    clock.now = 1061.0
    assert await verifier.verify(K2.token()) == EMAIL
    assert len(certs.calls) == 2


async def test_unknown_kid_after_refetch_denied_with_a_single_refetch(certs: FakeCerts) -> None:
    clock = Clock(1000.0)
    verifier = make(certs, clock)
    await verifier.verify(K1.token())
    clock.now = 1061.0
    with pytest.raises(AccessDenied, match="unknown key id"):
        await verifier.verify(K2.token())
    assert len(certs.calls) == 2


async def test_forged_kids_refetch_at_most_once_per_minute(certs: FakeCerts) -> None:
    clock = Clock(1000.0)
    verifier = make(certs, clock)
    forged = [Signer(f"forged-{i}").token() for i in range(3)]
    await verifier.verify(K1.token())  # the TTL fetch counts as the last fetch
    for t in (1001.0, 1030.0, 1059.0):
        clock.now = t
        for token in forged:
            with pytest.raises(AccessDenied):
                await verifier.verify(token)
    assert len(certs.calls) == 1
    clock.now = 1060.0
    for token in forged:
        with pytest.raises(AccessDenied):
            await verifier.verify(token)
    assert len(certs.calls) == 2  # one refetch, then the floor applies again


async def test_first_request_with_unknown_kid_fetches_once(certs: FakeCerts) -> None:
    with pytest.raises(AccessDenied):
        await make(certs).verify(K2.token())
    assert len(certs.calls) == 1


async def test_jwks_mixing_key_types_uses_only_the_rsa_key() -> None:
    ec_jwk = json.loads(ECAlgorithm.to_jwk(ec.generate_private_key(ec.SECP256R1()).public_key()))
    ec_jwk.update(kid="ec1", alg="ES256")
    oct_jwk = {"kty": "oct", "k": "c2VjcmV0", "kid": "oct1", "alg": "HS256"}
    certs = FakeCerts()
    body = {"keys": [ec_jwk, oct_jwk, K1.jwk()]}
    certs.default = lambda: httpx2.Response(200, json=body)
    verifier = make(certs)
    assert await verifier.verify(K1.token()) == EMAIL
    hs = jwt.encode(K1.claims(), "s" * 40, algorithm="HS256", headers={"kid": "oct1"})
    with pytest.raises(AccessDenied):
        await verifier.verify(hs)
    es = jwt.encode(
        K1.claims(),
        ec.generate_private_key(ec.SECP256R1()),
        algorithm="ES256",
        headers={"kid": "ec1"},
    )
    with pytest.raises(AccessDenied):
        await verifier.verify(es)


async def test_jwks_http_error_denies() -> None:
    certs = FakeCerts()
    certs.default = lambda: httpx2.Response(500)
    with pytest.raises(AccessDenied, match="HTTP 500"):
        await make(certs).verify(K1.token())


async def test_jwks_redirect_not_followed() -> None:
    certs = FakeCerts()
    certs.default = lambda: httpx2.Response(302, headers={"Location": "https://example.com/certs"})
    with pytest.raises(AccessDenied):
        await make(certs).verify(K1.token())
    assert certs.calls == [CERTS_URL]


async def test_jwks_network_error_denies() -> None:
    certs = FakeCerts(K1)
    certs.error = httpx2.ConnectError("boom")
    with pytest.raises(AccessDenied, match="ConnectError"):
        await make(certs).verify(K1.token())


async def test_jwks_too_large_denies() -> None:
    certs = FakeCerts()
    big = b'{"keys": [], "pad": "' + b"x" * (256 * 1024) + b'"}'
    certs.default = lambda: httpx2.Response(200, content=big)
    with pytest.raises(AccessDenied, match="ResponseTooLarge"):
        await make(certs).verify(K1.token())


async def test_jwks_declared_too_large_denies() -> None:
    certs = FakeCerts()
    certs.default = lambda: httpx2.Response(
        200, content=b"{}", headers={"Content-Length": str(10 * 1024 * 1024)}
    )
    with pytest.raises(AccessDenied):
        await make(certs).verify(K1.token())


@pytest.mark.parametrize(
    "body",
    [
        b'{"keys": []}',
        b'{"nope": 1}',
        b"[1, 2]",
        b"not json",
        b'{"keys": [{"kty": "oct", "k": "c2VjcmV0", "kid": "k1"}]}',
    ],
)
async def test_jwks_without_usable_rsa_keys_denies(body: bytes) -> None:
    certs = FakeCerts()
    certs.default = lambda: httpx2.Response(200, content=body)
    with pytest.raises(AccessDenied):
        await make(certs).verify(K1.token())


@pytest.mark.parametrize(
    "team",
    [
        "evil.example.com",
        "https://team.example.cloudflareaccess.com",
        "team.example.cloudflareaccess.com/path",
        "team.example.cloudflareaccess.com:8443",
        "cloudflareaccess.com",
        "user@team.cloudflareaccess.com",
        "team.cloudflareaccess.com.evil.example",
        "a" * 250 + ".cloudflareaccess.com",
    ],
)
async def test_bad_team_domain_denies_every_request_and_logs_once(
    certs: FakeCerts, team: str, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.ERROR, logger="nanoclaw_console.access")
    verifier = make(certs, team=team)
    for _ in range(2):
        with pytest.raises(AccessDenied):
            await verifier.verify(K1.token())
    assert certs.calls == []
    assert len([r for r in caplog.records if r.levelno == logging.ERROR]) == 1


@pytest.mark.parametrize("field", ["team", "aud", "emails"])
async def test_empty_config_denies_without_fetching_keys(
    certs: FakeCerts, field: str, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.ERROR, logger="nanoclaw_console.access")
    kwargs: dict[str, object] = {"team": TEAM, "aud": AUD, "emails": frozenset({EMAIL})}
    kwargs[field] = frozenset() if field == "emails" else ""
    verifier = make(certs, **kwargs)  # type: ignore[arg-type]
    for _ in range(3):
        with pytest.raises(AccessDenied):
            await verifier.verify(K1.token())
    assert certs.calls == []
    assert len([r for r in caplog.records if r.levelno == logging.ERROR]) == 1


async def test_token_never_logged(certs: FakeCerts, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)
    token = K1.token(aud=["wrong"])
    with pytest.raises(AccessDenied):
        await make(certs).verify(token)
    assert caplog.records, "a rejection must be logged"
    payload = token.split(".")[1]
    for record in caplog.records:
        assert token not in record.getMessage()
        assert payload not in record.getMessage()
        assert EMAIL not in record.getMessage()
