"""A rate-limited fallback waits and retries instead of failing.

Groq's free tier caps *tokens* per minute, not just requests. One
ordinary follow-up -- conversation history plus retrieved book excerpts
-- can exceed 8,000 TPM by itself, and the refusal says how long to
wait, usually a fraction of a second.

Before this, every non-200 raised the same bare RuntimeError, so a
"try again in 307.5ms" was indistinguishable from a malformed request
and nothing retried it. The answer failed, the row was marked failed,
and the student saw a question that never completed -- after the first
one in the conversation had worked, which is what made it confusing.
"""

from . import env_setup  # noqa: F401  (before any app import)

import pytest

from app.ai import fallback


class FakeResponse:
    """Only what _retry_after_seconds reads."""

    def __init__(self, text: str = "", headers: dict | None = None):
        self.text = text
        self.headers = headers or {}


# The two bodies below are copied verbatim from CloudWatch, which is the
# point: a parser written against imagined wording is not evidence.
GROQ_SUB_SECOND = (
    '{"error":{"message":"Rate limit reached for model '
    '`openai/gpt-oss-120b` in organization `org_01k4` service tier '
    '`on_demand` on tokens per minute (TPM): Limit 8000, Used 5223, '
    'Requested 2818. Please try again in 307.5ms. Need more tokens?"}}'
)
GROQ_SECONDS = (
    '{"error":{"message":"Rate limit reached ... Limit 8000, Used 5212, '
    'Requested 5318. Please try again in 18.974999999s. Need more"}}'
)


@pytest.mark.parametrize("body,expected", [
    (GROQ_SUB_SECOND, 0.3075),
    (GROQ_SECONDS, 18.975),
    ('{"error":{"message":"try again in 2s"}}', 2.0),
])
def test_the_wait_is_read_from_the_body(body, expected):
    assert fallback._retry_after_seconds(FakeResponse(body)) == \
        pytest.approx(expected)


def test_the_header_wins_when_present():
    got = fallback._retry_after_seconds(
        FakeResponse("try again in 9s", {"retry-after": "1.5"})
    )
    assert got == pytest.approx(1.5)


def test_an_http_date_header_falls_through_to_the_body():
    """Retry-After may be a date; the body still carries a usable figure."""
    got = fallback._retry_after_seconds(
        FakeResponse("try again in 2s",
                     {"retry-after": "Wed, 21 Oct 2026 07:28:00 GMT"})
    )
    assert got == pytest.approx(2.0)


def test_the_waits_the_free_tier_actually_asks_for_are_honoured():
    """Pins the ceiling against observed values, not a guessed one.

    Measured: a question costs ~4,000 tokens of an 8,000-per-minute
    bucket, and Groq asked for 29.4s and 30.4s once two were in flight.
    A 25s cap turned those into failures for the sake of five seconds.
    """
    for seconds in (29.3625, 30.3975):
        got = fallback._retry_after_seconds(
            FakeResponse(f"try again in {seconds}s")
        )
        assert got == pytest.approx(seconds), (
            f"a {seconds}s wait is within what the free tier asks for and "
            "must be waited out rather than failed"
        )


def test_a_long_wait_is_refused():
    """Past the ceiling, waiting is worse than failing.

    The student is watching a spinner, and a minute of silence is
    indistinguishable from the hang this replaced. None means the caller
    gives up rather than inventing a delay.
    """
    assert fallback._retry_after_seconds(
        FakeResponse("try again in 90s")
    ) is None


def test_no_hint_means_no_wait():
    assert fallback._retry_after_seconds(FakeResponse("rate limited")) is None


def test_a_429_is_its_own_exception(monkeypatch):
    """So a caller can tell "come back shortly" from "this is broken"."""
    monkeypatch.setattr(fallback.settings, "FALLBACK_API_KEY", "test-key")

    def fake_post(*_args, **_kwargs):
        class R:
            status_code = 429
            text = GROQ_SUB_SECOND
            headers: dict = {}
        return R()

    monkeypatch.setattr(fallback.httpx, "post", fake_post)
    # One attempt, so the test asserts on the raise rather than the wait.
    monkeypatch.setattr(fallback, "RATE_LIMIT_ATTEMPTS", 1)

    with pytest.raises(fallback.FallbackRateLimited) as caught:
        fallback.generate_text("anything")
    assert caught.value.retry_after == pytest.approx(0.3075)


def test_a_rate_limit_is_retried_and_can_succeed(monkeypatch):
    """The whole point: a 429 that clears must not fail the answer."""
    monkeypatch.setattr(fallback.settings, "FALLBACK_API_KEY", "test-key")
    slept: list[float] = []
    monkeypatch.setattr(fallback.time, "sleep", slept.append)

    calls = {"n": 0}

    def fake_post(*_args, **_kwargs):
        calls["n"] += 1

        class Limited:
            status_code = 429
            text = GROQ_SUB_SECOND
            headers: dict = {}

        class Ok:
            status_code = 200
            headers: dict = {}

            @staticmethod
            def json():
                return {"choices": [{"message": {"content": "the answer"}}]}

        return Limited() if calls["n"] == 1 else Ok()

    monkeypatch.setattr(fallback.httpx, "post", fake_post)

    assert fallback.generate_text("anything") == "the answer"
    assert calls["n"] == 2, "should have re-sent after the 429"
    assert slept and slept[0] == pytest.approx(0.3075 + 0.25), (
        "should wait the provider's own figure, plus a small margin so it "
        "does not land exactly on the bucket boundary"
    )


def test_a_non_429_is_not_retried(monkeypatch):
    """A malformed request fails the same way on the next attempt."""
    monkeypatch.setattr(fallback.settings, "FALLBACK_API_KEY", "test-key")
    calls = {"n": 0}

    def fake_post(*_args, **_kwargs):
        calls["n"] += 1

        class R:
            status_code = 400
            text = '{"error":{"message":"bad schema"}}'
            headers: dict = {}
        return R()

    monkeypatch.setattr(fallback.httpx, "post", fake_post)

    with pytest.raises(RuntimeError) as caught:
        fallback.generate_text("anything")
    assert not isinstance(caught.value, fallback.FallbackRateLimited)
    assert calls["n"] == 1
