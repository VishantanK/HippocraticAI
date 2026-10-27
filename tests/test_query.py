"""Server-side filtering, sorting and paging for Finance's expense list (store.query_expenses)."""

import pytest

from app import store


def _add(eid, employee, date, category, merchant, amount, decision, rules, source="portal", manip=False, post=None):
    raw = {"employee": employee, "date": date, "category": category, "merchant": merchant, "amount": amount}
    store.upsert_expense(eid, raw, source)
    payload = {"id": eid, "decision": decision, "amount": amount, "category": category,
               "reasons": [{"rule": r, "detail": r} for r in rules], "suspected_manipulation": manip,
               "decided_at": store.now()}
    rev = store.add_decision(eid, 1, payload, {})
    store.set_normalized(eid, {"date": date, "amount": amount}, decision)
    if post:
        store.record_post(eid, rev, post)


@pytest.fixture
def db(tmp_path):
    store.reset(str(tmp_path / "q.db"))
    _add("E1", "Mei Lin", "2026-06-01", "Dinner", "Nobu", 72.0, "reject", ["meal_over_cap"])
    _add("E2", "Mei Lin", "2026-06-10", "Lunch", "Chipotle", 12.0, "approve", ["within_policy"])
    _add("E3", "Sofia Reyes", "2026-06-15", "Dinner", "Mamma Mia", 45.0, "flag", ["missing_receipt"], post="dead")
    _add("E4", "Sofia Reyes", "2026-06-20", "Software", "Figma", 1500.0, "flag",
         ["missing_approval_code", "high_amount_review"], source="batch")
    _add("E5", "Arjun Rao", "2026-06-25", "Office", "Staples", 30.0, "reject", ["suspected_manipulation"], manip=True)
    store.upsert_expense("E6", {"employee": "Arjun Rao", "date": "2026-06-26", "merchant": "Uber", "amount": 9}, "portal")
    store.set_status("E6", "checking")


def ids(f=None, **kw):
    rows, total = store.query_expenses(f or {}, **kw)
    return [r["id"] for r in rows], total


def test_each_filter(db):
    assert set(ids({"status": "flag"})[0]) == {"E3", "E4"}
    assert ids({"status": "checking"})[0] == ["E6"]
    assert ids({"manipulation": True})[0] == ["E5"]
    assert ids({"source": "batch"})[0] == ["E4"]
    assert set(ids({"employee": "Mei Lin"})[0]) == {"E1", "E2"}
    assert set(ids({"category": "dinner"})[0]) == {"E1", "E3"}
    assert set(ids({"date_from": "2026-06-10", "date_to": "2026-06-20"})[0]) == {"E2", "E3", "E4"}
    assert set(ids({"amount_min": 40, "amount_max": 100})[0]) == {"E1", "E3"}
    assert ids({"rule": "high_amount_review"})[0] == ["E4"]
    assert ids({"delivery": "problem"})[0] == ["E3"]
    assert set(ids({"q": "sofia"})[0]) == {"E3", "E4"}
    assert ids({"q": "mamma"})[0] == ["E3"]


def test_filters_combine(db):
    assert ids({"category": "Dinner", "amount_min": 50})[0] == ["E1"]


def test_q_is_not_a_like_wildcard(db):
    assert ids({"q": "%"})[0] == []


def test_sort_and_stable_ties(db):
    assert ids(sort="amount", direction="desc")[0][:2] == ["E4", "E1"]
    assert ids(sort="date", direction="asc")[0][0] == "E1"
    names, _ = ids(sort="employee", direction="asc")
    assert names[:2] == ["E5", "E6"]  # same employee: tie broken by id, so the order is stable


def test_paging_reports_total(db):
    page, total = ids(sort="date", direction="asc", limit=2, offset=2)
    assert page == ["E3", "E4"] and total == 6
    page, total = ids({"status": "reject"}, limit=1)
    assert len(page) == 1 and total == 2


def test_unknown_sort_falls_back(db):
    assert ids(sort="raw_json; DROP TABLE expenses")[1] == 6
