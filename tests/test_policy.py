import datetime as dt

import pytest

from app import normalize, policy
from tests.helpers import expense

CODES = {"SW-5510": {}}


def run(sig=None, history=(), **kw):
    e = expense(**kw)
    n = normalize.normalize(e)
    n.update(id=e["id"], employee=e["employee"])
    s = {"category": (e["category"] or "unknown").title() if e["category"] else "unknown",
         "category_confidence": 0.95, "is_client": False, "client_name": "", "city": ""}
    s.update(sig or {})
    return policy.evaluate(n, s, history, CODES)


@pytest.mark.parametrize("cat,cap", [("Breakfast", 20), ("Lunch", 30), ("Dinner", 60)])
def test_meal_cap_boundaries(cat, cap):
    assert run(category=cat, amount=cap)[0] == "approve"
    assert run(category=cat, amount=cap + 0.01)[0] == "reject"


def test_client_meal_uncapped_needs_named_client():
    assert run(category="Dinner", amount=178, sig={"is_client": True, "client_name": "Acme"})[0] == "approve"
    assert run(category="Dinner", amount=178, sig={"is_client": True, "client_name": ""})[0] == "reject"


def test_weekend_meal():
    assert run(date="2026-06-06", amount=18)[0] == "reject"
    assert run(date="2026-06-06", amount=18, sig={"is_client": True, "client_name": "Acme"})[0] == "approve"


def test_receipt_threshold():
    assert run(category="Office", amount=25, receipt=False)[0] == "approve"
    d, r = run(category="Office", amount=25.01, receipt=False)
    assert d == "flag" and r[0]["rule"] == "missing_receipt"


def test_reject_outranks_missing_receipt():
    assert run(category="Dinner", amount=90, receipt=False)[0] == "reject"


def test_hotel_tiers():
    assert run(category="Hotel", amount=200, merchant="Hilton Columbus")[0] == "approve"
    assert run(category="Hotel", amount=201, merchant="Hilton Columbus")[0] == "reject"
    assert run(category="Hotel", amount=340, merchant="W Hotel San Francisco")[0] == "approve"
    assert run(category="Hotel", amount=351, merchant="W Hotel San Francisco")[0] == "reject"
    assert run(category="Hotel", amount=300, merchant="Hotel X", sig={"city": "London"})[0] == "approve"


def test_software_code():
    assert run(category="Software", amount=16)[1][0]["rule"] == "missing_approval_code"
    assert run(category="Software", amount=16, approval_code="SW-0000")[1][0]["rule"] == "unknown_approval_code"
    assert run(category="Software", amount=210, approval_code="SW-5510")[0] == "approve"


def test_entertainment_requires_client():
    assert run(category="Entertainment", amount=60)[0] == "reject"
    assert run(category="Entertainment", amount=60, sig={"is_client": True, "client_name": "Acme"})[0] == "approve"


@pytest.mark.parametrize("kw,rule", [
    ({"category": ""}, "missing_category"),
    ({"merchant": ""}, "missing_merchant"),
    ({"amount": "€65.00"}, "non_usd"),
    ({"amount": 0}, "non_positive_amount"),
    ({"amount": -40}, "non_positive_amount"),
    ({"date": "sometime"}, "invalid_date"),
])
def test_untrusted_data_flags(kw, rule):
    d, reasons = run(**kw)
    assert d == "flag" and rule in [r["rule"] for r in reasons]


def test_non_usd_over_cap_is_flag_not_reject():
    assert run(category="Dinner", amount="€500")[0] == "flag"


def test_unknown_category_flags():
    assert run(category="Gadgets", sig={"category": "unknown"})[0] == "flag"
    assert run(category="Gadgets", sig={"category": "Office", "category_confidence": 0.4})[0] == "flag"


def test_split_detection():
    prior = {"id": "T-0", "date": "2026-06-15", "merchant": "Cava", "category": "Lunch",
             "amount": 25.0, "is_client": False}
    d, r = run(amount=20, history=[prior])
    assert d == "flag" and r[0]["rule"] == "possible_split"
    far = dict(prior, date="2026-06-10")
    assert run(amount=20, history=[far])[0] == "approve"
    other = dict(prior, merchant="Chipotle")
    assert run(amount=20, history=[other])[0] == "approve"


