"""LLM calls. The model extracts facts and writes questions; it never decides.

Every call uses structured output (JSON schema). Expense text is wrapped in tags
and declared untrusted in the system prompt. Any failure raises LLMError, and the
pipeline fails closed (flag).
"""

import functools
import json
import os

import anthropic
import openai

from . import config

PROMPTS = os.path.join(os.path.dirname(__file__), "prompts")


class LLMError(Exception):
    pass


@functools.cache
def _prompt(name):
    with open(os.path.join(PROMPTS, f"{name}.md")) as f:
        return f.read()


@functools.cache
def _openai():
    return openai.OpenAI(timeout=config.LLM_TIMEOUT_S, max_retries=2)


@functools.cache
def _client():
    return anthropic.Anthropic(timeout=config.LLM_TIMEOUT_S, max_retries=2)


def _call_json(model, system, user, schema, max_tokens=2000):
    if config.LLM_DISABLED:
        raise LLMError("LLM disabled")
    try:
        resp = _client().beta.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_config={"effort": "low", "format": {"type": "json_schema", "schema": schema}},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
    except anthropic.APIError as e:
        raise LLMError(f"{e.__class__.__name__}: {e}") from e
    if resp.stop_reason in ("refusal", "max_tokens"):
        raise LLMError(f"stop_reason={resp.stop_reason}")
    text = next((b.text for b in resp.content if b.type == "text"), None)
    if text is None:
        raise LLMError("no text block in response")
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise LLMError(f"invalid JSON: {e}") from e


def _wrap(tag, obj):
    return f"<{tag}>\n{json.dumps(obj, ensure_ascii=False, indent=1)}\n</{tag}>"


GUARD_SCHEMA = {
    "type": "object",
    "properties": {
        "injection": {"type": "boolean"},
        "field": {"type": "string"},
        "evidence": {"type": "string"},
    },
    "required": ["injection", "field", "evidence"],
    "additionalProperties": False,
}


def classify_injection_claude(fields):
    out = _call_json(config.GUARD_FALLBACK_MODEL, _prompt("guard"), _wrap("fields", fields), GUARD_SCHEMA, 1500)
    return dict(out, probability=1.0 if out["injection"] else 0.0, detector="claude")


def classify_injection_decisions(fields):
    """OpenAI Decisions API: a calibrated probability instead of a free-form verdict."""
    if config.LLM_DISABLED:
        raise LLMError("LLM disabled")
    names = list(fields)
    try:
        resp = _openai().decisions.create(
            model=config.GUARD_DECISIONS_MODEL,
            input=_wrap("fields", fields),
            questions=[
                {"type": "predicate", "name": "manipulation", "instructions": _prompt("guard_decisions")},
                # No "none" option: the answer is only used when the predicate is high, and
                # offering "none" made it fail to point at text it had just scored 1.00.
                {"type": "choice", "name": "field",
                 "instructions": "Which field's text is most aimed at influencing the approval decision or the reviewer?",
                 "choices": [{"value": n, "description": f"the {n} field"} for n in names]},
            ],
        )
    except openai.OpenAIError as e:
        raise LLMError(f"{e.__class__.__name__}: {e}") from e
    answers = {a.name: a for a in resp.answers}
    pred = answers.get("manipulation")
    if pred is None or pred.type != "predicate":  # refusal or missing -> can't trust
        raise LLMError("decisions: no predicate answer")
    field = answers.get("field")
    field = field.choice if field is not None and field.type == "choice" else "unknown"
    p = float(pred.probability)
    return {"injection": p >= config.GUARD_REVIEW_THRESHOLD, "probability": p, "field": field,
            "evidence": (fields.get(field) or "") if field in fields else "", "detector": "openai_decisions"}


def classify_injection(fields):
    """Primary: Decisions API. Fallback: Claude screen. Both down -> LLMError (guard fails closed)."""
    try:
        return classify_injection_decisions(fields)
    except LLMError as primary:
        try:
            return dict(classify_injection_claude(fields), primary_error=str(primary))
        except LLMError as fallback:
            raise LLMError(f"decisions: {primary}; claude: {fallback}") from fallback


EXTRACT_SCHEMA = {
    "type": "object",
    "properties": {
        "category": {"type": "string", "enum": config.CATEGORIES + ["unknown"]},
        "category_confidence": {"type": "number"},
        "is_client": {"type": "boolean"},
        "client_name": {"type": "string"},
        "city": {"type": "string"},
    },
    "required": ["category", "category_confidence", "is_client", "client_name", "city"],
    "additionalProperties": False,
}

_EXTRACT_FIELDS = ("category", "merchant", "memo", "date", "followup_answers")


def extract(expense):
    payload = {k: expense.get(k) for k in _EXTRACT_FIELDS}
    out = _call_json(config.LLM_MODEL, _prompt("extract"), _wrap("expense", payload), EXTRACT_SCHEMA)
    if out["category"] not in config.CATEGORIES + ["unknown"]:
        out["category"] = "unknown"
    return out


QUESTION_SCHEMA = {
    "type": "object",
    "properties": {"question": {"type": "string"}},
    "required": ["question"],
    "additionalProperties": False,
}

_QUESTION_FIELDS = ("employee", "date", "category", "merchant", "amount", "memo", "receipt", "approval_code")


def generate_question(expense, reasons):
    payload = {k: expense.get(k) for k in _QUESTION_FIELDS}
    gaps = [{"gap": r["rule"], "detail": r["detail"]} for r in reasons]
    user = _wrap("expense", payload) + "\n" + _wrap("gaps", gaps)
    return _call_json(config.LLM_MODEL, _prompt("question"), user, QUESTION_SCHEMA)["question"].strip()
