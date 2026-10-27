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

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import config, jobs, outbox, pipeline, store

STATIC = os.path.join(config.ROOT, "static")
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
app.mount("/static", StaticFiles(directory=STATIC), name="static")


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


# --- pages --------------------------------------------------------------------

@app.get("/")
def employee_page():
    return FileResponse(os.path.join(STATIC, "employee.html"))


@app.get("/finance")
def finance_page():
    return FileResponse(os.path.join(STATIC, "finance.html"))


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
    if raw is not None:
        store.upsert_expense(expense_id, _raw(raw), "portal", external_id)
    store.set_status(expense_id, "checking")
    jobs.enqueue(expense_id)
    return store.expense_detail(expense_id)


def _submit(raw, external_id=None):
    return _accept(store.next_portal_id(), raw, external_id)


@app.get("/api/expenses")
def list_expenses(source: str | None = None, employee: str | None = None):
    return store.list_expenses(source, employee)


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
def upload_expenses(file: UploadFile = File(...)):
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


@app.post("/api/expenses/{expense_id}/override")
def override(expense_id: str, body: OverrideIn):
    try:
        pipeline.human_override(expense_id, body.decision, body.note)
    except KeyError:
        raise HTTPException(404, "not found")
    except ValueError as e:
        raise HTTPException(400, str(e))
    return store.expense_detail(expense_id)
