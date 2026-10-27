"""Score the decision logic against labelled data. No storage, no POSTs.

  python eval.py            # live LLM (guard + extraction), the real path
  python eval.py --no-llm   # deterministic-only (shows what fails closed without the LLM)

Hard assertion: zero false approves (system approved, truth was reject/flag).
"""

import json
import sys
from concurrent.futures import ThreadPoolExecutor

from app import pipeline

LABELS = ("approve", "reject", "flag")


def run(name, expenses, truth, use_llm):
    # Stateless: no history, so split detection is covered by unit tests instead.
    def one(i):
        exp = {k: v for k, v in expenses[i].items() if k != "decision"}
        return pipeline.evaluate(exp, use_llm=use_llm)

    with ThreadPoolExecutor(8) as pool:
        results = list(pool.map(one, range(len(expenses))))

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


def main():
    use_llm = "--no-llm" not in sys.argv
    with open("data/past_decisions.json") as f:
        past = json.load(f)
    with open("data/pending_expenses.json") as f:
        pending = json.load(f)
    with open("data/expected_pending.json") as f:
        expected = json.load(f)

    fa = run("past_decisions (Finance labels)", past, {e["id"]: e["decision"] for e in past}, use_llm)
    fa += run("pending (gold labels agreed with Finance)", pending, expected, use_llm)
    print()
    if fa:
        print(f"FAIL: false approves {fa}")
        sys.exit(1)
    print("OK: zero false approves")


if __name__ == "__main__":
    main()
