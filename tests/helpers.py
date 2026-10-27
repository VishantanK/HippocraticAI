def expense(**kw):
    base = {"id": "T-1", "employee": "Dana Ng", "date": "2026-06-15", "category": "Lunch",
            "merchant": "Cava", "amount": 20.0, "memo": "", "receipt": True, "approval_code": None}
    base.update(kw)
    return base


def extractor(category=None, is_client=False, client_name="", city=""):
    """Stub for llm.extract: echo the category (or a forced one) with the given signals."""
    def fn(e):
        return {"category": category or (e.get("category") or "unknown").title(),
                "category_confidence": 0.95, "is_client": is_client, "client_name": client_name,
                "city": city}
    return fn


def clean_screen(fields):
    return {"injection": False, "probability": 0.0, "field": "none", "evidence": "", "detector": "stub"}
