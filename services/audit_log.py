"""
Audit / Behavior log
- TSC (HQ): thấy toàn bộ log KH + bot + CN
- CN admin: thấy log theo nhân viên chi nhánh
- Staff CN: không xem log tập trung
"""
from threading import Lock
from copy import deepcopy
from typing import Any, Dict, List, Optional
import time

_lock = Lock()
_LOGS: List[Dict[str, Any]] = []


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
        # giữ tối đa 5000 bản ghi demo
        if len(_LOGS) > 5000:
            del _LOGS[: len(_LOGS) - 5000]


def list_logs(
    *,
    role_viewer: str = "HQ",
    branch_id: str = "",
    user_id: str = "",
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """
    HQ: tất cả
    CN_ADMIN: theo branch_id
    PNV: theo user_id của chính mình (hạn chế)
    """
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
