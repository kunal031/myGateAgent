"""Cache keys and invalidation, in one place.

Every cached value that depends on a user's activity is dropped by
``invalidate_user(user_id)``. Keeping that list here rather than at each
write site is the point: an endpoint that records an attempt should not
have to know which analytics panels exist, and the failure mode of
spreading it out is a new panel that nobody remembers to invalidate --
it then serves a stale number for a full TTL with nothing to indicate
why.

Cached values are derived and carry a TTL, so a missed invalidation is
bounded staleness rather than permanent corruption. That is what makes
prefix deletion acceptable here.
"""

from ..core.cache import delete, delete_prefix, key

#: Everything under this prefix belongs to one user.
_USER_PREFIXES = (
    "stats",   # summary, deep, insights, breakdown, coverage, calendar
    "feed",    # a page of the feed, which is ordered by progress
    "profile", # the profile screen's own counters
)


def user_prefix(kind: str, user_id: int) -> str:
    """The prefix under which one user's values of a kind live."""
    return key(kind, user_id) + ":"


def invalidate_user(user_id: int) -> None:
    """Drop every cached value that depends on this user's activity.

    Called after an attempt, an exam submission or a card review -- the
    writes that change what the analytics and the feed order should say.
    """
    for kind in _USER_PREFIXES:
        delete_prefix(user_prefix(kind, user_id))
        # The un-suffixed key, for a value with no further parameters.
        delete(key(kind, user_id))


def invalidate_feed(user_id: int) -> None:
    """Drop only this user's feed pages.

    Separate from the full sweep because seeing a card reorders the feed
    without changing any analytics, and that happens on every scroll.
    """
    delete_prefix(user_prefix("feed", user_id))
    delete(key("feed", user_id))