def test_duplicate_flags():
    prior = {"id": "T-0", "date": "2026-06-15", "merchant": "CAVA", "category": "Lunch",
             "amount": 20.0, "is_client": False, "status": "approve"}
    d, r = run(amount=20, history=[prior])
    assert d == "flag" and r[0]["rule"] == "possible_duplicate" and "T-0" in r[0]["detail"]
    assert run(amount=20, history=[dict(prior, status="reject")])[0] == "approve"   # rejected original
    assert run(amount=21, history=[prior])[0] == "flag"                              # split rule instead
    assert run(amount=20, history=[dict(prior, date="2026-06-16")])[0] == "flag"     # adjacent day -> split
    assert run(amount=20, history=[dict(prior, date="2026-06-20")])[0] == "approve"


def test_duplicate_applies_to_uncapped_categories():
    prior = {"id": "T-0", "date": "2026-06-15", "merchant": "Uber", "category": "GroundTransport",
             "amount": 32.4, "is_client": False, "status": "approve"}
    d, r = run(category="Uber", merchant="Uber", amount=32.4, sig={"category": "GroundTransport"}, history=[prior])
    assert d == "flag" and r[0]["rule"] == "possible_duplicate"


def test_high_amount_backstop():
    client = {"is_client": True, "client_name": "Acme"}
    assert run(category="Dinner", amount=1000, sig=client)[0] == "approve"
    d, r = run(category="Dinner", amount=1000.01, sig=client)
    assert d == "flag" and r[0]["rule"] == "high_amount_review"
    assert run(category="Airfare", amount=2400, sig={"category": "Airfare"})[0] == "flag"
    assert run(category="Dinner", amount=5000)[0] == "reject"   # a reject stays a reject


def test_future_date_flags():
    d, r = run(date="2999-01-01")
    assert d == "flag" and "future_date" in [x["rule"] for x in r]


def test_today_is_pinned_for_tests():
    from app import config
    assert str(config.today()) == "2026-10-27"


def test_over_six_months_old_goes_to_a_human():
    office = {"category": "Office", "merchant": "Staples"}        # weekday-proof: no weekend-meal rule
    d, r = run(date="2026-04-26", **office)
    assert d == "flag" and [x["rule"] for x in r] == ["stale_date"]
    assert run(date="2026-04-27", **office)[0] == "approve"       # exactly 6 months is not over
    assert run(date="2016-06-15", **office)[0] == "flag"          # year typo
    assert run(date="06/15/00", **office)[0] == "flag"            # two-digit year read as 2000
    assert run(date="2026-04-26", category="Dinner", amount=95)[0] == "reject"  # a reject stays a reject


def test_month_end_cutoff_clamps():
    n = normalize.normalize(expense(date="2026-02-28", category="Office"))
    n.update(id="T-1", employee="Dana Ng")
    s = {"category": "Office", "category_confidence": 1, "is_client": False, "client_name": "", "city": ""}
    assert policy.evaluate(n, s, (), CODES, today=dt.date(2026, 8, 31))[0] == "approve"  # cutoff Feb 28
    assert policy.evaluate(n, s, (), CODES, today=dt.date(2026, 9, 1))[0] == "flag"


@pytest.mark.parametrize("merchant", ["N/A", "n/a", "-", ".", "???", "unknown", "None", "TBD", " -- "])
def test_placeholder_merchant_is_missing(merchant):
    d, r = run(merchant=merchant)
    assert d == "flag" and r[0]["rule"] == "missing_merchant"


@pytest.mark.parametrize("merchant", ["7-Eleven", "Bar 51", "Noma", "A&W"])
def test_short_or_odd_real_merchants_are_fine(merchant):
    assert run(merchant=merchant)[0] == "approve"


@pytest.mark.parametrize("employee", ["", "   ", None])
def test_blank_employee_flags(employee):
    d, r = run(employee=employee)
    assert d == "flag" and r[0]["rule"] == "missing_employee"


@pytest.mark.parametrize("memo", ["3 nights", "2-night stay", "two nights, Columbus", "Nights of 6/1-6/3"])
def test_multi_night_hotel_goes_to_a_human(memo):
    # The cap is per night, but nights aren't divided automatically: a person checks the rate.
    d, r = run(category="Hotel", merchant="Hilton Columbus", amount=540, memo=memo)
    assert d == "flag" and r[0]["rule"] == "multi_night_hotel"
    assert run(category="Hotel", merchant="Hilton Columbus", amount=180, memo=memo)[0] == "flag"


@pytest.mark.parametrize("memo", ["1 night", "one night", "overnight", ""])
def test_single_night_hotel_still_capped(memo):
    assert run(category="Hotel", merchant="Hilton Columbus", amount=190, memo=memo)[0] == "approve"
    assert run(category="Hotel", merchant="Hilton Columbus", amount=260, memo=memo)[0] == "reject"
