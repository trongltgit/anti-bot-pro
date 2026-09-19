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


# ============================================================
# Simple in-memory nonce store (demo)
# Production: dùng Redis SET NX + TTL
# ============================================================
_nonce_store = OrderedDict()
_nonce_lock = Lock()
_NONCE_MAX_SIZE = 10000
_NONCE_TTL = 120  # seconds


def get_client_ip():
    """Lấy IP thật (hỗ trợ Cloudflare / proxy)"""
    if request.headers.get("CF-Connecting-IP"):
        return request.headers.get("CF-Connecting-IP")
    if request.headers.get("X-Forwarded-For"):
        return request.headers.get("X-Forwarded-For").split(",")[0].strip()
    return request.remote_addr or "unknown"


def get_client_fingerprint():
    """
    Fingerprint đơn giản từ header.
    Production nên kết hợp FingerprintJS phía client.
    """
    components = [
        request.headers.get("User-Agent", ""),
        request.headers.get("Accept", ""),
        request.headers.get("Accept-Language", ""),
        request.headers.get("Accept-Encoding", ""),
        request.headers.get("Sec-CH-UA", ""),
        request.headers.get("Sec-CH-UA-Platform", ""),
        request.headers.get("Sec-CH-UA-Mobile", ""),
        str(request.accept_languages),
    ]
    raw = "|".join(components)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def verify_fingerprint():
    """Kiểm tra fingerprint hiện tại khớp session"""
    current = get_client_fingerprint()
    stored = session.get("fingerprint")
    if not stored:
        return False
    return hmac.compare_digest(current, stored)


def is_suspicious_user_agent():
    """Phát hiện User-Agent bot phổ biến"""
    ua = (request.headers.get("User-Agent") or "").lower()
    bad_keywords = [
        "bot", "crawl", "spider", "slurp", "scrapy", "httpclient",
        "python-requests", "curl", "wget", "httpx", "aiohttp",
        "go-http", "java/", "phantomjs", "headless", "selenium",
        "puppeteer", "playwright",
    ]
    return any(k in ua for k in bad_keywords)


def generate_request_signature(timestamp: str, secret: str = None) -> str:
    """Tạo chữ ký HMAC đơn giản (legacy API)"""
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
    """
    Chữ ký đầy đủ cho Pricing / Transaction API.
    Canonical: timestamp:METHOD:path:body_hash:ip:fingerprint:nonce
    """
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
    """Xác minh chữ ký legacy + chống replay theo timestamp"""
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
    """Xác minh chữ ký pricing đầy đủ + nonce chống replay"""
    try:
        ts = int(timestamp)
    except (ValueError, TypeError):
        return False

    now = int(time.time())
    if abs(now - ts) > max_age_seconds:
        return False

    # Kiểm tra nonce (chống replay)
    if nonce:
        if not _check_and_store_nonce(nonce, ts):
            return False  # nonce đã dùng hoặc không hợp lệ

    expected = generate_pricing_signature(
        timestamp=timestamp,
        method=method,
        path=path,
        body=body,
        nonce=nonce,
    )
    return hmac.compare_digest(expected, signature)


def _check_and_store_nonce(nonce: str, ts: int) -> bool:
    """
    Lưu nonce đã dùng.
    Trả False nếu nonce đã tồn tại (replay).
    """
    if not nonce or len(nonce) < 8 or len(nonce) > 64:
        return False

    now = int(time.time())
    with _nonce_lock:
        # dọn nonce hết hạn
        expired = [k for k, v in _nonce_store.items() if now - v > _NONCE_TTL]
        for k in expired:
            _nonce_store.pop(k, None)

        if nonce in _nonce_store:
            return False  # replay

        _nonce_store[nonce] = ts

        # giới hạn kích thước
        while len(_nonce_store) > _NONCE_MAX_SIZE:
            _nonce_store.popitem(last=False)

    return True
