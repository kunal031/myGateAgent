"""Google sign-in: the authorisation URL, the code exchange, and the part
that actually matters -- verifying the ID token Google hands back.

This is written against Google's OpenID Connect discovery document rather
than from memory, because two of its details are easy to get wrong in ways
that are either insecure or quietly broken:

* `iss` has **two** legal values, `https://accounts.google.com` and the
  bare `accounts.google.com`. Checking only the first rejects valid tokens
  intermittently, which looks like a flaky login.
* The identity is `sub`, never `email`. Google states that an account's
  email can change and `sub` cannot, so an email key means a user who
  changes their address loses their history -- or inherits a stranger's if
  the address is reassigned.

No `authlib` or `google-auth` dependency: PyJWT is already pinned for our
own tokens and ships `PyJWKClient`, which fetches Google's rotating signing
keys and caches them. One less package in the supply chain.

The flow is the server-side authorisation-code flow with PKCE, not the
implicit flow: the code travels through the browser but is worthless
without the verifier, which never leaves this process.
"""

import base64
import hashlib
import logging
import secrets
import time
from dataclasses import dataclass

import httpx
import jwt
from jwt import PyJWKClient

from .config import settings
from .security import AuthError

logger = logging.getLogger(__name__)

AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
JWKS_URI = "https://www.googleapis.com/oauth2/v3/certs"

#: Both forms are legal per Google's documentation.
VALID_ISSUERS = ("https://accounts.google.com", "accounts.google.com")

#: openid gets us the ID token; the other two populate the profile. We ask
#: for nothing else -- no Gmail, no Drive -- so the consent screen stays
#: trivial and no sensitive-scope review is ever needed.
SCOPES = "openid email profile"

#: How long a sign-in attempt may sit half-finished. Long enough to pick an
#: account and type a password, short enough that a leaked state parameter
#: is useless by the time anyone finds it.
STATE_TTL_SECONDS = 600

#: Google's keys rotate. PyJWKClient caches them and refetches on a key it
#: has not seen, so this is created once rather than per request -- a fresh
#: client per sign-in would fetch the key set every time.
_jwk_client = PyJWKClient(JWKS_URI, cache_keys=True, lifespan=3600)


def _b64url(raw: bytes) -> str:
    """Base64url with the padding stripped, as every OAuth spec wants."""
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


@dataclass
class PendingLogin:
    """One in-flight sign-in attempt.

    `verifier` is the PKCE secret; it stays here and is sent only to
    Google's token endpoint, never through the browser. `next_url` is where
    the user was headed before being asked to sign in.
    """

    verifier: str
    created_at: float
    next_url: str = ""

    @property
    def expired(self) -> bool:
        return time.time() - self.created_at > STATE_TTL_SECONDS


class LoginStore:
    """In-memory store of pending sign-ins, keyed by the state parameter.

    Deliberately in-process, and the reason is worth stating because it is
    the same seam the rate limiter and OCR cache sit on: with two API
    containers, a sign-in begun on one and completed on the other finds no
    state and fails. The fix is Redis, which this application already runs
    for exactly that class of state. Until the API is actually replicated,
    a dict avoids a network round trip on every sign-in.

    Entries are swept on write rather than by a timer, so an abandoned
    attempt cannot accumulate -- there is no background task to forget to
    start, and the cost is bounded by how often anyone signs in.
    """

    def __init__(self) -> None:
        self._pending: dict[str, PendingLogin] = {}

    def issue(self, next_url: str = "") -> tuple[str, str, str]:
        """Create a state, verifier and challenge for a new attempt."""
        self._sweep()

        # 32 bytes from the OS CSPRNG. `secrets` rather than `random`:
        # a predictable state parameter is a CSRF hole, and a predictable
        # verifier defeats PKCE entirely.
        state = _b64url(secrets.token_bytes(32))
        verifier = _b64url(secrets.token_bytes(32))
        challenge = _b64url(hashlib.sha256(verifier.encode("ascii")).digest())

        self._pending[state] = PendingLogin(
            verifier=verifier, created_at=time.time(), next_url=next_url
        )
        return state, verifier, challenge

    def consume(self, state: str) -> PendingLogin:
        """Take an attempt, removing it.

        Single-use: popping rather than reading means a replayed callback
        finds nothing, so an intercepted authorisation code cannot be
        redeemed twice.
        """
        pending = self._pending.pop(state, None)
        if pending is None:
            raise AuthError("That sign-in attempt is unknown or already used")
        if pending.expired:
            raise AuthError("That sign-in attempt timed out; please try again")
        return pending

    def _sweep(self) -> None:
        for key in [k for k, v in self._pending.items() if v.expired]:
            self._pending.pop(key, None)


