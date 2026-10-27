"""FastAPI app: employee portal, Finance dashboard, REST API and SSE.

  uvicorn app.server:app --port 8001

Writes return 202 with status 'checking'; app/jobs.py decides in the background and the
result arrives over SSE (/api/stream). Overrides are quick and stay synchronous.
"""

import asyncio
import csv
import io
import json
import logging
import os
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import config, jobs, outbox, pipeline, store

FRONTEND = os.path.join(config.ROOT, "frontend", "dist")  # built by `npm run build`
UPLOADS = os.path.join(config.ROOT, "uploads")
FIELDS = ("employee", "date", "category", "merchant", "amount", "memo", "receipt", "approval_code")
MAX_UPLOAD_BYTES = 1_000_000
MAX_BATCH = 200

# --- SSE fan-out --------------------------------------------------------------

_subscribers: set[asyncio.Queue] = set()
_loop: asyncio.AbstractEventLoop | None = None


@asynccontextmanager
async def lifespan(_app):
    global _loop
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    _loop = asyncio.get_running_loop()
    store.conn()
    outbox.start()
    jobs.recover()
    yield
    outbox.stop()


app = FastAPI(title="Expense Auto-Approver", lifespan=lifespan)
if os.path.isdir(os.path.join(FRONTEND, "assets")):
    app.mount("/assets", StaticFiles(directory=os.path.join(FRONTEND, "assets")), name="assets")


def _broadcast(event):
    if _loop is None:
        return
    for q in list(_subscribers):
        _loop.call_soon_threadsafe(q.put_nowait, event)


pipeline.on_decision(_broadcast)


@app.get("/api/stream")
async def stream(request: Request):
    q: asyncio.Queue = asyncio.Queue()
    _subscribers.add(q)

    async def gen():
        try:
            yield "retry: 2000\n\n"
            while not await request.is_disconnected():
                try:
                    event = await asyncio.wait_for(q.get(), timeout=15)
                    yield f"data: {json.dumps(event)}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            _subscribers.discard(q)

    return StreamingResponse(gen(), media_type="text/event-stream")


# --- pages (React SPA; the router handles /employee/* and /finance/*) -------------

def _spa():
    index = os.path.join(FRONTEND, "index.html")
    if not os.path.exists(index):
        return HTMLResponse("<p>Frontend not built. Run <code>cd frontend && npm install && npm run build</code>.</p>", 503)
    return FileResponse(index)


@app.get("/", include_in_schema=False)
@app.get("/employee", include_in_schema=False)
@app.get("/employee/{path:path}", include_in_schema=False)
@app.get("/finance", include_in_schema=False)
@app.get("/finance/{path:path}", include_in_schema=False)
def spa(path: str = ""):
    return _spa()


# --- API ----------------------------------------------------------------------

class ExpenseIn(BaseModel):
    employee: str | None = None
    date: str | None = None
    category: str | None = None
    merchant: str | None = None
    amount: float | str | None = None
    memo: str | None = None
    receipt: bool = False
    approval_code: str | None = None


def _raw(data):
    return {k: data.get(k) for k in FIELDS}


def _accept(expense_id, raw=None, external_id=None):
    """Store the change, mark it 'checking', and decide in the background (result over SSE)."""
    with pipeline.expense_lock(expense_id):  # never interleave with a running decision
        if raw is not None:
            store.upsert_expense(expense_id, _raw(raw), "portal", external_id)
        store.set_status(expense_id, "checking")
    jobs.enqueue(expense_id)
    return store.expense_detail(expense_id)


def _submit(raw, external_id=None):
    return _accept(store.next_portal_id(), raw, external_id)


@app.get("/api/stats")
def get_stats():
    return store.stats()


