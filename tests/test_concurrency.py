"""Concurrent writes to one expense must serialise into clean revisions 1..N."""

import threading

import pytest

from app import pipeline, store
from tests.helpers import clean_screen, expense, extractor


@pytest.fixture()
def db(tmp_path, monkeypatch):
    store.reset(str(tmp_path / "c.db"))
    monkeypatch.setattr(pipeline.poster, "post_decision", lambda d: True)
    monkeypatch.setattr(pipeline.llm, "classify_injection", clean_screen)
    monkeypatch.setattr(pipeline.llm, "extract", extractor())
    monkeypatch.setattr(pipeline.llm, "generate_question", lambda raw, reasons: "q")


def run_parallel(fn, n=10):
    errors, barrier = [], threading.Barrier(n)

    def worker(i):
        barrier.wait()
        try:
            fn(i)
        except Exception as e:  # collected, asserted below
            errors.append(e)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return errors


def test_concurrent_overrides_get_unique_revisions(db):
    pipeline.process(expense(id="C-1"), source="portal")
    errors = run_parallel(lambda i: pipeline.human_override("C-1", "approve" if i % 2 else "reject", f"n{i}"))
    assert errors == []
    revs = [d["revision"] for d in store.expense_detail("C-1")["decisions"]]
    assert revs == list(range(1, 12))


def test_concurrent_reprocess_gets_unique_revisions(db):
    pipeline.process(expense(id="C-2"), source="portal")
    errors = run_parallel(lambda i: pipeline.process(expense(id="C-2", amount=10 + i), source="portal"))
    assert errors == []
    detail = store.expense_detail("C-2")
    revs = [d["revision"] for d in detail["decisions"]]
    assert revs == list(range(1, 12))
    # payload revision always matches the stored row
    assert all(d["payload"]["revision"] == d["revision"] for d in detail["decisions"])
