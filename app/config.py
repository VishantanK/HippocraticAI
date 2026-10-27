"""Central configuration: policy tables, model ids, endpoints."""

import json
import os

from dotenv import load_dotenv

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(ROOT, ".env"))

POLICY_VERSION = "2026-10-27.1"
PROMPT_VERSION = "v1"

DECISIONS_ENDPOINT = os.getenv("DECISIONS_ENDPOINT", "http://localhost:8000/decisions")
DB_PATH = os.getenv("EXPENSE_DB", os.path.join(ROOT, "expenses.db"))

LLM_MODEL = os.getenv("LLM_MODEL", "claude-haiku-5-5")  # extraction + question drafting
# Guard screen: OpenAI Decisions API (probability), Claude screen as fallback.
GUARD_DECISIONS_MODEL = os.getenv("GUARD_DECISIONS_MODEL", "gpt-6-luna")
GUARD_FALLBACK_MODEL = os.getenv("GUARD_FALLBACK_MODEL", LLM_MODEL)
# Reject when P(manipulation) >= threshold. Low on purpose: a missed manipulation is
# worse than a false reject (which a human can override). Calibrated in tests/eval.
GUARD_THRESHOLD = float(os.getenv("GUARD_THRESHOLD", "0.5"))
LLM_TIMEOUT_S = float(os.getenv("LLM_TIMEOUT_S", "30"))
LLM_DISABLED = os.getenv("LLM_DISABLED") == "1"  # tests / offline: forces fail-closed paths

# --- policy tables ----------------------------------------------------------

CATEGORIES = [
    "Breakfast", "Lunch", "Dinner", "Hotel", "Office", "Software",
    "GroundTransport", "Airfare", "Entertainment",
]
MEALS = {"Breakfast", "Lunch", "Dinner"}
MEAL_CAPS = {"Breakfast": 20.0, "Lunch": 30.0, "Dinner": 60.0}
UNCAPPED = {"Office", "Software", "GroundTransport", "Airfare"}

HOTEL_CAP = 200.0
HOTEL_CAP_TIER1 = 350.0
TIER1_CITIES = {
    "new york": ["new york", "nyc", "manhattan", "brooklyn"],
    "san francisco": ["san francisco", " sf ", "sfo"],
    "boston": ["boston"],
    "los angeles": ["los angeles", " la ", "lax"],
    "seattle": ["seattle"],
    "chicago": ["chicago"],
    "washington dc": ["washington dc", "washington, dc", "washington d.c", " dc "],
    "london": ["london"],
}

RECEIPT_THRESHOLD = 25.0


def load_approval_codes():
    with open(os.path.join(ROOT, "data", "approval_codes.json")) as f:
        return json.load(f)
