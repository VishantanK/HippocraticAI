"""The one decision path shared by the batch run and the portal.

  guard -> normalize -> extract (LLM) -> policy (pure) -> question (LLM, flags only)
        -> store -> POST -> notify listeners (SSE)
"""

import threading

from . import config, guard, llm, normalize, outbox, policy, poster, store  # noqa: F401 (poster: test seam)

_listeners = []  # callables(event: dict); the web server registers one for SSE

# One lock per expense: edits, answers and overrides on the same expense run one at a time,
# so each evaluation sees the previous one's state and revisions stay ordered.
_locks: dict[str, threading.RLock] = {}
_locks_guard = threading.Lock()


def expense_lock(expense_id):
    with _locks_guard:
        return _locks.setdefault(expense_id, threading.RLock())


# Expenses from the same employee are evaluated one at a time, so duplicate and split
# checks always see each other (two identical rows in one upload can't both pass).
# Lock order is always expense -> employee.
_employee_locks: dict[str, threading.Lock] = {}


def employee_lock(employee):
    with _locks_guard:
        return _employee_locks.setdefault((employee or "").strip().lower(), threading.Lock())


def on_decision(fn):
    _listeners.append(fn)


def notify(event):
    for fn in _listeners:
        try:
            fn(event)
        except Exception as e:
            print(f"listener error: {e}")


def _exact_category(raw):
    """Deterministic mapping wins over the LLM when the text is an exact match."""
    t = (raw or "").strip().lower()
    for c in config.CATEGORIES:
        if t == c.lower():
            return c
    if t in ("uber", "lyft", "taxi", "cab", "rideshare", "ground transport"):
        return "GroundTransport"
    return None


def _effective_memo(expense, answers):
    texts = [a["text"] for a in answers or [] if a.get("text")]
    memo = expense.get("memo") or ""
    return " | ".join([memo] + [f"Employee follow-up: {t}" for t in texts]).strip(" |")


def evaluate(raw, answers=None, history=(), use_llm=True, extract_fn=None, guard_fn=None):
    """Classify one expense. No side effects. Returns a result dict with
    decision, reasons, normalised view, and audit signals.

    answers: follow-up answers [{text, fields}]; structured fields are merged in,
    free text is guarded and appended to the memo for extraction.
    """
    merged = dict(raw)
    for a in answers or []:
        merged.update({k: v for k, v in (a.get("fields") or {}).items()
                       if k in guard.ALLOWED_FIELDS and v not in (None, "")})
    answer_text = {f"answer_{i + 1}": a["text"] for i, a in enumerate(answers or []) if a.get("text")}

    # 1. input guard ---------------------------------------------------------
    classifier = guard_fn if guard_fn is not None else (llm.classify_injection if use_llm else None)
    g = guard.run_guard(merged, extra_text=answer_text, llm_classifier=classifier)
    clean = g["clean"]
    signals = {"guard": {k: g[k] for k in ("schema_issues", "manipulation", "guard_error", "screen")}}
    base = {"id": raw.get("id"), "employee": clean.get("employee")}

    if g["manipulation"]:
        hit = g["manipulation"][0]
        prob = f" (p={hit['probability']:.2f}, {hit['detector']})" if hit.get("probability") is not None else f" ({hit['detector']})"
        reasons = [{"rule": "suspected_manipulation",
                    "detail": f"Text in '{hit['field']}' attempts to influence the reviewer{prob}: \"{hit['evidence']}\""}]
        norm = normalize.normalize(clean)
        return dict(base, decision="reject", reasons=reasons, normalized=norm, signals=signals,
                    suspected_manipulation=True)

    # 2. normalise -------------------------------------------------------------
    norm = normalize.normalize(clean)
    norm.update(id=raw.get("id"), employee=clean.get("employee"))

    # 3. extract ---------------------------------------------------------------
    exact = _exact_category(norm["category_raw"])
    llm_error = None
    try:
        if not use_llm and extract_fn is None:
            raise llm.LLMError("LLM disabled")
        ex = (extract_fn or llm.extract)(dict(clean, memo=_effective_memo(clean, answers)))
    except llm.LLMError as e:
        llm_error = str(e)
        ex = {"category": exact or "unknown", "category_confidence": 1.0 if exact else 0.0,
              "is_client": False, "client_name": "", "city": "", "injection_suspected": False}
    if exact:  # never let the model re-map an exact category
        ex["category"], ex["category_confidence"] = exact, 1.0
    if not norm["category_raw"]:
        ex["category"] = "unknown"
    signals["extract"] = ex
    if llm_error:
        signals["llm_error"] = llm_error

    norm["category"] = ex["category"] if ex["category"] != "unknown" else None
    norm["category_mapped_from"] = norm["category_raw"] if norm["category"] and not exact else None
    norm["is_client"] = bool(ex["is_client"] and ex["client_name"].strip())
    norm["client_name"] = ex["client_name"] if norm["is_client"] else ""

    if ex.get("injection_suspected"):
        reasons = [{"rule": "suspected_manipulation",
                    "detail": "The extraction model detected text addressed to the reviewer."}]
        return dict(base, decision="reject", reasons=reasons, normalized=norm, signals=signals,
                    suspected_manipulation=True)

    # 4. policy ----------------------------------------------------------------
    decision, reasons = policy.evaluate(norm, ex, history)

    # A follow-up answer may correct data, but it can't talk its way out of a duplicate:
    # the original submission is checked too, so only Finance can clear it.
    if answers and decision == "approve":
        original, _ = guard.check_schema(raw)
        orig_norm = dict(normalize.normalize(original), id=raw.get("id"))
        dup = policy.detect_duplicate(orig_norm, history)
        if dup:
            decision, reasons = "flag", [dup]

    # 5. fail closed: without full checks nothing is decided automatically ----
    if llm_error or g["guard_error"]:
        decision = "flag"
        reasons = [{"rule": "llm_unavailable" if llm_error else "guard_unavailable",
                    "detail": "Automated checks could not complete; a human must review."}] + \
                  [r for r in reasons if r["rule"] != "within_policy"]

    return dict(base, decision=decision, reasons=reasons, normalized=norm, signals=signals,
                suspected_manipulation=False)


