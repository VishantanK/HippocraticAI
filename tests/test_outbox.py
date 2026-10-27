"""POST delivery: retried with backoff, idempotency key, gives up as 'dead'."""

import datetime as dt

import pytest

from app import outbox, pipeline, poster, store
from tests.helpers import clean_screen, expense, extractor

FAR_FUTURE = dt.datetime(2100, 1, 1, tzinfo=dt.timezone.utc)


def later(n):
    """A clock n hours past FAR_FUTURE, so every backoff (max 5 min) has elapsed."""
    return FAR_FUTURE + dt.timedelta(hours=n)


@pytest.fixture()
def db(tmp_path, monkeypatch):
    store.reset(str(tmp_path / "o.db"))
    monkeypatch.setattr(pipeline.llm, "classify_injection", clean_screen)
    monkeypatch.setattr(pipeline.llm, "extract", extractor())
    monkeypatch.setattr(pipeline.llm, "generate_question", lambda raw, reasons: "q")


def post_row(eid):
    return store.expense_detail(eid)["decisions"][-1]


def test_retries_until_sent(db, monkeypatch):
    calls = []
    monkeypatch.setattr(poster, "post_decision", lambda d: calls.append(d) or len(calls) >= 3)
    pipeline.process(expense(id="O-1"), source="batch")          # attempt 1 fails
    row = post_row("O-1")
    assert row["post_status"] == "failed" and row["post_attempts"] == 1 and row["next_attempt_at"]
    assert outbox.run_due() == 0                                  # backoff not elapsed yet
    outbox.run_due(now=later(1))                                  # attempt 2 fails
    outbox.run_due(now=later(2))                                  # attempt 3 succeeds
    row = post_row("O-1")
    assert row["post_status"] == "sent" and row["post_attempts"] == 3
    assert {c["decision_key"] for c in calls} == {"O-1:1"}        # same key every attempt


def test_gives_up_as_dead(db, monkeypatch):
    monkeypatch.setattr(poster, "post_decision", lambda d: False)
    pipeline.process(expense(id="O-2"), source="batch")
    for i in range(outbox.MAX_ATTEMPTS + 2):
        outbox.run_due(now=later(i))
    row = post_row("O-2")
    assert row["post_status"] == "dead" and row["post_attempts"] == outbox.MAX_ATTEMPTS


def test_flush_delivers_failed(db, monkeypatch):
    state = {"up": False}
    monkeypatch.setattr(poster, "post_decision", lambda d: state["up"])
    pipeline.process(expense(id="O-3"), source="batch")
    state["up"] = True
    assert outbox.flush() == {"sent": 1, "failed": 0}
    assert post_row("O-3")["post_status"] == "sent"


def test_idempotency_header(monkeypatch):
    seen = {}

    class Resp:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *a): return False

    def fake_urlopen(req, timeout):
        seen.update(req.headers)
        return Resp()

    monkeypatch.setattr(poster.urllib.request, "urlopen", fake_urlopen)
    assert poster.post_decision({"id": "X", "decision_key": "X:2"})
    assert seen.get("Idempotency-key") == "X:2"
