"""The one decision path shared by the batch run and the portal.

  guard -> normalize -> extract (LLM) -> policy (pure) -> question (LLM, flags only)
        -> store -> POST -> notify listeners (SSE)
"""

from . import config, guard, llm, normalize, policy, poster, store

_listeners = []  # callables(event: dict); the web server registers one for SSE


def on_decision(fn):
    _listeners.append(fn)


def _notify(event):
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
        merged.update({k: v for k, v in (a.get("fields") or {}).items() if v not in (None, "")})
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
    raw = dict(raw, id=expense_id)
    version = store.upsert_expense(expense_id, raw, source, external_id)
    current = store.get_expense(expense_id)
    history = store.employee_history(raw.get("employee"), expense_id) if raw.get("employee") else []

    result = evaluate(raw, answers=current["answers"], history=history, use_llm=use_llm)
    question, question_source = None, None
    if result["decision"] == "flag":
        question, question_source = build_question(raw, result["reasons"], use_llm)

    norm = result["normalized"]
    revision = store.next_revision(expense_id)
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
        "revision": revision,
        "source": source,
        "decided_by": "system",
        "policy_version": config.POLICY_VERSION,
        "prompt_version": config.PROMPT_VERSION,
        "decided_at": store.now(),
    }
    signals = dict(result["signals"], question_source=question_source)
    store.add_decision(expense_id, revision, version, payload, signals)
    store.set_normalized(expense_id, norm, result["decision"])
    store.mark_posted(expense_id, revision, poster.post_decision(payload))
    _notify({"type": "decision", "expense_id": expense_id, "payload": payload})
    return payload


def human_override(expense_id, decision, note, reviewer="finance"):
    """Finance reviewer resolves an expense. Recorded and POSTed like any decision."""
    if decision not in ("approve", "reject"):
        raise ValueError("decision must be approve or reject")
    e = store.get_expense(expense_id)
    if not e:
        raise KeyError(expense_id)
    revision = store.next_revision(expense_id)
    payload = {
        "id": expense_id, "employee": e["employee"], "decision": decision,
        "reasons": [{"rule": "human_review", "detail": note or f"Decided by {reviewer}."}],
        "question": None, "revision": revision, "source": e["source"], "decided_by": "human",
        "reviewer": reviewer, "policy_version": config.POLICY_VERSION, "decided_at": store.now(),
    }
    store.add_decision(expense_id, revision, e["version"], payload, {}, decided_by="human")
    store.set_normalized(expense_id, e.get("normalized") or {}, decision)
    store.mark_posted(expense_id, revision, poster.post_decision(payload))
    _notify({"type": "decision", "expense_id": expense_id, "payload": payload})
    return payload
