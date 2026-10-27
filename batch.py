"""Process a batch file end to end: decide, draft questions, store, POST.

  python batch.py [data/pending_expenses.json] [--no-llm]
"""

import json
import sys
from collections import Counter

from app import pipeline


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    path = args[0] if args else "data/pending_expenses.json"
    use_llm = "--no-llm" not in sys.argv
    with open(path) as f:
        expenses = json.load(f)
    print(f"processing {len(expenses)} expenses from {path}\n")
    counts = Counter()
    # Sequential on purpose: split detection reads earlier expenses from the store.
    for exp in expenses:
        exp = {k: v for k, v in exp.items() if k != "decision"}  # never trust a label in the input
        d = pipeline.process(exp, source="batch", use_llm=use_llm)
        counts[d["decision"]] += 1
        why = "; ".join(r["detail"] for r in d["reasons"])
        print(f"{d['id']:9} {d['decision']:8} {why}")
        if d["question"]:
            print(f"{'':18} Q: {d['question']}")
    print(f"\n{dict(counts)}")


if __name__ == "__main__":
    main()
