"""Register, sign in, refresh, sign out."""

import logging
from datetime import datetime
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from ..core.auth import current_user
from ..core.config import settings
from ..core.database import get_db
from ..core.google_oauth import (
    GoogleIdentity, authorization_url, exchange_code, login_store,
    verify_id_token,
)
from ..core.security import (
    ACCESS_TOKEN_MINUTES, AuthError, MIN_PASSWORD_CHARS, create_access_token,
    create_refresh_token, decode_token, hash_password, verify_password,
)
from ..models.users import User, UserRole
from ..services import auth_sessions

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["Auth"])


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=MIN_PASSWORD_CHARS)
    display_name: str = ""


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


def _tokens(db: Session, user: User, request: Request | None = None) -> dict:
    """Start a session and return its token pair.

    Goes through auth_sessions rather than minting directly, so every
    refresh token issued anywhere is recorded and can be rotated. A token
    handed out without a row would silently bypass reuse detection.
    """
    agent = request.headers.get("user-agent") if request is not None else None
    issued = auth_sessions.issue(db, user, user_agent=agent)
    return {**issued, "expires_in": ACCESS_TOKEN_MINUTES * 60}


def _public(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name or "",
        "role": user.role,
        "avatar_url": user.avatar_url or None,
        # Lets the account screen offer "set a password" to a Google-only
        # account rather than "change password", which it has none to change.
        "has_password": user.has_password,
    }


