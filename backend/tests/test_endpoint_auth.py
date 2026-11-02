"""Every endpoint requires a token unless it is deliberately public.

This sweeps the live OpenAPI schema rather than listing routes by hand,
so a new endpoint is covered the moment it is added. That is the point:
the original gap was not a wrong decision about one route, it was fifteen
routes that nobody re-checked.
"""

from . import env_setup  # noqa: F401  (before app.main is imported)

import pytest

#: The only routes that may answer without a token, each for a reason.
PUBLIC = {
    # A health check that needs auth cannot report that auth is broken.
    ("GET", "/api/health"),
    # Sign-in happens before a token exists.
    ("POST", "/api/auth/login"),
    ("POST", "/api/auth/register"),
    ("POST", "/api/auth/refresh"),
    ("GET", "/api/auth/google/config"),
    ("GET", "/api/auth/google/start"),
    ("GET", "/api/auth/google/callback"),
}

PATH_PARAMS = {
    "card_id": "1", "question_id": "1", "session_id": "1", "paper_id": "1",
    "thread_id": "1", "concept_id": "1", "position": "1", "level": "subject",
    "node_id": "1", "on": "2026-01-01", "view": "due",
}


def _all_routes() -> list[tuple[str, str]]:
    """Every (method, path) in the schema, read from the app directly.

    Taken from app.openapi() rather than a request, because this runs at
    collection time -- before fixtures exist. app.routes would not do:
    an included router appears there as one opaque object, not as the
    routes it carries.
    """
    from app.main import app

    found = set()
    for path, operations in app.openapi()["paths"].items():
        for method in operations:
            if method.upper() in ("GET", "POST", "PUT", "PATCH", "DELETE"):
                found.add((method.upper(), path))
    return sorted(found)


ROUTES = _all_routes()


def _concrete(path: str) -> str:
    for name, value in PATH_PARAMS.items():
        path = path.replace("{" + name + "}", value)
    return path


def test_the_public_list_matches_the_schema():
    """Guards the allow-list itself: a renamed route must be noticed."""
    stale = {r for r in PUBLIC if r not in set(ROUTES)}
    assert not stale, f"PUBLIC names routes that no longer exist: {stale}"


@pytest.mark.parametrize("method,path", ROUTES)
def test_route_requires_authentication(client, method, path):
    if (method, path) in PUBLIC:
        pytest.skip("deliberately public")

    res = client.request(method, _concrete(path), json={})
    assert res.status_code in (401, 403), (
        f"{method} {path} answered {res.status_code} with no token; "
        "add it to PUBLIC with a reason, or add an auth dependency"
    )