def _template_question(raw, reasons):
    name = (raw.get("employee") or "there").split()[0]
    asks = {
        "missing_receipt": "upload the itemized receipt",
        "missing_approval_code": "reply with your software approval code (format SW-####)",
        "unknown_approval_code": "double-check the approval code; the one provided isn't on file",
        "missing_category": "tell us which category this is (Breakfast, Lunch, Dinner, Hotel, Office, Software, Ground transport, Airfare, Entertainment)",
        "unknown_category": "tell us what was purchased and which category applies",
        "missing_merchant": "tell us the merchant name",
        "non_usd": "tell us the amount in USD as charged to your card",
        "invalid_amount": "confirm the amount",
        "non_positive_amount": "confirm the amount",
        "invalid_date": "confirm the date of the expense",
        "possible_split": "confirm whether these charges were one meal, how many attended, and whether a client was present",
        "possible_duplicate": "confirm whether this is a separate purchase or a duplicate of an expense you already submitted",
        "edited_after_review": "note that Finance will review your changes",
        "check_failed": "note that Finance will review this expense",
        "high_amount_review": "attach the itemized receipt and a short business justification for this amount",
        "future_date": "confirm the date of the expense",
    }
    items = [asks[r["rule"]] for r in reasons if r["rule"] in asks]
    what = f"{raw.get('merchant') or 'your expense'} on {raw.get('date')} ({raw.get('amount')})"
    if not items:
        return f"Hi {name}, Finance is reviewing {what} and will be in touch if anything else is needed."
    return f"Hi {name}, before we can process {what}, could you please " + "; and ".join(items) + "?"


def build_question(raw, reasons, use_llm=True):
    if use_llm:
        try:
            return llm.generate_question(raw, reasons), "llm"
        except llm.LLMError:
            pass
    return _template_question(raw, reasons), "template"


def process(raw, source, expense_id=None, external_id=None, use_llm=True):
    """Full side-effecting path: store -> evaluate -> question -> store decision -> POST -> notify."""
    expense_id = expense_id or raw.get("id")
    with expense_lock(expense_id):
        store.upsert_expense(expense_id, dict(raw, id=expense_id), source, external_id)
        payload = _decide_locked(expense_id, use_llm)
    # Deliver outside the lock: a slow endpoint must not block the next edit.
    outbox.deliver(expense_id, payload["revision"])
    return payload


