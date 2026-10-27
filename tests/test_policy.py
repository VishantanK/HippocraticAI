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
             "amount": 25.0, "currency": "USD", "is_client": False}
    d, r = run(amount=20, history=[prior])
    assert d == "flag" and r[0]["rule"] == "possible_split"
    far = dict(prior, date="2026-06-10")
    assert run(amount=20, history=[far])[0] == "approve"
    other = dict(prior, merchant="Chipotle")
    assert run(amount=20, history=[other])[0] == "approve"
