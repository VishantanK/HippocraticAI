"""Score the decision logic against labelled data. No storage, no POSTs.

  python eval.py            # live LLM (guard + extraction), the real path
  python eval.py --no-llm   # deterministic-only (shows what fails closed without the LLM)
  python eval.py --suite mock   # only the 100 synthetic failure-mode cases (data/mock_cases.json)

Suites: past, pending, mock (default: all). The mock set also checks the expected rule,
replays follow-up answers, and gives duplicate/split cases their prior expenses.

Hard assertion: zero false approves (system approved, truth was reject/flag).
"""

import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor

# Labels were set as of this date; pin it so the stale/future-date rules don't age the data.
os.environ.setdefault("EXPENSE_TODAY", "2026-10-27")

from app import normalize, pipeline  # noqa: F401 (normalize: used by tests)

LABELS = ("approve", "reject", "flag")
SUITES = ("past", "pending", "mock")


def run(name, expenses, truth, use_llm):
    # Stateless: no history, so split detection is covered by unit tests instead.
    def one(i):
        exp = {k: v for k, v in expenses[i].items() if k != "decision"}
        return pipeline.evaluate(exp, use_llm=use_llm)

    with ThreadPoolExecutor(8) as pool:
        results = list(pool.map(one, range(len(expenses))))
    return report(name, expenses, truth, results)


def report(name, expenses, truth, results):
    matrix = {t: {p: 0 for p in LABELS} for t in LABELS}
    misses, false_approves = [], []
    for exp, res in zip(expenses, results):
        t, p = truth[exp["id"]], res["decision"]
        matrix[t][p] += 1
        if t != p:
            misses.append((exp["id"], t, p, "; ".join(r["detail"] for r in res["reasons"])))
            if p == "approve":
                false_approves.append(exp["id"])

    correct = sum(matrix[l][l] for l in LABELS)
    print(f"\n== {name}: {correct}/{len(expenses)} correct")
    print(f"{'truth \\ pred':14}" + "".join(f"{p:>9}" for p in LABELS))
    for t in LABELS:
        print(f"{t:14}" + "".join(f"{matrix[t][p]:>9}" for p in LABELS))
    for m in misses:
        print(f"  MISS {m[0]} truth={m[1]} got={m[2]}  ({m[3]})")
    return false_approves


def build_history(case):
    """Prior expenses as store.employee_history returns them: normalised, with id and status.
    Priors are normalised offline (exact categories), so history doesn't depend on the LLM."""
    out = []
    for h in case.get("history", []):
        res = pipeline.evaluate(h["expense"], use_llm=False)
        out.append(dict(res["normalized"], id=h["expense"]["id"], status=h["status"]))
    return out


def rule_matches(expected, reasons):
    wanted = {expected} if isinstance(expected, str) else set(expected)
    return bool(wanted & {r["rule"] for r in reasons})


def run_mock(cases, use_llm):
    def one(c):
        return pipeline.evaluate(c["expense"], answers=c.get("answers"), history=build_history(c), use_llm=use_llm)

    with ThreadPoolExecutor(8) as pool:
        results = list(pool.map(one, cases))

    expenses = [c["expense"] for c in cases]
    fa = report("mock (100 synthetic failure modes)", expenses, {c["id"]: c["expected"] for c in cases}, results)

    by_mode = {}
    for c, res in zip(cases, results):
        ok = by_mode.setdefault(c["mode"], [0, 0])
        ok[0] += res["decision"] == c["expected"]
        ok[1] += 1
    print("  by mode: " + ", ".join(f"{m} {a}/{n}" for m, (a, n) in sorted(by_mode.items())))
    for c, res in zip(cases, results):
        if res["decision"] == c["expected"] and not rule_matches(c["expected_rule"], res["reasons"]):
            got = ",".join(r["rule"] for r in res["reasons"])
            print(f"  RULE {c['id']} right decision, expected rule {c['expected_rule']} got {got}  ({c['note']})")
    return fa


def main():
    use_llm = "--no-llm" not in sys.argv
    suites = [sys.argv[sys.argv.index("--suite") + 1]] if "--suite" in sys.argv else SUITES
    fa = []
    if "past" in suites:
        with open("data/past_decisions.json") as f:
            past = json.load(f)
        fa += run("past_decisions (Finance labels)", past, {e["id"]: e["decision"] for e in past}, use_llm)
    if "pending" in suites:
        with open("data/pending_expenses.json") as f:
            pending = json.load(f)
        with open("data/expected_pending.json") as f:
            expected = json.load(f)
        fa += run("pending (gold labels agreed with Finance)", pending, expected, use_llm)
    if "mock" in suites:
        with open("data/mock_cases.json") as f:
            fa += run_mock(json.load(f), use_llm)
    print()
    if fa:
        print(f"FAIL: false approves {fa}")
        sys.exit(1)
    print("OK: zero false approves")


if __name__ == "__main__":
    main()
