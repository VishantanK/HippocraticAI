"""Every submitted version of an expense is kept (append-only), so Finance can see what changed."""

from app import store

RAW = {"employee": "Mei Lin", "date": "2026-06-19", "category": "Dinner", "merchant": "Nobu", "amount": 72}


def test_each_change_is_a_new_version(tmp_path):
    store.reset(str(tmp_path / "v.db"))
    store.upsert_expense("V-1", RAW, "portal")
    store.upsert_expense("V-1", RAW, "portal")                          # unchanged: no new version
    store.upsert_expense("V-1", dict(RAW, memo="with Acme Corp"), "portal")
    versions = store.expense_detail("V-1")["versions"]
    assert [v["version"] for v in versions] == [1, 2]
    assert "memo" not in versions[0]["raw"] and versions[1]["raw"]["memo"] == "with Acme Corp"


def test_batch_inserts_record_version_one(tmp_path):
    store.reset(str(tmp_path / "v.db"))
    [eid] = store.add_portal_expenses([(RAW, None)])
    assert [v["version"] for v in store.expense_detail(eid)["versions"]] == [1]


def test_existing_databases_are_backfilled_with_the_current_version(tmp_path):
    path = str(tmp_path / "v.db")
    store.reset(path)
    store.upsert_expense("V-1", RAW, "portal")
    store.upsert_expense("V-1", dict(RAW, amount=50), "portal")
    store.conn().execute("DELETE FROM expense_versions")                # as if created before this table
    store.conn().commit()
    store.reset(path)
    versions = store.expense_detail("V-1")["versions"]
    assert [(v["version"], v["raw"]["amount"]) for v in versions] == [(2, 50)]
