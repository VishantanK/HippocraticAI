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


# --- Finance's delivery panel: list problems, retry one, retry all ---------------------------

def _kill(eid, monkeypatch):
    monkeypatch.setattr(poster, "post_decision", lambda d: False)
    pipeline.process(expense(id=eid), source="batch")
    for n in range(1, outbox.MAX_ATTEMPTS + 1):
        outbox.run_due(now=later(n))
    assert post_row(eid)["post_status"] == "dead"


def test_problems_lists_latest_failed_and_dead(db, monkeypatch):
    _kill("D-1", monkeypatch)
    pipeline.process(expense(id="D-2"), source="batch")           # failed once, not dead
    monkeypatch.setattr(poster, "post_decision", lambda d: True)
    pipeline.process(expense(id="D-3"), source="batch")           # sent
    rows = {r["expense_id"]: r for r in store.delivery_problems()}
    assert set(rows) == {"D-1", "D-2"}
    assert rows["D-1"]["post_status"] == "dead" and rows["D-1"]["post_attempts"] == outbox.MAX_ATTEMPTS
    assert rows["D-1"]["last_error"] and rows["D-1"]["employee"] is not None


def test_retry_dead_delivers_exactly_once(db, monkeypatch):
    _kill("D-1", monkeypatch)
    calls = []
    monkeypatch.setattr(poster, "post_decision", lambda d: calls.append(d["decision_key"]) or True)
    assert outbox.retry("D-1", 1) == "sent"
    assert outbox.retry("D-1", 1) is None                          # already sent: nothing to do
    assert calls == ["D-1:1"] and post_row("D-1")["post_status"] == "sent"


def test_retry_that_fails_stays_dead(db, monkeypatch):
    _kill("D-1", monkeypatch)
    assert outbox.retry("D-1", 1) == "dead"


def test_retry_refuses_superseded_revision(db, monkeypatch):
    _kill("D-1", monkeypatch)
    pipeline.human_override("D-1", "reject", "x")                 # rev 2 (fails: poster still down)
    calls = []
    monkeypatch.setattr(poster, "post_decision", lambda d: calls.append(d["decision_key"]) or True)
    assert outbox.retry("D-1", 1) is None and calls == []
    assert outbox.retry("D-1", 2) == "sent" and calls == ["D-1:2"]


def test_retry_all(db, monkeypatch):
    _kill("D-1", monkeypatch)
    pipeline.process(expense(id="D-2"), source="batch")
    monkeypatch.setattr(poster, "post_decision", lambda d: True)
    assert outbox.retry_all() == {"sent": 2, "failed": 0}
    assert store.delivery_problems() == []


def test_stats_count_only_latest_undelivered(db, monkeypatch):
    _kill("D-1", monkeypatch)                                       # rev 1 dead
    monkeypatch.setattr(poster, "post_decision", lambda d: True)
    pipeline.human_override("D-1", "reject", "x")                  # rev 2 sent: rev 1 no longer matters
    s = store.stats()
    assert s["post"]["dead"] == 0 and s["post"]["failed"] == 0
    assert len(store.delivery_problems()) == 0
