"""The mock eval set is well-formed: run by `eval.py --suite mock` against live LLMs."""

import datetime as dt
import json
import os

import eval as ev

PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "mock_cases.json")


def cases():
    with open(PATH) as f:
        return json.load(f)


def test_hundred_unique_labelled_cases():
    cs = cases()
    assert len(cs) == 100
    assert len({c["id"] for c in cs}) == 100
    assert {c["expected"] for c in cs} == {"approve", "reject", "flag"}
    for c in cs:
        assert c["id"] == c["expense"]["id"]
        assert c["mode"] and c["note"] and c["expected_rule"]


def test_weekend_cases_fall_on_a_weekend():
    for c in cases():
        if c["mode"] != "weekend":
            continue
        d = ev.normalize.parse_date(c["expense"]["date"])[0]
        assert d.weekday() >= 5, c["id"]


def test_history_belongs_to_the_same_employee():
    for c in cases():
        for h in c.get("history", []):
            assert h["expense"]["employee"] == c["expense"]["employee"]
            assert h["status"] in ev.LABELS


def test_history_is_built_from_normalised_priors():
    c = next(c for c in cases() if c.get("history"))
    hist = ev.build_history(c)
    assert hist[0]["id"] == c["history"][0]["expense"]["id"]
    assert hist[0]["status"] == c["history"][0]["status"]
    assert hist[0]["date"] == dt.date.fromisoformat(c["history"][0]["expense"]["date"]).isoformat()


def test_rule_match_accepts_a_list():
    assert ev.rule_matches(["non_usd", "invalid_amount"], [{"rule": "invalid_amount"}])
    assert not ev.rule_matches("missing_receipt", [{"rule": "within_policy"}])
