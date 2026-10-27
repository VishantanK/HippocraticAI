"""Starter scaffold for the expense auto-approver.

This is a leg-up, not a solution: data loading, a POST helper, and a stubbed LLM
call are wired so you can spend your time on the interesting parts. Replace the
TODOs. You are free to restructure or ignore this entirely.

  python starter.py
"""

import json
import os
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ENDPOINT = "http://localhost:8000/decisions"


# --- ingest -----------------------------------------------------------------

def load(name):
    with open(os.path.join(HERE, "data", name)) as f:
        return json.load(f)


# --- integration ------------------------------------------------------------

def post_decision(decision):
    """POST one decision (a dict) to the mock endpoint. Returns True on success."""
    body = json.dumps(decision).encode()
    req = urllib.request.Request(ENDPOINT, data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status == 200
    except Exception as e:
        print(f"  POST failed for {decision.get('id')}: {e}")
        return False


# --- LLM (stub) -------------------------------------------------------------

def call_llm(expense):
    """TODO: use the LLM to parse / judge the expense.

    A good pattern is to have the model EXTRACT structured signals from the messy
    fields (canonical category, numeric amount, whether a client is named, whether
    alcohol is involved, ...) and then apply the policy in plain Python. Consider
    structured outputs so you always get parseable JSON back.

    Use whichever major LLM you like (bring your own API key) — e.g. the `anthropic`,
    `openai`, or `google-generativeai` SDK. Prefer your provider's structured-output / JSON
    mode so you always get parseable output back.
    """
    raise NotImplementedError


def generate_question(expense, reason):
    """TODO: draft a short, specific question to the submitter for an expense that
    can't be auto-decided (missing receipt, needs an approval code, foreign currency,
    unclear category, ...). Aim it at the actual gap — don't ask for everything.
    Return the question text; the caller attaches it to the flagged decision.
    """
    raise NotImplementedError


# --- decide -----------------------------------------------------------------

def decide(expense):
    """TODO: return a decision dict for one expense.

    Decide approve / reject / flag. What fields should a decision carry so Finance
    (and your own eval) can trust it? What is the policy? (Ask the customer.)

    When the decision is "flag", attach a clarifying question for the submitter on
    the same object (e.g. a "question" field) — decisions and their questions go to
    the one /decisions endpoint together.
    """
    return {
        "id": expense["id"],
        "decision": "flag",           # approve | reject | flag
        "question": None,             # fill in when decision == "flag"
        # TODO: add other fields here if needed
    }


# --- run --------------------------------------------------------------------

def main():
    pending = load("pending_expenses.json")
    print(f"processing {len(pending)} expenses -> {ENDPOINT}\n")
    for expense in pending:
        decision = decide(expense)
        # TODO: if decision["decision"] == "flag", set decision["question"] =
        #       generate_question(expense, decision["reason"]) before POSTing.
        post_decision(decision)
    print("\ndone. (this scaffold flags everything — that's your job to fix)")


if __name__ == "__main__":
    main()
