"""Pure, deterministic policy engine. No I/O, no LLM.

evaluate(norm, signals, history) -> (decision, reasons)

  norm     output of normalize.normalize() (plus "id", "employee")
  signals  LLM-extracted facts: category, category_confidence, is_client, client_name, city
  history  other normalised expenses by the same employee, with their latest "status"
           (for duplicate and split detection)

Order: rejects that can be determined from trusted fields first, then flags,
then approve. Data we cannot trust (non-USD amount, unknown category) is a flag
before any cap is applied, because a cap can't be applied to it.
"""

import datetime as dt
import re

from . import config


def _reason(rule, detail):
    return {"rule": rule, "detail": detail}


# Words people type when they don't know the merchant; also anything with no letters or digits.
PLACEHOLDER_MERCHANTS = {"na", "n/a", "none", "null", "unknown", "tbd", "test", "misc", "various"}
# More than one night: "nights" anywhere, or a number above one before "night".
MULTI_NIGHT_RE = re.compile(
    r"\bnights\b|\b([2-9]|\d{2,}|two|three|four|five|six|seven|eight|nine|ten)[\s-]*nights?\b", re.IGNORECASE)


def is_placeholder_merchant(name):
    name = (name or "").strip().lower()
    return not re.search(r"[a-z0-9]", name) or name in PLACEHOLDER_MERCHANTS


def months_before(day, months):
    """Same day-of-month `months` earlier, clamped to the month's end (Aug 31 - 6 -> Feb 28)."""
    y, m = divmod(day.year * 12 + day.month - 1 - months, 12)
    for d in range(day.day, 27, -1):
        try:
            return dt.date(y, m + 1, d)
        except ValueError:
            continue
    return dt.date(y, m + 1, day.day)


def is_tier1(city_text):
    t = f" {(city_text or '').lower()} "
    return any(alias in t for aliases in config.TIER1_CITIES.values() for alias in aliases)


def evaluate(norm, signals, history=(), approval_codes=None, today=None):
    approval_codes = approval_codes if approval_codes is not None else config.load_approval_codes()
    today = today or config.today()
    flags, rejects = [], []

    category = signals.get("category")
    is_client = bool(signals.get("is_client")) and bool((signals.get("client_name") or "").strip())
    amount = norm["amount"]  # always USD (normalize returns None for other currencies)

    # --- data we cannot evaluate -> flag -------------------------------------
    if not norm["category_raw"]:
        flags.append(_reason("missing_category", "No category was provided."))
    elif category in (None, "unknown") or signals.get("category_confidence", 0) < 0.7:
        flags.append(_reason("unknown_category",
                             f"Category {norm['category_raw']!r} does not map to a policy category."))
    if not (norm.get("employee") or "").strip():
        flags.append(_reason("missing_employee", "No employee was given, so duplicate and split checks can't run."))
    if is_placeholder_merchant(norm["merchant"]):
        flags.append(_reason("missing_merchant", "No merchant was provided." if not norm["merchant"]
                             else f"Merchant {norm['merchant']!r} is a placeholder, not a merchant name."))
    if norm.get("foreign_symbol"):
        flags.append(_reason("non_usd", f"Amount {norm['amount_raw']} isn't in US dollars; a USD amount is needed."))
    elif amount is None:
        flags.append(_reason("invalid_amount", "; ".join(norm["errors"]) or "Amount could not be read."))
    elif amount <= 0:
        flags.append(_reason("non_positive_amount", f"Amount {amount:.2f} is zero or negative."))
    if norm["date"] is None:
        flags.append(_reason("invalid_date", "Date is missing or unreadable."))
    elif dt.date.fromisoformat(norm["date"]) > today:
        flags.append(_reason("future_date", f"Date {norm['date']} is in the future."))
    elif dt.date.fromisoformat(norm["date"]) < months_before(today, config.STALE_MONTHS):
        flags.append(_reason("stale_date", f"Date {norm['date']} is more than {config.STALE_MONTHS} months ago."))

    can_apply_caps = amount is not None and amount > 0 and \
        category not in (None, "unknown") and not any(f["rule"] in ("missing_category", "unknown_category") for f in flags)

    # --- hard rejects ---------------------------------------------------------
    if can_apply_caps:
        if category in config.MEALS and not is_client:
            if norm["is_weekend"]:
                rejects.append(_reason("weekend_meal",
                                       f"{category} on a {norm['weekday']} with no client named."))
            cap = config.MEAL_CAPS[category]
            if amount > cap:
                rejects.append(_reason("meal_over_cap",
                                       f"{category} ${amount:.2f} exceeds the ${cap:.0f} cap (no client named)."))
        if category == "Hotel" and MULTI_NIGHT_RE.search(f"{norm['merchant']} {norm['memo']}"):
            # The cap is per night; a person checks the nightly rate rather than code guessing nights.
            flags.append(_reason("multi_night_hotel", "Hotel stay covers more than one night; the nightly rate needs a check."))
        elif category == "Hotel":
            location = " ".join(filter(None, [signals.get("city"), norm["merchant"], norm["memo"]]))
            tier1 = is_tier1(location)
            cap = config.HOTEL_CAP_TIER1 if tier1 else config.HOTEL_CAP
            if amount > cap:
                rejects.append(_reason("hotel_over_cap",
                                       f"Hotel ${amount:.2f} exceeds the ${cap:.0f} "
                                       f"{'Tier-1' if tier1 else 'standard'} nightly cap."))
        if category == "Entertainment" and not is_client:
            rejects.append(_reason("entertainment_not_client", "Entertainment is only reimbursable with a client."))

    if rejects:
        return "reject", rejects
    if flags:
        return "flag", flags

    # --- needs a human --------------------------------------------------------
    if amount > config.RECEIPT_THRESHOLD and not norm["receipt"]:
        flags.append(_reason("missing_receipt", f"${amount:.2f} is over ${config.RECEIPT_THRESHOLD:.0f} and has no receipt."))
    if category == "Software":
        code = norm["approval_code"]
        if not code:
            flags.append(_reason("missing_approval_code", "Software purchases need an approval code."))
        elif code not in approval_codes:
            flags.append(_reason("unknown_approval_code", f"Approval code {code!r} is not on file."))
    dup = detect_duplicate(norm, history)
    split = None if dup else detect_split(norm, category, is_client, history)
    flags.extend(r for r in (dup, split) if r)
    if amount > config.HIGH_AMOUNT_REVIEW:
        flags.append(_reason("high_amount_review",
                             f"${amount:,.2f} is over the ${config.HIGH_AMOUNT_REVIEW:,.0f} automatic-approval limit."))

    if flags:
        return "flag", flags
    return "approve", [_reason("within_policy", _approve_detail(category, amount, is_client, signals))]