login_store = LoginStore()


@dataclass
class GoogleIdentity:
    """A verified Google user. Only built from a validated ID token."""

    sub: str
    email: str
    email_verified: bool
    name: str = ""
    picture: str = ""


def safe_next(next_url: str) -> str:
    """Reduce a post-sign-in destination to a same-origin path.

    Anything else is dropped. An absolute URL surviving to the redirect
    would make this an open redirect: an attacker could send someone
    through a genuine sign-in on this domain and land them on theirs, with
    the trust of having just authenticated. A leading `//` is rejected too,
    because browsers read `//evil.com` as protocol-relative and absolute.
    """
    if not next_url.startswith("/") or next_url.startswith("//"):
        return ""
    # Backslashes are normalised to forward slashes by some browsers, so
    # `/\evil.com` would also escape the origin.
    if "\\" in next_url:
        return ""
    return next_url[:512]


def authorization_url(next_url: str = "") -> str:
    """Build the URL that sends the browser to Google."""
    from urllib.parse import urlencode

    state, _verifier, challenge = login_store.issue(safe_next(next_url))

    return AUTH_ENDPOINT + "?" + urlencode({
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": SCOPES,
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        # Ask for an account each time rather than silently reusing the
        # one Google remembers, which on a shared machine signs the
        # previous person back in.
        "prompt": "select_account",
    })


def exchange_code(code: str, verifier: str) -> str:
    """Trade an authorisation code for an ID token.

    Returns the raw ID token; verification is separate and always runs.
    """
    try:
        response = httpx.post(
            TOKEN_ENDPOINT,
            data={
                "code": code,
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "redirect_uri": settings.GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code",
                "code_verifier": verifier,
            },
            timeout=15.0,
        )
    except httpx.HTTPError as exc:
        raise AuthError("Could not reach Google to complete sign-in") from exc

    if response.status_code != 200:
        # Google's error body names the cause -- redirect_uri_mismatch and
        # invalid_client are the two that happen during setup -- so it is
        # logged. It is not returned to the browser: it describes our
        # configuration, not anything the user did.
        logger.warning(
            "Google token exchange failed (%s): %s",
            response.status_code, response.text[:400],
        )
        raise AuthError("Google rejected this sign-in attempt")

    id_token = response.json().get("id_token")
    if not id_token:
        raise AuthError("Google's reply contained no identity token")
    return id_token


def verify_id_token(id_token: str) -> GoogleIdentity:
    """Validate an ID token and return the identity inside it.

    Everything in the token is attacker-supplied until the signature is
    checked against Google's published keys, so the signature check comes
    before any claim is read.
    """
    try:
        signing_key = _jwk_client.get_signing_key_from_jwt(id_token)
    except Exception as exc:  # network, or a kid Google no longer publishes
        raise AuthError("Could not verify Google's signature") from exc

    try:
        claims = jwt.decode(
            id_token,
            signing_key.key,
            algorithms=["RS256"],
            # `aud` must be our client ID. Without this check a token
            # minted for any other Google application would be accepted
            # here -- the single most important line in this file.
            audience=settings.GOOGLE_CLIENT_ID,
            # PyJWT takes one issuer; Google has two legal spellings, so
            # it is checked below instead of here.
            options={"require": ["sub", "aud", "exp", "iss"]},
            leeway=30,  # tolerate small clock skew between us and Google
        )
    except jwt.ExpiredSignatureError as exc:
        raise AuthError("That Google sign-in expired; please try again") from exc
    except jwt.InvalidAudienceError as exc:
        raise AuthError("That identity token was issued for another app") from exc
    except jwt.InvalidTokenError as exc:
        raise AuthError("That Google identity token is not valid") from exc

    if claims.get("iss") not in VALID_ISSUERS:
        raise AuthError("That identity token was not issued by Google")

    email = (claims.get("email") or "").lower().strip()
    verified = bool(claims.get("email_verified"))

    if not email:
        raise AuthError("Google did not supply an email address")

    # An unverified email cannot be trusted to identify anyone: Google
    # permits it on some account types, and accepting one would let a
    # signup with someone else's address adopt their existing account
    # through the email-linking path below.
    if not verified:
        raise AuthError(
            "That Google account's email is not verified, so it cannot be "
            "used to sign in"
        )

    return GoogleIdentity(
        sub=str(claims["sub"]),
        email=email,
        email_verified=verified,
        name=(claims.get("name") or "").strip(),
        picture=(claims.get("picture") or "").strip(),
    )
