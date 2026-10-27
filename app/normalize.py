"""Deterministic parsing of the messy raw fields (amount, currency, date)."""

import datetime as dt
import re

CURRENCY_SYMBOLS = {"$": "USD", "€": "EUR", "£": "GBP", "¥": "JPY", "₹": "INR"}
CURRENCY_CODES = {"USD", "EUR", "GBP", "CAD", "JPY", "INR", "AUD"}


def parse_amount(raw):
    """Return (amount: float|None, currency: str|None, error: str|None).

    Plain numbers are USD. Strings may carry a symbol or ISO code.
    """
    if isinstance(raw, bool):
        return None, None, "amount is not a number"
    if isinstance(raw, (int, float)):
        return float(raw), "USD", None
    if not isinstance(raw, str) or not raw.strip():
        return None, None, "amount is missing"

    s = raw.strip().upper().replace(",", "")
    currency = None
    for sym, code in CURRENCY_SYMBOLS.items():
        if sym in s:
            currency = code
            s = s.replace(sym, "")
    for code in CURRENCY_CODES:
        if re.search(rf"\b{code}\b", s):
            if currency and currency != code:
                return None, None, "conflicting currency markers"
            currency = code
            s = re.sub(rf"\b{code}\b", "", s)
    if currency is None and re.search(r"[^\d.\s-]", s):
        return None, None, f"unrecognised currency in {raw!r}"
    s = s.strip()
    try:
        value = float(s)
    except ValueError:
        return None, None, f"could not parse amount {raw!r}"
    return value, currency or "USD", None


def parse_date(raw):
    """Return (date|None, error|None). Accepts ISO and US MM/DD/YYYY."""
    if not isinstance(raw, str) or not raw.strip():
        return None, "date is missing"
    s = raw.strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%Y/%m/%d"):
        try:
            return dt.datetime.strptime(s, fmt).date(), None
        except ValueError:
            continue
    return None, f"unrecognised date format {raw!r}"


def normalize(expense):
    """Deterministic normalisation. Never raises; errors are collected."""
    amount, currency, amount_err = parse_amount(expense.get("amount"))
    date, date_err = parse_date(expense.get("date"))
    category_raw = (expense.get("category") or "").strip()
    merchant = (expense.get("merchant") or "").strip()
    code = expense.get("approval_code")
    code = code.strip().upper() if isinstance(code, str) and code.strip() else None
    receipt = expense.get("receipt")
    return {
        "amount": amount,
        "currency": currency,
        "date": date.isoformat() if date else None,
        "weekday": date.strftime("%a") if date else None,
        "is_weekend": date.weekday() >= 5 if date else None,
        "category_raw": category_raw,
        "merchant": merchant,
        "memo": (expense.get("memo") or "").strip(),
        "receipt": receipt is True,  # anything other than literal true = no receipt
        "approval_code": code,
        "errors": [e for e in (amount_err, date_err) if e],
    }
