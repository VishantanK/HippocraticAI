"""POST decisions to the downstream endpoint (same helper shape as starter.py)."""

import json
import urllib.request

from . import config


def post_decision(decision):
    """POST one decision dict. Returns True on HTTP 200."""
    body = json.dumps(decision).encode()
    req = urllib.request.Request(config.DECISIONS_ENDPOINT, data=body,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status == 200
    except Exception as e:
        print(f"  POST failed for {decision.get('id')}: {e}")
        return False
