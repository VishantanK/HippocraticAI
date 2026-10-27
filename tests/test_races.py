"""Guarantees found by review: ordering, human decisions, same-employee races, sticky duplicates."""

import datetime as dt
import threading

import pytest

from app import jobs, outbox, pipeline, poster, store
from tests.helpers import clean_screen, expense, extractor

LATER = dt.datetime(2100, 1, 1, tzinfo=dt.timezone.utc)


@pytest.fixture()
def db(tmp_path, monkeypatch):
    store.reset(str(tmp_path / "r.db"))
    monkeypatch.setattr(pipeline.llm, "classify_injection", clean_screen)
    monkeypatch.setattr(pipeline.llm, "extract", extractor())
    monkeypatch.setattr(pipeline.llm, "generate_question", lambda raw, reasons: "q")
    monkeypatch.setattr(poster, "post_decision", lambda d: True)


def latest(eid):
    return store.expense_detail(eid)["decisions"][-1]


def test_superseded_revision_is_never_delivered(db, monkeypatch):
    sent = []
    state = {"up": False}
    monkeypatch.setattr(poster, "post_decision", lambda d: state["up"] and not sent.append(d["decision_key"]))
    pipeline.process(expense(id="R-1"), source="batch")             # rev 1 fails
    state["up"] = True
    pipeline.human_override("R-1", "reject", "no")                  # rev 2 sent
    outbox.run_due(now=LATER)
    assert sent == ["R-1:2"]
    assert store.expense_detail("R-1")["decisions"][0]["post_status"] == "superseded"


def test_row_is_claimed_once(db):
    pipeline.process(expense(id="R-2"), source="batch")
    store.record_post("R-2", 1, "failed", "x", None)                # make it due again
    assert store.claim_post("R-2", 1) is not None
    assert store.claim_post("R-2", 1) is None                       # second claimer loses


def test_queued_job_does_not_overwrite_human_decision(db):
    pipeline.process(expense(id="R-3", amount=10), source="portal")  # approve
    store.set_status("R-3", "checking")                              # e.g. an answer queued a job
    pipeline.human_override("R-3", "reject", "policy exception denied")
    assert pipeline.process_stored("R-3") is None                    # job sees nothing new
    assert latest("R-3")["decided_by"] == "human" and store.get_expense("R-3")["status"] == "reject"


def test_edit_after_human_review_cannot_auto_approve(db):
    pipeline.process(expense(id="R-4", amount=50), source="portal")  # reject (over lunch cap)
    pipeline.human_override("R-4", "reject", "over cap")
    pipeline.process(expense(id="R-4", amount=12), source="portal")  # edited to something approvable
    d = latest("R-4")
    assert d["decision"] == "flag" and "edited_after_review" in [r["rule"] for r in d["payload"]["reasons"]]


def test_same_employee_parallel_duplicates_caught(db, monkeypatch):
    barrier = threading.Barrier(2, timeout=2)
    base = extractor()

    def slow_extract(e):
        try:
            barrier.wait()        # without serialisation both evaluations overlap here
        except threading.BrokenBarrierError:
            pass                  # serialised: the second never meets the first
        return base(e)

    monkeypatch.setattr(pipeline.llm, "extract", slow_extract)
    threads = [threading.Thread(target=pipeline.process, args=(expense(id=f"R-5{i}", amount=20), "portal"))
               for i in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    rules = [r["rule"] for i in range(2) for r in latest(f"R-5{i}")["payload"]["reasons"]]
    assert rules.count("possible_duplicate") == 1


def test_answer_cannot_clear_duplicate(db):
    pipeline.process(expense(id="R-6a", amount=20, merchant="Chipotle"), source="portal")
    pipeline.process(expense(id="R-6b", amount=20, merchant="Chipotle"), source="portal")
    assert latest("R-6b")["decision"] == "flag"
    store.add_answer("R-6b", {"text": "", "fields": {"amount": "19.99", "merchant": "Chipotle #12"}})
    pipeline.process_stored("R-6b")
    d = latest("R-6b")
    assert d["decision"] == "flag" and "possible_duplicate" in [r["rule"] for r in d["payload"]["reasons"]]


def test_crashed_job_records_fail_closed_flag(db, monkeypatch):
    store.upsert_expense("R-7", expense(id="R-7"), "portal")
    store.set_status("R-7", "checking")

    def boom(*a, **k):
        raise RuntimeError("bug")

    monkeypatch.setattr(pipeline, "evaluate", boom)
    jobs.enqueue("R-7")
    assert jobs.wait_idle(5)
    d = latest("R-7")
    assert d["decision"] == "flag" and d["payload"]["reasons"][0]["rule"] == "check_failed"
    assert store.get_expense("R-7")["status"] == "flag"
