"""Configuration that must be right before the app serves a request.

Separate from lifespan because Lambda runs with ``lifespan="off"``: a
check that lives only in the startup hook protects the container and
silently skips the serverless deployment, which is where a
misconfiguration is hardest to notice.

These are fatal, not warnings. A warning about a missing signing key
scrolls past in a deploy log and leaves an app that looks healthy -- it
answers /api/health, serves the frontend, and fails only when someone
tries to sign in. Refusing to start turns that into one obvious failure
at deploy time.
"""

from .config import settings


class ConfigurationError(RuntimeError):
    """The app cannot run safely with the configuration it was given."""


def check_configuration() -> None:
    """Raise unless the app is safe to serve.

    Only genuinely unsafe or unusable states are fatal. A missing Gemini
    key disables generation but leaves a working app, so it stays a
    warning and lives in the lifespan hook.
    """
    problems: list[str] = []

    if not settings.JWT_SECRET.strip():
        problems.append(
            "JWT_SECRET is not set. Every access and refresh token is signed "
            "with it, so without it nobody can sign in. Generate one with: "
            "python -c 'import secrets; print(secrets.token_urlsafe(48))'"
        )
    elif not settings.auth_configured:
        problems.append(
            f"JWT_SECRET is only {len(settings.JWT_SECRET.strip())} characters. "
            "At least 32 are required: a short secret is brute-forceable, and "
            "forging the signature means minting a token for any account."
        )

    if settings.google_oauth_configured and not settings.GOOGLE_REDIRECT_URI.strip():
        problems.append(
            "GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET are set but "
            "GOOGLE_REDIRECT_URI is empty, so the callback has nowhere to "
            "land and sign-in would fail at the last step."
        )

    if problems:
        raise ConfigurationError(
            "Refusing to start:\n"
            + "\n".join(f"  - {p}" for p in problems)
        )