@app.get("/api/policy")
def get_policy():
    """Policy numbers for the form's hints. Guidance only: the server decision is authoritative.
    Approval codes are deliberately left out (publishing them would let anyone use one)."""
    return {
        "version": config.POLICY_VERSION, "today": config.today().isoformat(),
        "categories": config.CATEGORIES, "meal_caps": config.MEAL_CAPS,
        "hotel_cap": config.HOTEL_CAP, "hotel_cap_tier1": config.HOTEL_CAP_TIER1,
        "tier1_cities": list(config.TIER1_CITIES), "receipt_threshold": config.RECEIPT_THRESHOLD,
        "high_amount_review": config.HIGH_AMOUNT_REVIEW, "stale_months": config.STALE_MONTHS,
    }


@app.get("/api/employees")
def get_employees():
    return store.employees()


def _filters(status, manipulation, source, employee, category, date_from, date_to,
             amount_min, amount_max, rule, delivery, q):
    return {"status": status, "manipulation": manipulation, "source": source, "employee": employee,
            "category": category, "date_from": date_from, "date_to": date_to, "amount_min": amount_min,
            "amount_max": amount_max, "rule": rule, "delivery": delivery, "q": q}


@app.get("/api/expenses")
def list_expenses(
    response: Response, status: str | None = None, manipulation: bool = False, source: str | None = None,
    employee: str | None = None, category: str | None = None, date_from: str | None = None,
    date_to: str | None = None, amount_min: float | None = None, amount_max: float | None = None,
    rule: str | None = None, delivery: str | None = None, q: str | None = None,
    sort: str = "updated", dir: str = "desc", limit: int | None = None, offset: int = 0,
):
    """Latest state of each expense. Filters combine; with `limit`, X-Total-Count has the full count."""
    f = _filters(status, manipulation, source, employee, category, date_from, date_to,
                 amount_min, amount_max, rule, delivery, q)
    rows, total = store.query_expenses(f, sort, dir, limit, offset)
    response.headers["X-Total-Count"] = str(total)
    return rows


EXPORT_COLUMNS = ["id", "external_id", "employee", "source", "date", "merchant", "category", "amount",
                  "decision", "decided_by", "rules", "revision", "decided_at", "post_status"]


def _cell(v):
    """Text that a spreadsheet would run as a formula gets a leading quote. Memos and merchants are
    untrusted (and sometimes adversarial by design), so every string cell goes through this."""
    if v is None:
        return ""
    if isinstance(v, str) and v[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + v
    return v


def _export_row(e):
    p, raw = e.get("latest") or {}, e["raw"]
    return [_cell(x) for x in (
        e["id"], e.get("external_id"), e.get("employee"), e["source"], raw.get("date"), raw.get("merchant"),
        p.get("category") or raw.get("category"), p["amount"] if p.get("amount") is not None else raw.get("amount"),
        e.get("status"), e.get("decided_by"), " ".join(r["rule"] for r in p.get("reasons", [])),
        p.get("revision"), p.get("decided_at"), e.get("post_status"))]


# Registered before /api/expenses/{expense_id} so "export.csv" isn't read as an id.
@app.get("/api/expenses/export.csv")
def export_expenses(
    status: str | None = None, manipulation: bool = False, source: str | None = None,
    employee: str | None = None, category: str | None = None, date_from: str | None = None,
    date_to: str | None = None, amount_min: float | None = None, amount_max: float | None = None,
    rule: str | None = None, delivery: str | None = None, q: str | None = None,
    sort: str = "updated", dir: str = "desc",
):
    """The same rows as the filtered list (no paging), latest decision per expense."""
    f = _filters(status, manipulation, source, employee, category, date_from, date_to,
                 amount_min, amount_max, rule, delivery, q)
    rows, _ = store.query_expenses(f, sort, dir)

    def gen():
        buf = io.StringIO()
        w = csv.writer(buf)
        buf.write("\ufeff")  # BOM so Excel reads UTF-8 names correctly
        w.writerow(EXPORT_COLUMNS)
        for e in rows:
            w.writerow(_export_row(e))
            if buf.tell() > 64_000:
                yield buf.getvalue()
                buf.seek(0); buf.truncate()
        yield buf.getvalue()

    name = f"expenses-{store.now()[:10]}.csv"
    return StreamingResponse(gen(), media_type="text/csv; charset=utf-8",
                             headers={"Content-Disposition": f'attachment; filename="{name}"'})


@app.get("/api/expenses/{expense_id}")
def get_expense(expense_id: str):
    e = store.expense_detail(expense_id)
    if not e:
        raise HTTPException(404, "not found")
    return e


@app.post("/api/expenses", status_code=202)
def create_expense(body: ExpenseIn):
    return _submit(body.model_dump())


@app.put("/api/expenses/{expense_id}", status_code=202)
def edit_expense(expense_id: str, body: ExpenseIn):
    e = store.get_expense(expense_id)
    if not e:
        raise HTTPException(404, "not found")
    if e["source"] != "portal":
        raise HTTPException(403, "only portal submissions can be edited")
    return _accept(expense_id, body.model_dump())


def _parse_upload(name, content):
    text = content.decode("utf-8-sig")
    if name.lower().endswith(".csv"):
        rows = list(csv.DictReader(io.StringIO(text)))
        for r in rows:  # CSV is all strings; only literal true counts as a receipt
            r["receipt"] = str(r.get("receipt", "")).strip().lower() == "true"
            r["approval_code"] = r.get("approval_code") or None
        return rows
    data = json.loads(text)
    return data if isinstance(data, list) else [data]


@app.post("/api/expenses/upload", status_code=202)
def upload_expenses(file: UploadFile = File(...), employee: str = Form("")):
    content = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "file too large")
    try:
        rows = _parse_upload(file.filename or "", content)
    except (ValueError, UnicodeDecodeError) as e:
        raise HTTPException(400, f"could not parse file: {e}")
    if len(rows) > MAX_BATCH:
        raise HTTPException(413, f"at most {MAX_BATCH} expenses per upload")
    results = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        if employee.strip() and not row.get("employee"):
            row["employee"] = employee.strip()  # CSVs usually don't name the submitter
        ext = str(row.get("id"))[:40] if row.get("id") else None
        results.append(_submit(row, external_id=ext))
    return results


