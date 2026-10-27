from app.normalize import normalize, parse_amount, parse_date


def test_amount_forms():
    # No currency conversion or identification: USD unless a non-$ currency symbol is present.
    assert parse_amount(18.5) == (18.5, None, None)
    assert parse_amount("$28.00") == (28.0, None, None)
    assert parse_amount("28.00") == (28.0, None, None)           # no symbol -> USD
    assert parse_amount("US$ 1,200.50") == (1200.5, None, None)
    assert parse_amount("40 USD") == (40.0, None, None)
    assert parse_amount("€65.00") == (None, "€", None)           # non-USD symbol -> flagged upstream
    assert parse_amount("£10")[1] == "£" and parse_amount("₹900")[1] == "₹" and parse_amount("¥5")[1] == "¥"
    assert parse_amount("₩5000")[1] == "₩"                       # any currency symbol, not a fixed list
    assert parse_amount("65 EUR")[2]                              # letters aren't a currency we read: unreadable
    assert parse_amount("twelve")[2]
    assert parse_amount(None)[2] and parse_amount(True)[2]


def test_normalize_amount_fields():
    n = normalize({"amount": "€65.00"})
    assert n["amount"] is None and n["foreign_symbol"] == "€" and "currency" not in n
    n = normalize({"amount": "$12"})
    assert n["amount"] == 12.0 and n["foreign_symbol"] is None


def test_dates_and_weekend():
    assert str(parse_date("05/12/2026")[0]) == "2026-05-12"
    assert parse_date("12th May")[0] is None
    n = normalize({"date": "2026-06-06", "amount": 1})
    assert n["weekday"] == "Sat" and n["is_weekend"] is True


def test_receipt_must_be_literal_true():
    assert normalize({"receipt": "yes"})["receipt"] is False
    assert normalize({"receipt": True})["receipt"] is True
