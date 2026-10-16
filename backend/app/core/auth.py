"""Who is making this request, and may they.

`current_user` is the dependency almost every endpoint wants. It reads the
access token, loads the account, and refuses a disabled one. Authorising a
request costs one indexed primary-key lookup -- the role travels in the
token, so no join is needed to decide what is allowed.

`optional_user` exists for the handful of endpoints that are useful
unauthenticated, and `admin_user` for the ones that spend quota or change
the shared corpus.
"""

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from ..models.users import User, UserRole
from .database import get_db
from .security import AuthError, decode_token

#: auto_error=False so a missing header reaches our own handler and
#: produces a message a client can act on, rather than FastAPI's bare 403.
_scheme = HTTPBearer(auto_error=False)

_UNAUTHENTICATED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Sign in to continue",
    headers={"WWW-Authenticate": "Bearer"},
)


def _user_from_token(token: str, db: Session) -> User:
    try:
        payload = decode_token(token, expect="access")
    except AuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    user = db.query(User).filter(User.id == int(payload["sub"])).first()
    if user is None or not user.is_active:
        # One message for both cases: distinguishing them would confirm
        # which accounts exist.
        raise _UNAUTHENTICATED
    return user


def current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_scheme),
    db: Session = Depends(get_db),
) -> User:
    """The signed-in account, or 401."""
    if credentials is None:
        raise _UNAUTHENTICATED
    return _user_from_token(credentials.credentials, db)


def optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_scheme),
    db: Session = Depends(get_db),
) -> User | None:
    """The signed-in account, or None.

    For endpoints that work either way -- the syllabus tree is the same for
    everyone, but knowing who is asking lets it carry their progress.
    """
    if credentials is None:
        return None
    try:
        return _user_from_token(credentials.credentials, db)
    except HTTPException:
        return None


def admin_user(user: User = Depends(current_user)) -> User:
    """An admin, or 403.

    Guards the operations that spend API quota or change the shared
    corpus: ingestion, generation, paper import. A student drilling
    questions should not be able to start a thousand-page vision run.
    """
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="That action needs an admin account",
        )
    return user
