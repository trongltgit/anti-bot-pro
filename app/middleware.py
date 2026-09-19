"""
Anti-Bot middleware cho Pricing & Transaction API.

Các lớp bảo vệ:
1. User-Agent bot detection
2. Session fingerprint
3. Authentication (user_id trong session)
4. HMAC signature (method + path + body + nonce)
5. Timestamp + Replay protection
"""

from functools import wraps

from flask import request, jsonify, session

from utils.security import (
    verify_fingerprint,
    verify_pricing_signature,
    is_suspicious_user_agent,
)


def pricing_security_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        # 1. Chặn User-Agent bot
        if is_suspicious_user_agent():
            return jsonify({
                "error": "ACCESS_DENIED",
                "message": "Request bị từ chối",
            }), 403

        # 2. Fingerprint session
        if not verify_fingerprint():
            return jsonify({
                "error": "INVALID_SESSION",
                "message": "Phiên làm việc không hợp lệ",
            }), 403

        # 3. Authentication
        user_id = session.get("user_id")
        if not user_id:
            return jsonify({
                "error": "AUTHENTICATION_REQUIRED",
                "message": "Yêu cầu đăng nhập",
            }), 401

        # 4. HMAC + Nonce + Timestamp
        timestamp = request.headers.get("X-Timestamp")
        signature = request.headers.get("X-Signature")
        nonce = request.headers.get("X-Nonce", "")

        if not timestamp or not signature:
            return jsonify({
                "error": "SIGNATURE_REQUIRED",
                "message": "Thiếu X-Timestamp hoặc X-Signature",
            }), 401

        body = request.get_data(as_text=True) or ""
        path = request.path
        method = request.method

        if not verify_pricing_signature(
            timestamp=timestamp,
            signature=signature,
            method=method,
            path=path,
            body=body,
            nonce=nonce,
            max_age_seconds=60,
        ):
            return jsonify({
                "error": "INVALID_SIGNATURE",
                "message": "Request signature không hợp lệ, hết hạn hoặc replay",
            }), 401

        return func(*args, **kwargs)

    return wrapper


def auth_required(func):
    """Chỉ yêu cầu đăng nhập + fingerprint (không HMAC)."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        if is_suspicious_user_agent():
            return jsonify({
                "error": "ACCESS_DENIED",
                "message": "Request bị từ chối",
            }), 403
        if not verify_fingerprint():
            return jsonify({
                "error": "INVALID_SESSION",
                "message": "Phiên làm việc không hợp lệ",
            }), 403
        if not session.get("user_id"):
            return jsonify({
                "error": "AUTHENTICATION_REQUIRED",
                "message": "Yêu cầu đăng nhập",
            }), 401
        return func(*args, **kwargs)
    return wrapper
