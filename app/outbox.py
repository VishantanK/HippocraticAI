"""Reliable delivery of decisions to the downstream endpoint.

Every decision row starts as post_status='pending'. deliver() tries once right after
the decision is stored; failures get exponential backoff and the background worker
retries them. After MAX_ATTEMPTS a row is 'dead' (shown on the Finance dashboard).
Each attempt carries the same Idempotency-Key ({id}:{revision}).
"""

import datetime as dt
import logging
import threading

from . import poster, store

log = logging.getLogger("outbox")

MAX_ATTEMPTS = 8
BASE_DELAY_S = 5
MAX_DELAY_S = 300
POLL_S = 2

_stop = threading.Event()
_thread = None


def _utcnow():
    return dt.datetime.now(dt.timezone.utc)


def _attempt(expense_id, revision, payload, attempts_so_far, now=None):
    """One delivery attempt; records the outcome. Returns True if sent."""
    try:
        ok = poster.post_decision(payload)
        error = None if ok else "POST did not return 200"
    except Exception as e:  # poster shouldn't raise, but never let the worker die
        ok, error = False, f"{e.__class__.__name__}: {e}"
    attempts = attempts_so_far + 1
    if ok:
        store.record_post(expense_id, revision, "sent")
    elif attempts >= MAX_ATTEMPTS:
        store.record_post(expense_id, revision, "dead", error)
        log.error("giving up on %s:%s after %d attempts: %s", expense_id, revision, attempts, error)
    else:
        delay = min(BASE_DELAY_S * 2 ** (attempts - 1), MAX_DELAY_S)
        retry_at = ((now or _utcnow()) + dt.timedelta(seconds=delay)).isoformat(timespec="seconds")
        store.record_post(expense_id, revision, "failed", error, retry_at)
        log.warning("POST %s:%s failed (attempt %d), retry at %s", expense_id, revision, attempts, retry_at)
    return ok


def deliver(expense_id, revision, payload):
    """First attempt, made right after the decision is stored."""
    return _attempt(expense_id, revision, payload, 0)


def run_due(now=None, ignore_backoff=False):
    """Retry everything that is due. Returns the number sent."""
    now = now or _utcnow()
    sent = 0
    for row in store.due_posts(now.isoformat(timespec="seconds"), ignore_backoff=ignore_backoff):
        sent += _attempt(row["expense_id"], row["revision"], row["payload"], row["post_attempts"], now)
    return sent


def flush():
    """One immediate pass over every undelivered decision (e.g. at the end of a batch)."""
    before = len(store.due_posts("", limit=10_000, ignore_backoff=True))
    sent = run_due(ignore_backoff=True)
    return {"sent": sent, "failed": before - sent}


def _loop():
    while not _stop.wait(POLL_S):
        try:
            run_due()
        except Exception:
            log.exception("outbox pass failed")


def start():
    global _thread
    if _thread is None or not _thread.is_alive():
        _stop.clear()
        _thread = threading.Thread(target=_loop, name="outbox", daemon=True)
        _thread.start()


def stop():
    _stop.set()
