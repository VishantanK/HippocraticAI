"""Deterministic parsing of the messy raw fields (amount, date).

Amounts are always USD. There is no currency conversion or identification: an amount
marked with any non-dollar currency symbol is reported so policy can flag it and ask
the employee for the USD amount.
"""

import datetime as dt
import math
import re
import unicodedata

USD_MARKERS = re.compile(r"US\$|USD|\$", re.IGNORECASE)
# ASCII digits, commas only as thousands groups, at most two decimals. Anything else
# ("12,50", "1.234,56", "1e1", "nan", "15.999") is a likely typo: ask, don't guess.
AMOUNT_RE = re.compile(r"-?(?:[0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)(?:\.[0-9]{1,2})?")


def parse_amount(raw):
    """Return (amount: float|None, foreign_symbol: str|None, error: str|None).

    Plain numbers and $/US$/USD amounts are USD. Any other currency symbol (Unicode
    category Sc, e.g. € £ ¥ ₹ ₩) returns that symbol and no amount. A number that isn't
    plainly dollars and cents (see AMOUNT_RE; NaN/inf; sub-cent) is unreadable.
    """
    if isinstance(raw, bool):
        return None, None, "amount is not a number"
    if isinstance(raw, (int, float)):
        if not math.isfinite(raw) or round(raw, 2) != raw:
            return None, None, f"amount {raw!r} is not a dollar-and-cents value"
        return float(raw), None, None
    if not isinstance(raw, str) or not raw.strip():
        return None, None, "amount is missing"

    s = USD_MARKERS.sub("", raw)
    foreign = next((c for c in s if unicodedata.category(c) == "Sc"), None)
    if foreign:
        return None, foreign, None
    s = re.sub(r"\s+", "", s)
    if not AMOUNT_RE.fullmatch(s):
        return None, None, f"could not read amount {raw!r}"
    return float(s.replace(",", "")), None, None


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
    amount, foreign_symbol, amount_err = parse_amount(expense.get("amount"))
    date, date_err = parse_date(expense.get("date"))
    category_raw = (expense.get("category") or "").strip()
    merchant = (expense.get("merchant") or "").strip()
    code = expense.get("approval_code")
    code = code.strip().upper() if isinstance(code, str) and code.strip() else None
    receipt = expense.get("receipt")
    return {
        "amount": amount,                 # USD, or None
        "foreign_symbol": foreign_symbol,  # e.g. "€" when the amount isn't in dollars
        "amount_raw": str(expense.get("amount")) if expense.get("amount") is not None else "",
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