def process_stored(expense_id, use_llm=True):
    """Re-evaluate an expense from its latest stored state (background jobs).
    Returns None when there is nothing new to decide since Finance's decision."""
    with expense_lock(expense_id):
        if not store.get_expense(expense_id):
            raise KeyError(expense_id)
        payload = _decide_locked(expense_id, use_llm)
    if payload:
        outbox.deliver(expense_id, payload["revision"])
    return payload


def _decide_locked(expense_id, use_llm):
    """Caller holds expense_lock. Reads the stored state once; decides on exactly that."""
    current = store.get_expense(expense_id)
    raw, version, source = current["raw"], current["version"], current["source"]
    last = store.latest_decision(expense_id)
    reviewed = last is not None and last["decided_by"] == "human"
    if reviewed and last["expense_version"] == version:
        # Finance already decided this exact version (e.g. a job queued before the override).
        store.set_status(expense_id, last["decision"])
        notify({"type": "decision", "expense_id": expense_id, "payload": last["payload"]})
        return None

    notify({"type": "processing", "expense_id": expense_id})
    with employee_lock(raw.get("employee") or expense_id):
        history = store.employee_history(raw.get("employee"), expense_id) if raw.get("employee") else []
        result = evaluate(raw, answers=current["answers"], history=history, use_llm=use_llm)
        if reviewed and result["decision"] == "approve":
            # Edited after Finance reviewed it: a human must look again.
            result["decision"] = "flag"
            result["reasons"] = [{"rule": "edited_after_review",
                                  "detail": f"Changed after Finance {last['decision']}ed it; needs another review."}]
        return _record_locked(expense_id, raw, version, source, result, use_llm)


def _record_locked(expense_id, raw, version, source, result, use_llm):
    question, question_source = None, None
    if result["decision"] == "flag":
        question, question_source = build_question(raw, result["reasons"], use_llm)

    norm = result["normalized"]
    payload = {
        "id": expense_id,
        "employee": raw.get("employee"),
        "decision": result["decision"],
        "reasons": result["reasons"],
        "question": question,
        "amount": norm.get("amount"),
        "currency": norm.get("currency"),
        "category": norm.get("category"),
        "category_mapped_from": norm.get("category_mapped_from"),
        "client": norm.get("client_name") or None,
        "suspected_manipulation": result["suspected_manipulation"],
        "revision": None,  # allocated atomically by store.add_decision
        "source": source,
        "decided_by": "system",
        "policy_version": config.POLICY_VERSION,
        "prompt_version": config.PROMPT_VERSION,
        "decided_at": store.now(),
    }
    signals = dict(result["signals"], question_source=question_source)
    store.add_decision(expense_id, version, payload, signals)
    store.set_normalized(expense_id, norm, result["decision"])
    notify({"type": "decision", "expense_id": expense_id, "payload": payload})
    return payload


def record_failure(expense_id, error):
    """A job crashed (a bug, not an LLM outage): fail closed with a stored, POSTed flag."""
    with expense_lock(expense_id):
        e = store.get_expense(expense_id)
        result = {"decision": "flag", "suspected_manipulation": False, "signals": {"job_error": error},
                  "normalized": e.get("normalized") or {},
                  "reasons": [{"rule": "check_failed", "detail": "The automated check hit an internal error; Finance will review."}]}
        payload = _record_locked(expense_id, e["raw"], e["version"], e["source"], result, use_llm=False)
    outbox.deliver(expense_id, payload["revision"])
    return payload


def human_override(expense_id, decision, note, reviewer="finance"):
    """Finance reviewer resolves an expense. Recorded and POSTed like any decision."""
    if decision not in ("approve", "reject"):
        raise ValueError("decision must be approve or reject")
    with expense_lock(expense_id):
        e = store.get_expense(expense_id)
        if not e:
            raise KeyError(expense_id)
        payload = {
            "id": expense_id, "employee": e["employee"], "decision": decision,
            "reasons": [{"rule": "human_review", "detail": note or f"Decided by {reviewer}."}],
            "question": None, "revision": None, "source": e["source"], "decided_by": "human",
            "reviewer": reviewer, "policy_version": config.POLICY_VERSION, "decided_at": store.now(),
        }
        revision = store.add_decision(expense_id, e["version"], payload, {}, decided_by="human")
        store.set_normalized(expense_id, e.get("normalized") or {}, decision)
    outbox.deliver(expense_id, revision)
    notify({"type": "decision", "expense_id": expense_id, "payload": payload})
    return payload
