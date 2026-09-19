"""Margin CN theo CIF – chỉ CN xem/sửa; HQ không xem margin."""
from threading import Lock
from copy import deepcopy

_lock = Lock()
_PRESETS = {}


def set_preset(customer_id, currency, side, margin, amount_min=0, amount_max=None):
    currency = str(currency).upper()
    side = str(side).upper()
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


def get_preset(customer_id, currency, side, amount=None):
    currency = str(currency).upper()
    side = str(side).upper()
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


def delete_preset(customer_id, currency, side):
    currency = str(currency).upper()
    side = str(side).upper()
    key = (customer_id, currency, side)
    with _lock:
        return _PRESETS.pop(key, None) is not None
