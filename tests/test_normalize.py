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


def test_ambiguous_or_mistyped_amounts_are_unreadable():
    # A typo must be asked about, not guessed: "12,50" is not $1,250 and "1.234,56" is not $1.23.
    for raw in ["12,50", "1,5", "1,0000", "1.234,56", "1,234.5,6", "15.999", "15.", ".5",
                "1e1", "1e308", "1_5", "nan", "inf", "Infinity", "１５", "١٥"]:
        assert parse_amount(raw)[0] is None and parse_amount(raw)[2], raw
    assert parse_amount("1,234.56") == (1234.56, None, None)      # proper thousands grouping is fine
    assert parse_amount("$$15") == (15.0, None, None)
    assert parse_amount("-$15") == (-15.0, None, None)            # parsed; policy flags it as non-positive


def test_non_finite_or_sub_cent_numbers_are_unreadable():
    for raw in [float("nan"), float("inf"), float("-inf"), 15.999]:
        assert parse_amount(raw)[0] is None and parse_amount(raw)[2], raw
    assert parse_amount(52.75) == (52.75, None, None)
    assert parse_amount(32.4) == (32.4, None, None)