@app.post("/api/expenses/{expense_id}/answer", status_code=202)
def answer_followup(
    expense_id: str,
    text: str = Form(""),
    approval_code: str = Form(""),
    category: str = Form(""),
    amount: str = Form(""),
    merchant: str = Form(""),
    receipt_file: UploadFile | None = File(None),
):
    e = store.expense_detail(expense_id)
    if not e:
        raise HTTPException(404, "not found")
    if not any(f["status"] == "open" for f in e["followups"]):
        raise HTTPException(409, "no open question for this expense")
    fields = {"approval_code": approval_code.strip() or None, "category": category.strip() or None,
              "amount": amount.strip() or None, "merchant": merchant.strip() or None}
    if receipt_file is not None and receipt_file.filename:
        content = receipt_file.file.read(5_000_000)
        os.makedirs(UPLOADS, exist_ok=True)
        ext = os.path.splitext(receipt_file.filename)[1][:8]
        path = os.path.join(UPLOADS, f"{expense_id}-{uuid.uuid4().hex[:8]}{ext}")
        with open(path, "wb") as f:
            f.write(content)
        fields["receipt"] = True
        fields["receipt_file"] = os.path.basename(path)
    fields = {k: v for k, v in fields.items() if v is not None}
    if not text.strip() and not fields:
        raise HTTPException(400, "empty answer")
    store.add_answer(expense_id, {"text": text.strip(), "fields": fields, "at": store.now()})
    return _accept(expense_id)


class OverrideIn(BaseModel):
    decision: str
    note: str = ""
    expected_revision: int | None = None  # the revision the reviewer saw; the UI always sends it


@app.post("/api/expenses/{expense_id}/override")
def override(expense_id: str, body: OverrideIn):
    try:
        pipeline.human_override(expense_id, body.decision, body.note, expected_revision=body.expected_revision)
    except KeyError:
        raise HTTPException(404, "not found")
    except pipeline.Stale as e:
        raise HTTPException(409, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))
    return store.expense_detail(expense_id)
