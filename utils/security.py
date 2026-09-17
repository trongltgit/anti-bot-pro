import hashlib
import hmac
import time
import os
import json
from flask import request, session


def get_client_ip():
    """Lấy IP thật (hỗ trợ Cloudflare / proxy)"""
    if request.headers.get("CF-Connecting-IP"):
        return request.headers.get("CF-Connecting-IP")
    if request.headers.get("X-Forwarded-For"):
        return request.headers.get("X-Forwarded-For").split(",")[0].strip()
    return request.remote_addr or "unknown"


def get_client_fingerprint():
    """
    Tạo fingerprint đơn giản nhưng hiệu quả từ nhiều header.
    Trong production nên kết hợp thêm FingerprintJS phía client.
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
    """Kiểm tra fingerprint hiện tại có khớp với session không"""
    current = get_client_fingerprint()
    stored = session.get("fingerprint")
    if not stored:
        return False
    return hmac.compare_digest(current, stored)


def is_suspicious_user_agent():
    """Phát hiện một số User-Agent bot phổ biến"""
    ua = (request.headers.get("User-Agent") or "").lower()
    bad_keywords = [
        "bot", "crawl", "spider", "slurp", "scrapy", "httpclient",
        "python-requests", "curl", "wget", "httpx", "aiohttp",
        "go-http", "java/", "phantomjs", "headless", "selenium"
    ]
    return any(k in ua for k in bad_keywords)


def generate_request_signature(timestamp: str, secret: str = None) -> str:
    """Tạo chữ ký HMAC cho request"""
    if secret is None:
        secret = os.environ.get("API_SIGNING_SECRET", "default-signing-secret-change-me")
    message = f"{timestamp}:{get_client_ip()}:{session.get('fingerprint', '')}"
    return hmac.new(
        secret.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

def generate_pricing_signature(
    timestamp: str,
    method: str,
    path: str,
    body: str,
    secret: str = None
) -> str:

    if secret is None:
        secret = os.environ.get(
            "API_SIGNING_SECRET",
            "default-signing-secret-change-me"
        )

    body_hash = hashlib.sha256(
        body.encode("utf-8")
    ).hexdigest()

    message = (
        f"{timestamp}:"
        f"{method.upper()}:"
        f"{path}:"
        f"{body_hash}:"
        f"{get_client_ip()}:"
        f"{session.get('fingerprint', '')}"
    )

    return hmac.new(
        secret.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

def verify_request_signature(timestamp: str, signature: str, max_age_seconds: int = 60) -> bool:
    """
    Xác minh chữ ký + chống replay attack (request không được quá cũ).
    """
    try:
        ts = int(timestamp)
    except (ValueError, TypeError):
        return False

    now = int(time.time())
    if abs(now - ts) > max_age_seconds:
        return False  # request quá hạn hoặc timestamp giả

    expected = generate_request_signature(timestamp)
    return hmac.compare_digest(expected, signature)
