"""
Security utilities – Fingerprint, HMAC, UA, Nonce, IP
"""

import hashlib
import hmac
import time
import os
from collections import OrderedDict
from threading import Lock

from flask import request, session


_nonce_store = OrderedDict()
_nonce_lock = Lock()
_NONCE_MAX_SIZE = 10000
_NONCE_TTL = 120


def get_client_ip():
    if request.headers.get("CF-Connecting-IP"):
        return request.headers.get("CF-Connecting-IP")
    if request.headers.get("X-Forwarded-For"):
        return request.headers.get("X-Forwarded-For").split(",")[0].strip()
    return request.remote_addr or "unknown"


def get_client_fingerprint():
    """
    Fingerprint ổn định hơn trên proxy/CDN (Render).
    Chỉ dùng các header ít thay đổi giữa các request cùng trình duyệt.
    """
    components = [
        request.headers.get("User-Agent", ""),
        request.headers.get("Accept-Language", ""),
        request.headers.get("Sec-CH-UA-Platform", ""),
    ]
    raw = "|".join(components)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def bind_fingerprint():
    """Gắn / làm mới fingerprint vào session (gọi sau login, trước API)."""
    fp = get_client_fingerprint()
    session["fingerprint"] = fp
    session.modified = True
    return fp


def verify_fingerprint(strict: bool = False) -> bool:
    """
    Kiểm tra fingerprint.
    - Nếu chưa có trong session: gắn mới và cho qua (lần đầu).
    - Nếu đã login (có user_id) và lệch nhẹ: làm mới (tránh false positive trên Render).
    - strict=True: bắt buộc khớp (dùng khi cần cứng).
    """
    current = get_client_fingerprint()
    stored = session.get("fingerprint")

    if not stored:
        session["fingerprint"] = current
        session.modified = True
        return True

    if hmac.compare_digest(current, stored):
        return True

    # Đã đăng nhập: re-bind thay vì chặn cứng (demo / proxy header thay đổi)
    if session.get("user_id") and not strict:
        session["fingerprint"] = current
        session.modified = True
        return True

    if strict:
        return False

    # Chưa login + mismatch: gắn lại
    session["fingerprint"] = current
    session.modified = True
    return True


def is_suspicious_user_agent():
    ua = (request.headers.get("User-Agent") or "").lower()
    bad_keywords = [
        "bot", "crawl", "spider", "slurp", "scrapy", "httpclient",
        "python-requests", "curl", "wget", "httpx", "aiohttp",
        "go-http", "java/", "phantomjs", "headless", "selenium",
        "puppeteer", "playwright",
    ]
    return any(k in ua for k in bad_keywords)


def generate_request_signature(timestamp: str, secret: str = None) -> str:
    if secret is None:
        secret = os.environ.get(
            "API_SIGNING_SECRET",
            "default-signing-secret-change-me",
        )
    message = f"{timestamp}:{get_client_ip()}:{session.get('fingerprint', '')}"
    return hmac.new(
        secret.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def generate_pricing_signature(
    timestamp: str,
    method: str,
    path: str,
    body: str,
    nonce: str = "",
    secret: str = None,
) -> str:
    if secret is None:
        secret = os.environ.get(
            "API_SIGNING_SECRET",
            "default-signing-secret-change-me",
        )
    body_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()
    message = (
        f"{timestamp}:"
        f"{method.upper()}:"
        f"{path}:"
        f"{body_hash}:"
        f"{get_client_ip()}:"
        f"{session.get('fingerprint', '')}:"
        f"{nonce}"
    )
    return hmac.new(
        secret.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def verify_request_signature(
    timestamp: str,
    signature: str,
    max_age_seconds: int = 60,
) -> bool:
    try:
        ts = int(timestamp)
    except (ValueError, TypeError):
        return False
    now = int(time.time())
    if abs(now - ts) > max_age_seconds:
        return False
    expected = generate_request_signature(timestamp)
    return hmac.compare_digest(expected, signature)


def verify_pricing_signature(
    timestamp: str,
    signature: str,
    method: str,
    path: str,
    body: str,
    nonce: str = "",
    max_age_seconds: int = 60,
) -> bool:
    try:
        ts = int(timestamp)
    except (ValueError, TypeError):
        return False
    now = int(time.time())
    if abs(now - ts) > max_age_seconds:
        return False
    if nonce:
        if not _check_and_store_nonce(nonce, ts):
            return False
    expected = generate_pricing_signature(
        timestamp=timestamp,
        method=method,
        path=path,
        body=body,
        nonce=nonce,
    )
    return hmac.compare_digest(expected, signature)


def _check_and_store_nonce(nonce: str, ts: int) -> bool:
    if not nonce or len(nonce) < 8 or len(nonce) > 64:
        return False
    now = int(time.time())
    with _nonce_lock:
        expired = [k for k, v in _nonce_store.items() if now - v > _NONCE_TTL]
        for k in expired:
            _nonce_store.pop(k, None)
        if nonce in _nonce_store:
            return False
        _nonce_store[nonce] = ts
        while len(_nonce_store) > _NONCE_MAX_SIZE:
            _nonce_store.popitem(last=False)
    return True
