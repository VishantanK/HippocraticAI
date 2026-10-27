"""Background decision jobs for the portal.

Endpoints store the change, mark the expense 'checking', and enqueue its id; a worker
runs the full pipeline and the result arrives over SSE. The queue is keyed by expense
id: while an id is queued, more enqueues are no-ops; while it runs, one re-run is
scheduled. Rapid edits therefore coalesce, and the worker always evaluates the latest
stored state.
"""

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from . import pipeline, store

log = logging.getLogger("jobs")

_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="decide")
_guard = threading.Lock()
_queued: set[str] = set()
_running: set[str] = set()
_rerun: set[str] = set()
_idle = threading.Condition(_guard)


def enqueue(expense_id):
    with _guard:
        if expense_id in _queued:
            return
        if expense_id in _running:
            _rerun.add(expense_id)
            return
        _queued.add(expense_id)
    pipeline.notify({"type": "queued", "expense_id": expense_id})
    _executor.submit(_run, expense_id)


def _run(expense_id):
    with _guard:
        _queued.discard(expense_id)
        _running.add(expense_id)
    started = time.monotonic()
    try:
        payload = pipeline.process_stored(expense_id)
        if payload:
            log.info("decided %s rev %s -> %s in %.1fs", expense_id, payload["revision"],
                     payload["decision"], time.monotonic() - started)
    except Exception as e:
        # A bug, not an LLM outage (those fail closed inside the pipeline): record a
        # fail-closed flag so it is stored, POSTed and in Finance's queue.
        log.exception("decision job failed for %s", expense_id)
        try:
            pipeline.record_failure(expense_id, f"{e.__class__.__name__}: {e}")
        except Exception:
            log.exception("could not record failure for %s", expense_id)
            store.set_status(expense_id, "error")
            pipeline.notify({"type": "error", "expense_id": expense_id})
    finally:
        with _guard:
            _running.discard(expense_id)
            again = expense_id in _rerun
            _rerun.discard(expense_id)
            _idle.notify_all()
        if again:
            enqueue(expense_id)


def recover():
    """Re-enqueue anything left 'checking' or 'error' by a previous process (crash/restart)."""
    ids = store.ids_with_status("checking") + store.ids_with_status("error")
    for expense_id in ids:
        enqueue(expense_id)
    return ids


def wait_idle(timeout=30):
    """Block until no job is queued or running (tests, scripts)."""
    deadline = time.monotonic() + timeout
    with _guard:
        while _queued or _running or _rerun:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return False
            _idle.wait(remaining)
    return True
