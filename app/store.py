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
  post_status TEXT NOT NULL DEFAULT 'pending',  -- pending|sending|sent|failed|dead|superseded (app/outbox.py)
  post_attempts INTEGER NOT NULL DEFAULT 0,
  decided_at TEXT NOT NULL,
  UNIQUE (expense_id, revision)
);
CREATE TABLE IF NOT EXISTS idempotency (
  key TEXT PRIMARY KEY,               -- "<endpoint scope>:<client Idempotency-Key>"
  expense_ids TEXT NOT NULL,          -- JSON list: what the first request created or changed
  created_at TEXT NOT NULL
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

# Indexes for Finance's filtered list (idempotent; applied on connect).
INDEXES = """
CREATE INDEX IF NOT EXISTS idx_expenses_employee ON expenses(employee, updated_at);
CREATE INDEX IF NOT EXISTS idx_expenses_status ON expenses(status, updated_at);
CREATE INDEX IF NOT EXISTS idx_decisions_post ON decisions(post_status);
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
            _conn.executescript(INDEXES)
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


def add_portal_expenses(rows):
    """Insert several new portal expenses in one transaction, already 'checking'.
    rows: [(raw, external_id)]. Returns their ids. On any error nothing is stored."""
    with _lock:
        c = conn()
        ids, ts = [], now()
        try:
            for raw, external_id in rows:
                eid = next_portal_id()  # sees this transaction's own inserts
                c.execute(
                    "INSERT INTO expenses (id, employee, source, external_id, raw_json, version, status, created_at, updated_at)"
                    " VALUES (?,?,?,?,?,1,'checking',?,?)",
                    (eid, raw.get("employee"), "portal", external_id, json.dumps(raw), ts, ts))
                ids.append(eid)
            c.commit()
        except Exception:
            c.rollback()
            raise
        return ids


def idempotent_ids(key):
    with _lock:
        r = conn().execute("SELECT expense_ids FROM idempotency WHERE key=?", (key,)).fetchone()
        return json.loads(r[0]) if r else None


def remember_idempotent(key, expense_ids):
    with _lock:
        conn().execute("INSERT OR IGNORE INTO idempotency (key, expense_ids, created_at) VALUES (?,?,?)",
                       (key, json.dumps(expense_ids), now()))
        conn().commit()


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
        # Older undelivered revisions must never arrive after this one; downstream wants the latest.
        c.execute("UPDATE decisions SET post_status='superseded' WHERE expense_id=? AND revision<?"
                  " AND post_status IN ('pending','failed')", (expense_id, revision))
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


def claim_post(expense_id, revision):
    """Atomically take a deliverable row (so the inline attempt and the outbox worker never
    both send it). Only the latest revision of an expense is deliverable. Returns
    {"payload", "attempts"} or None if someone else has it / it's done / it's superseded."""
    with _lock:
        c = conn()
        cur = c.execute(
            "UPDATE decisions SET post_status='sending' WHERE expense_id=? AND revision=?"
            " AND post_status IN ('pending','failed')"
            " AND revision=(SELECT MAX(revision) FROM decisions d2 WHERE d2.expense_id=decisions.expense_id)",
            (expense_id, revision))
        c.commit()
        if cur.rowcount != 1:
            return None
        r = c.execute("SELECT payload_json, post_attempts FROM decisions WHERE expense_id=? AND revision=?",
                      (expense_id, revision)).fetchone()
        return {"payload": json.loads(r["payload_json"]), "attempts": r["post_attempts"]}


def delivery_problems():
    """Latest decisions that haven't reached downstream ('failed' = retrying, 'dead' = gave up)."""
    with _lock:
        return [_row(r) for r in conn().execute(
            "SELECT d.expense_id, d.revision, d.decision, d.decided_by, d.decided_at, d.post_status,"
            " d.post_attempts, d.last_error, d.next_attempt_at, e.employee FROM decisions d"
            " JOIN expenses e ON e.id=d.expense_id WHERE d.post_status IN ('failed','dead')"
            " AND d.revision=(SELECT MAX(revision) FROM decisions WHERE expense_id=d.expense_id)"
            " ORDER BY d.post_status='dead' DESC, d.rowid")]


def revive_post(expense_id, revision=None):
    """Make dead rows deliverable again (latest revision only); revision=None revives all of them."""
    q = ("UPDATE decisions SET post_status='failed', next_attempt_at=NULL WHERE post_status='dead'"
         " AND revision=(SELECT MAX(revision) FROM decisions d2 WHERE d2.expense_id=decisions.expense_id)")
    args = []
    if revision is not None:
        q += " AND expense_id=? AND revision=?"
        args = [expense_id, revision]
    with _lock:
        n = conn().execute(q, args).rowcount
        conn().commit()
        return n


def post_status(expense_id, revision):
    with _lock:
        r = conn().execute("SELECT post_status FROM decisions WHERE expense_id=? AND revision=?",
                           (expense_id, revision)).fetchone()
        return r[0] if r else None


def reset_stale_sending():
    """Rows left 'sending' by a crashed process go back to the retry queue."""
    with _lock:
        conn().execute("UPDATE decisions SET post_status='failed', next_attempt_at=NULL WHERE post_status='sending'")
        conn().commit()


def latest_decision(expense_id):
    with _lock:
        return _row(conn().execute(
            "SELECT * FROM decisions WHERE expense_id=? ORDER BY revision DESC LIMIT 1", (expense_id,)).fetchone())


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


_LATEST = ("SELECT e.*, d.payload_json AS latest_json, d.post_status, d.decided_by FROM expenses e"
           " LEFT JOIN decisions d ON d.expense_id=e.id"
           " AND d.revision=(SELECT MAX(revision) FROM decisions WHERE expense_id=e.id)")
_DATE = "COALESCE(json_extract(e.normalized_json,'$.date'), json_extract(e.raw_json,'$.date'))"
_AMOUNT = "json_extract(d.payload_json,'$.amount')"
# Whitelisted sort columns: the key comes from the query string, so it is never interpolated.
SORTS = {"updated": "e.updated_at", "date": _DATE, "amount": _AMOUNT, "employee": "LOWER(e.employee)"}
MAX_PAGE = 500


def _like(text):
    return "%" + text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def query_expenses(f, sort="updated", direction="desc", limit=None, offset=0):
    """Filtered, sorted page of expenses with their latest decision. Returns (rows, total).

    f keys (all optional): status (approve|reject|flag|checking|error), manipulation, source,
    employee, category, date_from, date_to, amount_min, amount_max, rule, delivery ("problem"), q.
    """
    where, args = [], []
    status = f.get("status")
    if status == "checking":
        where.append("(e.status IS NULL OR e.status='checking')")
    elif status:
        where.append("e.status=?"); args.append(status)
    if f.get("manipulation"):
        where.append("json_extract(d.payload_json,'$.suspected_manipulation')=1")
    for key in ("source", "employee"):
        if f.get(key):
            where.append(f"e.{key}=?"); args.append(f[key])
    if f.get("category"):
        where.append("LOWER(COALESCE(json_extract(d.payload_json,'$.category'), json_extract(e.raw_json,'$.category')))=LOWER(?)")
        args.append(f["category"])
    if f.get("date_from"):
        where.append(f"{_DATE}>=?"); args.append(f["date_from"])
    if f.get("date_to"):
        where.append(f"{_DATE}<=?"); args.append(f["date_to"])
    if f.get("amount_min") is not None:
        where.append(f"{_AMOUNT}>=?"); args.append(float(f["amount_min"]))
    if f.get("amount_max") is not None:
        where.append(f"{_AMOUNT}<=?"); args.append(float(f["amount_max"]))
    if f.get("rule"):
        where.append("EXISTS (SELECT 1 FROM json_each(d.payload_json,'$.reasons') WHERE json_extract(value,'$.rule')=?)")
        args.append(f["rule"])
    if f.get("delivery") == "problem":
        where.append("d.post_status IN ('failed','dead')")
    if f.get("q"):
        where.append("(e.id || ' ' || COALESCE(e.external_id,'') || ' ' || COALESCE(e.employee,'') || ' '"
                     " || COALESCE(json_extract(e.raw_json,'$.merchant'),'') || ' '"
                     " || COALESCE(json_extract(e.raw_json,'$.category'),'')) LIKE ? ESCAPE '\\'")
        args.append(_like(f["q"].strip()))
    q = _LATEST + (" WHERE " + " AND ".join(where) if where else "")
    order = SORTS.get(sort, SORTS["updated"])
    sql_dir = "ASC" if direction == "asc" else "DESC"
    page = q + f" ORDER BY {order} IS NULL, {order} {sql_dir}, e.id {sql_dir}"
    page_args = list(args)
    if limit is not None:
        page += " LIMIT ? OFFSET ?"
        page_args += [max(1, min(int(limit), MAX_PAGE)), max(0, int(offset))]
    with _lock:
        c = conn()
        rows = [_row(r) for r in c.execute(page, page_args)]
        total = c.execute(f"SELECT COUNT(*) FROM ({q})", args).fetchone()[0] if limit is not None else len(rows)
    return rows, total


def list_expenses(source=None, employee=None):
    return query_expenses({"source": source, "employee": employee})[0]


def employees():
    with _lock:
        return [r[0] for r in conn().execute(
            "SELECT DISTINCT employee FROM expenses WHERE employee IS NOT NULL AND employee != '' ORDER BY employee")]


def stats():
    """Aggregates for the Finance overview. Amounts (always USD) from the latest decision only."""
    with _lock:
        c = conn()
        latest = [(r["source"], r["status"], json.loads(r["payload_json"]) if r["payload_json"] else {})
                  for r in c.execute(
                      "SELECT e.source, e.status, d.payload_json FROM expenses e LEFT JOIN decisions d"
                      " ON d.expense_id=e.id AND d.revision=(SELECT MAX(revision) FROM decisions WHERE expense_id=e.id)")]
        post = {k: 0 for k in ("pending", "sent", "failed", "dead")}
        post.update({r[0]: r[1] for r in c.execute("SELECT post_status, COUNT(*) FROM decisions GROUP BY post_status")})
        # An old revision that failed doesn't matter once a newer one exists: count the latest only.
        post.update({"failed": 0, "dead": 0})
        post.update({r[0]: r[1] for r in c.execute(
            "SELECT post_status, COUNT(*) FROM decisions d WHERE post_status IN ('failed','dead')"
            " AND revision=(SELECT MAX(revision) FROM decisions WHERE expense_id=d.expense_id) GROUP BY post_status")})
        open_q = c.execute("SELECT COUNT(*) FROM followups WHERE status='open'").fetchone()[0]
        answered = c.execute(
            "SELECT COUNT(DISTINCT f.expense_id) FROM followups f JOIN expenses e ON e.id=f.expense_id"
            " WHERE f.status='answered' AND e.status='flag'").fetchone()[0]
        recent = [dict(r) for r in c.execute(
            "SELECT d.expense_id, d.revision, d.decision, d.decided_by, d.decided_at, e.employee"
            " FROM decisions d JOIN expenses e ON e.id=d.expense_id ORDER BY d.rowid DESC LIMIT 15")]
    by_status, by_source, by_cat = {"approve": 0, "reject": 0, "flag": 0}, {}, {}
    for source, status, p in latest:
        by_status[status or "checking"] = by_status.get(status or "checking", 0) + 1
        by_source[source] = by_source.get(source, 0) + 1
        if p.get("category") and p.get("amount") is not None:
            row = by_cat.setdefault(p["category"], {"category": p["category"], "approve": 0.0, "reject": 0.0, "flag": 0.0})
            if p.get("decision") in row:
                row[p["decision"]] += p["amount"]
    return {
        "total": len(latest), "by_status": by_status, "by_source": by_source,
        "manipulation": sum(1 for _, _, p in latest if p.get("suspected_manipulation")),
        "open_questions": open_q, "answered_awaiting_review": answered, "post": post,
        "by_category": sorted(by_cat.values(), key=lambda r: -(r["approve"] + r["reject"] + r["flag"])),
        "recent": recent,
    }
