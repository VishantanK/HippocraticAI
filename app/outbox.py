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


def _attempt(expense_id, revision, now=None):
    """Claim the row, make one delivery attempt, record the outcome. Returns True if sent."""
    claim = store.claim_post(expense_id, revision)
    if claim is None:  # already sent, superseded, or another thread is sending it
        return False
    payload, attempts_so_far = claim["payload"], claim["attempts"]
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


def deliver(expense_id, revision, payload=None):
    """First attempt, made right after the decision is stored (payload is read from the row)."""
    return _attempt(expense_id, revision)


def run_due(now=None, ignore_backoff=False):
    """Retry everything that is due. Returns the number sent."""
    now = now or _utcnow()
    sent = 0
    for row in store.due_posts(now.isoformat(timespec="seconds"), ignore_backoff=ignore_backoff):
        sent += _attempt(row["expense_id"], row["revision"], now)
    return sent


def flush():
    """One immediate pass over every undelivered decision (e.g. at the end of a batch)."""
    before = len(store.due_posts("", limit=10_000, ignore_backoff=True))
    sent = run_due(ignore_backoff=True)
    return {"sent": sent, "failed": before - sent}


def retry(expense_id, revision):
    """Finance's "Retry now": one immediate attempt, ignoring backoff. A dead row gets just this
    attempt (it goes straight back to dead if it fails). Only the latest revision is retried.
    Returns the resulting post_status, or None if there was nothing to retry."""
    store.revive_post(expense_id, revision)  # no-op unless it is the latest revision and dead
    if store.post_status(expense_id, revision) not in ("pending", "failed"):
        return None  # sent, superseded, still dead (an older revision), or unknown
    _attempt(expense_id, revision)  # claims atomically, so the worker can't send it twice
    return store.post_status(expense_id, revision)


def retry_all():
    """Revive every dead latest decision and try all undelivered ones now."""
    store.revive_post(None)
    return flush()


def _loop():
    while not _stop.wait(POLL_S):
        try:
            run_due()
        except Exception:
            log.exception("outbox pass failed")


def start():
    global _thread
    if _thread is None or not _thread.is_alive():
        store.reset_stale_sending()
        _stop.clear()
        _thread = threading.Thread(target=_loop, name="outbox", daemon=True)
        _thread.start()


def stop():
    _stop.set()
