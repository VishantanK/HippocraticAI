from app.normalize import normalize, parse_amount, parse_date


def test_amount_forms():
    assert parse_amount(18.5) == (18.5, "USD", None)
    assert parse_amount("$28.00") == (28.0, "USD", None)
    assert parse_amount("28.00") == (28.0, "USD", None)          # no symbol -> USD
    assert parse_amount("€65.00")[:2] == (65.0, "EUR")
    assert parse_amount("65 GBP")[:2] == (65.0, "GBP")
    assert parse_amount("1,200.50")[:2] == (1200.5, "USD")
    assert parse_amount(None)[0] is None
    assert parse_amount(True)[0] is None
    assert parse_amount("twelve")[0] is None
    assert parse_amount("$65 EUR")[2] == "conflicting currency markers"


def test_dates_and_weekend():
    assert str(parse_date("05/12/2026")[0]) == "2026-05-12"
    assert parse_date("12th May")[0] is None
    n = normalize({"date": "2026-06-06", "amount": 1})
    assert n["weekday"] == "Sat" and n["is_weekend"] is True


def test_receipt_must_be_literal_true():
    assert normalize({"receipt": "yes"})["receipt"] is False
    assert normalize({"receipt": True})["receipt"] is True
