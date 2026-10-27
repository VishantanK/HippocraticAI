"""SQLite persistence. Three tables; decisions and follow-ups are append-only history.

expenses   current state of each expense (raw submitted JSON + normalised view)
decisions  one row per evaluation (revision), exactly what was POSTed + post status
followups  question asked, employee answer, status open|answered|superseded
"""

import datetime as dt
import json
import sqlite3
import threading

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS expenses (
  id TEXT PRIMARY KEY,
  employee TEXT,
  source TEXT NOT NULL,               -- batch | portal
  external_id TEXT,                   -- id from an uploaded file, if any
  raw_json TEXT NOT NULL,             -- latest submitted fields (as received, pre-guard)
  normalized_json TEXT,               -- latest normalised + extracted view
  answers_json TEXT NOT NULL DEFAULT '[]',
  version INTEGER NOT NULL DEFAULT 1,
  status TEXT,                        -- latest decision
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS decisions (
  rowid INTEGER PRIMARY KEY AUTOINCREMENT,
  expense_id TEXT NOT NULL REFERENCES expenses(id),
  revision INTEGER NOT NULL,
  expense_version INTEGER NOT NULL,
  decision TEXT NOT NULL,
  decided_by TEXT NOT NULL,           -- system | human
  payload_json TEXT NOT NULL,         -- exact body POSTed to /decisions
  signals_json TEXT,                  -- guard + LLM extraction, for audit
  post_status TEXT NOT NULL DEFAULT 'pending',  -- pending | sent | failed | dead (see app/outbox.py)
  post_attempts INTEGER NOT NULL DEFAULT 0,
  decided_at TEXT NOT NULL,
  UNIQUE (expense_id, revision)
);
CREATE TABLE IF NOT EXISTS followups (
  rowid INTEGER PRIMARY KEY AUTOINCREMENT,
  expense_id TEXT NOT NULL REFERENCES expenses(id),
  decision_revision INTEGER NOT NULL,
  question TEXT NOT NULL,
  answer TEXT,
  status TEXT NOT NULL DEFAULT 'open',   -- open | answered | superseded
  asked_at TEXT NOT NULL,
  answered_at TEXT
);
"""

# Columns added after v1; applied on connect if missing.
MIGRATIONS = [
    ("decisions", "next_attempt_at", "TEXT"),
    ("decisions", "last_error", "TEXT"),
]

_lock = threading.RLock()
_conn = None


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def conn():
    global _conn
    with _lock:
        if _conn is None:
            _conn = sqlite3.connect(config.DB_PATH, check_same_thread=False)
            _conn.row_factory = sqlite3.Row
            _conn.execute("PRAGMA journal_mode=WAL")
            _conn.executescript(SCHEMA)
            for table, column, ctype in MIGRATIONS:
                cols = {r["name"] for r in _conn.execute(f"PRAGMA table_info({table})")}
                if column not in cols:
                    _conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ctype}")
            _conn.commit()
        return _conn


def reset(path=None):
    """Point the store at a different DB (tests) and re-create schema."""
    global _conn
    with _lock:
        if _conn is not None:
            _conn.close()
        _conn = None
        if path:
            config.DB_PATH = path
        conn()


def _row(r):
    if r is None:
        return None
    d = dict(r)
    for k in list(d):
        if k.endswith("_json") and d[k] is not None:
            d[k[:-5]] = json.loads(d.pop(k))
    return d


def next_portal_id():
    with _lock:
        n = conn().execute("SELECT COUNT(*) FROM expenses WHERE source='portal'").fetchone()[0]
        while get_expense(f"WEB-{n + 1:04d}"):
            n += 1
        return f"WEB-{n + 1:04d}"


def upsert_expense(expense_id, raw, source, external_id=None):
    """Insert or replace the submitted fields; bumps version on change. Returns version."""
    with _lock:
        c = conn()
        existing = c.execute("SELECT version, raw_json FROM expenses WHERE id=?", (expense_id,)).fetchone()
        ts = now()
        if existing is None:
            c.execute(
                "INSERT INTO expenses (id, employee, source, external_id, raw_json, version, created_at, updated_at)"
                " VALUES (?,?,?,?,?,1,?,?)",
                (expense_id, raw.get("employee"), source, external_id, json.dumps(raw), ts, ts))
            c.commit()
            return 1
        version = existing["version"] + (json.loads(existing["raw_json"]) != raw)
        c.execute("UPDATE expenses SET raw_json=?, employee=?, version=?, updated_at=? WHERE id=?",
                  (json.dumps(raw), raw.get("employee"), version, ts, expense_id))
        c.commit()
        return version


def set_normalized(expense_id, normalized, status):
    with _lock:
        conn().execute("UPDATE expenses SET normalized_json=?, status=?, updated_at=? WHERE id=?",
                       (json.dumps(normalized), status, now(), expense_id))
        conn().commit()


def set_status(expense_id, status):
    with _lock:
        conn().execute("UPDATE expenses SET status=?, updated_at=? WHERE id=?", (status, now(), expense_id))
        conn().commit()


def ids_with_status(status):
    with _lock:
        return [r[0] for r in conn().execute("SELECT id FROM expenses WHERE status=?", (status,))]


def add_answer(expense_id, answer):
    with _lock:
        c = conn()
        row = c.execute("SELECT answers_json FROM expenses WHERE id=?", (expense_id,)).fetchone()
        answers = json.loads(row["answers_json"]) + [answer]
        c.execute("UPDATE expenses SET answers_json=?, updated_at=? WHERE id=?",
                  (json.dumps(answers), now(), expense_id))
        c.execute("UPDATE followups SET status='answered', answer=?, answered_at=? WHERE expense_id=? AND status='open'",
                  (answer.get("text") or json.dumps(answer.get("fields")), now(), expense_id))
        c.commit()


def add_decision(expense_id, expense_version, payload, signals, decided_by="system"):
    """Allocate the next revision and insert atomically. Sets payload["revision"]; returns it."""
    with _lock:
        c = conn()
        r = c.execute("SELECT MAX(revision) FROM decisions WHERE expense_id=?", (expense_id,)).fetchone()[0]
        revision = payload["revision"] = (r or 0) + 1
        payload["decision_key"] = f"{expense_id}:{revision}"  # idempotency key for downstream
        c.execute(
            "INSERT INTO decisions (expense_id, revision, expense_version, decision, decided_by, payload_json,"
            " signals_json, decided_at) VALUES (?,?,?,?,?,?,?,?)",
            (expense_id, revision, expense_version, payload["decision"], decided_by,
             json.dumps(payload), json.dumps(signals), payload["decided_at"]))
        # Any still-open question is superseded by a newer decision.
        c.execute("UPDATE followups SET status='superseded' WHERE expense_id=? AND status='open'", (expense_id,))
        if payload.get("question"):
            c.execute("INSERT INTO followups (expense_id, decision_revision, question, asked_at) VALUES (?,?,?,?)",
                      (expense_id, revision, payload["question"], payload["decided_at"]))
        c.commit()
        return revision


def record_post(expense_id, revision, status, error=None, next_attempt_at=None):
    with _lock:
        conn().execute(
            "UPDATE decisions SET post_status=?, post_attempts=post_attempts+1, last_error=?, next_attempt_at=?"
            " WHERE expense_id=? AND revision=?",
            (status, error, next_attempt_at, expense_id, revision))
        conn().commit()


def due_posts(now_iso, limit=50, ignore_backoff=False):
    """Decisions still waiting to be delivered, oldest first."""
    q = ("SELECT expense_id, revision, payload_json, post_attempts FROM decisions"
         " WHERE post_status IN ('pending','failed')")
    args = []
    if not ignore_backoff:
        q += " AND (next_attempt_at IS NULL OR next_attempt_at <= ?)"
        args.append(now_iso)
    q += " ORDER BY rowid LIMIT ?"
    args.append(limit)
    with _lock:
        return [_row(r) for r in conn().execute(q, args)]


def get_expense(expense_id):
    with _lock:
        return _row(conn().execute("SELECT * FROM expenses WHERE id=?", (expense_id,)).fetchone())


def employee_history(employee, exclude_id):
    """Normalised view of the employee's other expenses (for split detection)."""
    with _lock:
        rows = conn().execute(
            "SELECT id, normalized_json, status FROM expenses WHERE employee=? AND id!=? AND normalized_json IS NOT NULL",
            (employee, exclude_id)).fetchall()
    return [dict(json.loads(r["normalized_json"]), id=r["id"], status=r["status"]) for r in rows]


def expense_detail(expense_id):
    e = get_expense(expense_id)
    if not e:
        return None
    with _lock:
        c = conn()
        e["decisions"] = [_row(r) for r in c.execute(
            "SELECT * FROM decisions WHERE expense_id=? ORDER BY revision", (expense_id,))]
        e["followups"] = [dict(r) for r in c.execute(
            "SELECT * FROM followups WHERE expense_id=? ORDER BY rowid", (expense_id,))]
    return e


def list_expenses(source=None, employee=None):
    q = ("SELECT e.*, d.payload_json AS latest_json, d.post_status, d.decided_by FROM expenses e"
         " LEFT JOIN decisions d ON d.expense_id=e.id AND d.revision=(SELECT MAX(revision) FROM decisions WHERE expense_id=e.id)"
         " WHERE 1=1")
    args = []
    if source:
        q += " AND e.source=?"
        args.append(source)
    if employee:
        q += " AND e.employee=?"
        args.append(employee)
    q += " ORDER BY e.updated_at DESC"
    with _lock:
        return [_row(r) for r in conn().execute(q, args)]
