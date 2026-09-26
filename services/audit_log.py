"""
Audit / Behavior log – TSC thấy hết; CN_ADMIN theo branch.
"""
from threading import Lock
from copy import deepcopy
from typing import Any, Dict, List, Optional
import time
import csv
import io

_lock = Lock()
_LOGS: List[Dict[str, Any]] = []

# KH same-param quote cooldown: key=(user_id, currency, side, amount_key) -> last_ts
_QUOTE_COOLDOWN: Dict[tuple, int] = {}
# CN interrupt: customer_id -> version (tăng mỗi khi đổi margin/NSDH)
_CIF_QUOTE_VERSION: Dict[str, int] = {}


def add_log(
    event: str,
    *,
    user_id: str = "",
    role: str = "",
    customer_id: str = "",
    branch_id: str = "",
    detail: Optional[Dict] = None,
    ip: str = "",
    level: str = "info",
) -> None:
    entry = {
        "ts": int(time.time()),
        "event": event,
        "user_id": user_id or "",
        "role": (role or "").upper(),
        "customer_id": customer_id or "",
        "branch_id": branch_id or "",
        "ip": ip or "",
        "level": level,
        "detail": detail or {},
    }
    with _lock:
        _LOGS.append(entry)
        if len(_LOGS) > 8000:
            del _LOGS[: len(_LOGS) - 8000]


def list_logs(
    *,
    role_viewer: str = "HQ",
    branch_id: str = "",
    user_id: str = "",
    limit: int = 200,
) -> List[Dict[str, Any]]:
    role_viewer = (role_viewer or "").upper()
    with _lock:
        items = list(_LOGS)
    if role_viewer == "HQ":
        selected = items
    elif role_viewer == "CN_ADMIN" and branch_id:
        selected = [x for x in items if x.get("branch_id") == branch_id]
    elif role_viewer in {"PNV", "STAFF", "BRANCH"} and user_id:
        selected = [x for x in items if x.get("user_id") == user_id]
    else:
        selected = []
    return [deepcopy(x) for x in selected[-limit:]]


def count_recent_quotes(user_id: str, window_seconds: int = 60) -> int:
    cutoff = int(time.time()) - window_seconds
    with _lock:
        return sum(
            1
            for x in _LOGS
            if x.get("user_id") == user_id
            and x.get("event") == "quote_request"
            and x.get("ts", 0) >= cutoff
        )


def check_same_param_cooldown(
    user_id: str, currency: str, side: str, amount: float, cooldown_seconds: int = 60
) -> Optional[int]:
    """
    Trả về số giây còn lại nếu KH hỏi cùng ccy+side+amount trong cooldown.
    None = được phép hỏi.
    """
    key = (user_id, currency.upper(), side.upper(), round(float(amount), 2))
    now = int(time.time())
    with _lock:
        last = _QUOTE_COOLDOWN.get(key)
        if last is not None and now - last < cooldown_seconds:
            return cooldown_seconds - (now - last)
        _QUOTE_COOLDOWN[key] = now
        # dọn key cũ
        stale = [k for k, t in _QUOTE_COOLDOWN.items() if now - t > 600]
        for k in stale:
            _QUOTE_COOLDOWN.pop(k, None)
    return None


def bump_cif_quote_version(customer_id: str) -> int:
    """CN đổi margin/NSDH → tăng version → quote cũ hết hiệu lực."""
    with _lock:
        v = _CIF_QUOTE_VERSION.get(customer_id, 0) + 1
        _CIF_QUOTE_VERSION[customer_id] = v
        return v


def get_cif_quote_version(customer_id: str) -> int:
    with _lock:
        return _CIF_QUOTE_VERSION.get(customer_id, 0)


def logs_to_csv(logs: List[Dict]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["ts", "event", "level", "user_id", "role", "customer_id", "branch_id", "ip", "detail"])
    for x in logs:
        writer.writerow([
            x.get("ts"), x.get("event"), x.get("level"), x.get("user_id"),
            x.get("role"), x.get("customer_id"), x.get("branch_id"), x.get("ip"),
            str(x.get("detail") or {}),
        ])
    return buf.getvalue()
