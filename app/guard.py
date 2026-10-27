"""Input guard: the first stage of the pipeline.

Runs before normalisation or extraction. Three jobs:
  1. schema: keep only known fields, enforce types and length limits
  2. sanitize: Unicode NFKC, strip zero-width / control chars, fold common homoglyphs
  3. detect manipulation: an LLM screen is the primary detector (OpenAI Decisions API
     probability, Claude screen as fallback; see llm.classify_injection); a handful of
     regex patterns are a deterministic backstop

Anything that looks like an instruction to the reviewer is a manipulation attempt
and the expense is rejected (Finance policy: reject outright).
"""

import re
import unicodedata

ALLOWED_FIELDS = {
    "id": str, "employee": str, "date": str, "category": str, "merchant": str,
    "amount": (int, float, str), "memo": str, "receipt": bool, "approval_code": str,
}
MAX_LEN = {"id": 40, "employee": 80, "date": 20, "category": 40, "merchant": 120,
           "amount": 30, "memo": 500, "approval_code": 30, "answer": 1000}
TEXT_FIELDS = ("employee", "category", "merchant", "memo", "approval_code")

ZERO_WIDTH = re.compile(r"[​-‏‪-‮⁠-⁤﻿]")
CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
# Cyrillic/Greek letters that render like Latin; folded so regexes can't be dodged.
HOMOGLYPHS = str.maketrans({
    "а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "у": "y", "х": "x", "і": "i",
    "А": "A", "Е": "E", "О": "O", "Р": "P", "С": "C", "Т": "T", "Х": "X", "І": "I",
    "ο": "o", "α": "a", "ε": "e", "ι": "i", "Ο": "O",
})

# Backstop only. The LLM screen is the primary detector; these few
# high-precision patterns still fire if that call is down or itself gets talked round.
BACKSTOP_PATTERNS = [
    r"\b(auto|automatically)[\s-]*approve",
    r"\bpre[\s-]*approved\b",
    r"\bnote\s+to\s+(the\s+)?(reviewer|approver|ai|model|system|assistant)\b",
    r"\bignore\b.{0,40}\b(previous|prior|rules?|limits?|polic(y|ies)|instructions?|caps?)\b",
]
_BACKSTOP_RE = [re.compile(p, re.IGNORECASE | re.DOTALL) for p in BACKSTOP_PATTERNS]


def sanitize_text(s):
    s = unicodedata.normalize("NFKC", s)
    s = ZERO_WIDTH.sub("", s)
    s = CONTROL.sub(" ", s)
    return s.translate(HOMOGLYPHS)


def _squash(s):
    """Lower-case and drop separators so 'a.u.t.o-a p p r o v e' still matches."""
    return re.sub(r"[^a-z]", "", s.lower())


def regex_scan(text):
    """Return the first matching evidence string, or None."""
    for rx in _BACKSTOP_RE:
        m = rx.search(text)
        if m:
            return m.group(0)
    squashed = _squash(text)  # catches 'a.u.t.o-a p p r o v e' style spacing tricks
    for needle in ("autoapprove", "preapproved", "notetoreviewer"):
        if needle in squashed:
            return needle
    return None


def check_schema(expense):
    """Return (clean_expense, issues). Unknown keys are dropped and reported."""
    if not isinstance(expense, dict):
        return {}, ["expense is not an object"]
    clean, issues = {}, []
    for key, value in expense.items():
        if key not in ALLOWED_FIELDS:
            issues.append(f"dropped unexpected field {key!r}")
            continue
        if value is None:
            clean[key] = None
            continue
        if not isinstance(value, ALLOWED_FIELDS[key]) or (key != "receipt" and isinstance(value, bool)):
            issues.append(f"field {key!r} has wrong type")
            clean[key] = None
            continue
        if isinstance(value, str):
            value = sanitize_text(value)
            limit = MAX_LEN.get(key)
            if limit and len(value) > limit:
                issues.append(f"field {key!r} exceeds {limit} chars")
                value = value[:limit]
        clean[key] = value
    return clean, issues


def scan_fields(fields):
    """fields: {name: text}. Return list of {field, evidence} hits from the regex layer."""
    hits = []
    for name, text in fields.items():
        if isinstance(text, str) and text:
            ev = regex_scan(text)
            if ev:
                hits.append({"field": name, "evidence": ev, "detector": "regex"})
    return hits


def run_guard(expense, extra_text=None, llm_classifier=None):
    """Full guard. Returns dict:
        {clean, schema_issues, manipulation: [hits], guard_error: str|None}

    extra_text: additional untrusted text to scan (e.g. follow-up answers).
    llm_classifier: callable(fields) -> {"injection", "probability", "field", "evidence", "detector"}
    """
    clean, schema_issues = check_schema(expense)
    fields = {k: clean.get(k) for k in TEXT_FIELDS}
    for k, v in (extra_text or {}).items():
        fields[k] = sanitize_text(v)[: MAX_LEN["answer"]] if isinstance(v, str) else v
    guard_error, screen = None, None
    hits = []
    if llm_classifier is not None:
        try:
            res = llm_classifier({k: v for k, v in fields.items() if v})
            screen = {k: res.get(k) for k in ("detector", "probability", "field", "primary_error")}
            if res.get("injection"):
                hits.append({"field": res.get("field") or "unknown", "evidence": res.get("evidence") or "",
                             "detector": res.get("detector", "llm"), "probability": res.get("probability")})
        except Exception as e:  # fail closed: caller turns this into a flag
            guard_error = f"guard classifier unavailable: {e}"
    if not hits:
        hits = scan_fields(fields)
    return {"clean": clean, "schema_issues": schema_issues, "manipulation": hits,
            "guard_error": guard_error, "screen": screen}
