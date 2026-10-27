import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LLM_DISABLED"] = "1"  # unit tests never hit the network
# Fixture dates are fixed, so "today" is too: otherwise the 6-month stale rule would
# start flagging them as the real calendar moves on.
os.environ["EXPENSE_TODAY"] = "2026-10-27"
