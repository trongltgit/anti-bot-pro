"""
Margin CN đã cài sẵn theo CIF / side / currency (cho KH online).
CN cấu hình một lần; KH online lấy giá theo margin này mà không cần CN quote từng lần.
"""
from threading import Lock
from copy import deepcopy

_lock = Lock()
# key: (customer_id, currency, side) -> margin str
_PRESETS = {}


def set_preset(customer_id: str, currency: str, side: str, margin, amount_min=0, amount_max=None):
    currency = currency.upper()
    side = side.upper()
    key = (customer_id, currency, side)
    with _lock:
        _PRESETS[key] = {
            "margin": str(margin),
            "amount_min": float(amount_min or 0),
            "amount_max": float(amount_max) if amount_max is not None else None,
            "customer_id": customer_id,
            "currency": currency,
            "side": side,
        }
    return deepcopy(_PRESETS[key])


def get_preset(customer_id: str, currency: str, side: str, amount=None):
    currency = currency.upper()
    side = side.upper()
    key = (customer_id, currency, side)
    with _lock:
        p = _PRESETS.get(key)
        if not p:
            return None
        if amount is not None:
            a = float(amount)
            if a < p["amount_min"]:
                return None
            if p["amount_max"] is not None and a > p["amount_max"]:
                return None
        return deepcopy(p)


def list_presets_for_customers(customer_ids):
    ids = set(customer_ids or [])
    with _lock:
        return [deepcopy(v) for k, v in _PRESETS.items() if k[0] in ids]