def _active(history, norm):
    """Other expenses that could be paid: not this one, not rejected, with a USD amount and date."""
    for other in history:
        if other.get("id") == norm.get("id") or other.get("status") == "reject":
            continue
        if not other.get("date") or other.get("amount") is None:
            continue
        yield other


def merchant_key(name):
    """'Chipotle #12 ' and 'CHIPOTLE' compare equal: letters only, store numbers dropped."""
    return re.sub(r"[^a-z]", "", (name or "").lower())


def detect_duplicate(norm, history):
    """Same employee (history is per-employee), merchant, date and ~amount (1%) as a live expense."""
    if norm.get("amount") is None or not norm.get("date"):
        return None
    merchant = merchant_key(norm["merchant"])
    for other in _active(history, norm):
        tolerance = max(0.01, 0.01 * max(other["amount"], norm["amount"]))
        if (merchant and merchant_key(other.get("merchant")) == merchant and other["date"] == norm["date"]
                and abs(other["amount"] - norm["amount"]) <= tolerance):
            return _reason("possible_duplicate",
                           f"Looks like a duplicate of {other['id']} (same merchant, date and amount).")
    return None


def detect_split(norm, category, is_client, history):
    """Same employee + merchant + meal category within 1 day, each under cap, combined over."""
    if category not in config.MEALS or is_client or not norm["date"]:
        return None
    cap = config.MEAL_CAPS[category]
    day = dt.date.fromisoformat(norm["date"])
    merchant = norm["merchant"].lower()
    for other in _active(history, norm):
        if (other.get("merchant") or "").lower() != merchant or other.get("category") != category:
            continue
        if other.get("is_client"):
            continue
        if abs((dt.date.fromisoformat(other["date"]) - day).days) > 1:
            continue
        combined = norm["amount"] + other["amount"]
        if norm["amount"] <= cap and other["amount"] <= cap and combined > cap:
            return _reason("possible_split",
                           f"Together with {other['id']} (${other['amount']:.2f}, {other['date']}) at the same merchant, "
                           f"the total ${combined:.2f} exceeds the ${cap:.0f} {category} cap.")
    return None


def _approve_detail(category, amount, is_client, signals):
    if category in config.MEALS or category == "Entertainment":
        if is_client:
            return f"Client {category.lower()} with {signals.get('client_name')}; no cap applies."
        return f"{category} ${amount:.2f} within the ${config.MEAL_CAPS[category]:.0f} cap."
    if category == "Hotel":
        return f"Hotel ${amount:.2f} within the nightly cap."
    return f"{category} is uncapped; receipt/approval requirements met."
