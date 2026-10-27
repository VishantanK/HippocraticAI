"""POST decisions to the downstream endpoint (same helper shape as starter.py).

Retries live in app/outbox.py; this is one attempt."""

import json
import logging
import urllib.request

from . import config

log = logging.getLogger("poster")


def post_decision(decision):
    """POST one decision dict. Returns True on HTTP 200."""
    body = json.dumps(decision).encode()
    headers = {"Content-Type": "application/json"}
    if decision.get("decision_key"):
        headers["Idempotency-Key"] = decision["decision_key"]
    req = urllib.request.Request(config.DECISIONS_ENDPOINT, data=body, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status == 200
    except Exception as e:
        log.warning("POST failed for %s: %s", decision.get("decision_key") or decision.get("id"), e)
        return False