@router.post("/register", status_code=201)
def register(payload: RegisterRequest, request: Request,
             db: Session = Depends(get_db)):
    """Create an account.

    Password registration is closed once an account exists. New accounts
    come in through Google, which hands over an email Google has already
    verified -- so there is no OTP to send, store, expire or leak, and no
    route by which someone can claim an address they do not own.

    The first account is still allowed through, because a fresh deployment
    with Google unconfigured would otherwise have no way in at all. That
    account becomes the admin.

    Existing accounts keep signing in with their password; only creating
    new ones this way is closed.
    """
    if not settings.auth_configured:
        raise HTTPException(503, "Authentication is not configured on this server")

    # Checked before the email is even read, so the reply cannot differ
    # based on whether that address happens to exist.
    bootstrap = db.query(User.id).first() is None
    if not bootstrap:
        raise HTTPException(
            403,
            "New accounts are created with Google sign-in, which verifies "
            "your email address. Use the Continue with Google button.",
        )

    email = payload.email.lower().strip()
    if db.query(User.id).filter(User.email == email).first():
        raise HTTPException(409, "An account with that email already exists")

    try:
        password_hash = hash_password(payload.password)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    user = User(
        email=email,
        display_name=payload.display_name.strip()[:120],
        password_hash=password_hash,
        # Only reachable when this is the first account, so always admin.
        role=UserRole.ADMIN,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    logger.info("Registered %s as %s", email, user.role)
    return {"user": _public(user), **_tokens(db, user, request)}


@router.post("/login")
def login(payload: LoginRequest, request: Request,
          db: Session = Depends(get_db)):
    """Exchange an email and password for tokens."""
    if not settings.auth_configured:
        raise HTTPException(503, "Authentication is not configured on this server")

    user = db.query(User).filter(User.email == payload.email.lower().strip()).first()

    # The password is verified even when no account matched, so the reply
    # takes the same time either way and does not reveal which emails are
    # registered.
    # A Google-only account has no hash at all, so the placeholder stands
    # in for it too -- otherwise verify_password receives None and raises,
    # turning a wrong-credentials case into a 500 that also reveals the
    # account exists and uses Google.
    placeholder = "$2b$12$" + "." * 53
    ok = verify_password(
        payload.password,
        user.password_hash if user and user.password_hash else placeholder,
    )

    if user is None or not user.password_hash or not ok or not user.is_active:
        raise HTTPException(401, "That email and password do not match")

    user.last_login_at = datetime.utcnow()
    db.commit()
    return {"user": _public(user), **_tokens(db, user, request)}


@router.post("/refresh")
def refresh(payload: RefreshRequest, request: Request,
            db: Session = Depends(get_db)):
    """Trade a refresh token for a new access token, and rotate it.

    Three checks, cheapest first: the signature, then the account's
    token_version (which is what makes "sign out everywhere" work without
    a blacklist), then the token's own row.

    The response carries a *new* refresh token and the presented one stops
    working. A client that replays a retired token is telling us two
    parties hold it, so that whole device family is revoked -- see
    services/auth_sessions for why that is the useful signal.
    """
    try:
        claims = decode_token(payload.refresh_token, expect="refresh")
    except AuthError as exc:
        raise HTTPException(401, str(exc)) from exc

    user = db.query(User).filter(User.id == int(claims["sub"])).first()
    if user is None or not user.is_active:
        raise HTTPException(401, "That session is no longer valid")
    if claims.get("ver") != user.token_version:
        raise HTTPException(401, "That session was signed out")

    try:
        rotated = auth_sessions.rotate(
            db, user, payload.refresh_token,
            user_agent=request.headers.get("user-agent"),
        )
    except auth_sessions.ReuseDetected as exc:
        # Deliberately the same 401 a expired token gets: telling a
        # caller "you replayed a token" confirms it was once valid.
        raise HTTPException(401, str(exc)) from exc

    return {
        "user": _public(user),
        **rotated,
        "expires_in": ACCESS_TOKEN_MINUTES * 60,
    }


@router.post("/logout", status_code=204)
def logout(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Sign out of every device.

    Both halves matter. Bumping token_version invalidates every refresh
    token at once without a blacklist to sweep; revoking the session rows
    means a later replay of one is reported as a dead session rather than
    being mistaken for a theft and logged as one.

    Access tokens already issued stay valid until they expire, which is
    the trade-off that keeps authorisation free of a database read.
    """
    user.token_version = (user.token_version or 0) + 1
    db.commit()
    auth_sessions.revoke_all(db, user.id, reason="signed_out")


@router.get("/me")
def me(user: User = Depends(current_user)):
    return _public(user)


# ---------------------------------------------------------------- Google

@router.get("/google/config")
def google_config():
    """Whether to show the Google button.

    The frontend asks rather than being told at build time, so the same
    bundle works against a deployment with Google configured and one
    without. Returns no secret -- only whether sign-in is possible.
    """
    return {"enabled": settings.google_oauth_configured}


@router.get("/google/start")
def google_start(next: str = "", db: Session = Depends(get_db)):
    """Begin Google sign-in by redirecting to Google's consent screen."""
    if not settings.auth_configured:
        raise HTTPException(503, "Authentication is not configured on this server")
    if not settings.google_oauth_configured:
        raise HTTPException(503, "Google sign-in is not configured on this server")

    return RedirectResponse(authorization_url(db, next_url=next),
                            status_code=307)


def _link_or_create(db: Session, identity: GoogleIdentity) -> User:
    """Find the account behind a verified Google identity, or make one.

    Three cases, in this order:

    1. **Known `sub`** -- the normal return visit. Matched on `sub` and not
       email, so an account whose Google email changed is still recognised.
    2. **Known email, no `sub`** -- someone who registered with a password
       and is now using the Google button. The Google identity is attached
       to that existing account. This is only safe because the email was
       verified by Google upstream; an unverified one would let a stranger
       claim the account by signing up to Google with its address.
    3. **Neither** -- a new account.
    """
    user = db.query(User).filter(User.google_sub == identity.sub).first()

    if user is None:
        user = db.query(User).filter(User.email == identity.email).first()
        if user is not None:
            logger.info("Linking Google identity to existing account %s", user.email)
            user.google_sub = identity.sub

    if user is None:
        first = db.query(User.id).first() is None
        user = User(
            email=identity.email,
            display_name=identity.name[:120],
            # No password: this account signs in with Google only, until
            # its owner sets one.
            password_hash=None,
            google_sub=identity.sub,
            role=UserRole.ADMIN if first else UserRole.STUDENT,
        )
        db.add(user)
        logger.info("Created %s from Google as %s", identity.email, user.role)

    # Refreshed each time: Google's avatar URLs expire, and the display
    # name may have changed upstream.
    if identity.picture:
        user.avatar_url = identity.picture[:512]
    if identity.name and not user.display_name:
        user.display_name = identity.name[:120]

    user.last_login_at = datetime.utcnow()
    db.commit()
    db.refresh(user)
    return user


def _failure_redirect(message: str) -> RedirectResponse:
    """Send the browser back to the sign-in screen with a reason.

    A redirect rather than a JSON error because the user is in a browser
    mid-flow: a raw 401 body would leave them on a blank API page with no
    way back.
    """
    base = settings.OAUTH_SUCCESS_REDIRECT
    return RedirectResponse(f"{base}?{urlencode({'error': message})}", status_code=307)


@router.get("/google/callback")
def google_callback(
    request: Request,
    db: Session = Depends(get_db),
    code: str = Query(default=""),
    state: str = Query(default=""),
    error: str = Query(default=""),
):
    """Where Google sends the browser back.

    Tokens leave in the URL *fragment*, not the query string. A fragment is
    never sent to a server and does not appear in server logs or the
    Referer header, which a query parameter does -- that is the difference
    between a token that stays in the browser and one that lands in an
    access log.
    """
    if error:
        # The ordinary case is the user pressing "cancel" on the consent
        # screen, which is not an error worth alarming them about.
        return _failure_redirect(
            "Sign-in was cancelled" if error == "access_denied"
            else "Google could not complete sign-in"
        )

    if not settings.google_oauth_configured:
        return _failure_redirect("Google sign-in is not configured")
    if not code or not state:
        return _failure_redirect("That sign-in link was incomplete")

    try:
        # Consuming the state proves this callback belongs to a sign-in
        # this server started, which is what stops a forged callback from
        # logging someone into an attacker's account.
        pending = login_store.consume(db, state)
        id_token = exchange_code(code, pending.verifier)
        identity = verify_id_token(id_token)
    except AuthError as exc:
        logger.warning("Google sign-in failed: %s", exc)
        return _failure_redirect(str(exc))

    user = _link_or_create(db, identity)

    if not user.is_active:
        return _failure_redirect("That account has been disabled")

    tokens = _tokens(db, user, request)
    fragment = urlencode({
        "access_token": tokens["access_token"],
        "refresh_token": tokens["refresh_token"],
        "expires_in": tokens["expires_in"],
        "next": pending.next_url or "/",
    })
    return RedirectResponse(
        f"{settings.OAUTH_SUCCESS_REDIRECT}#{fragment}", status_code=307
    )
