```python
"""
Anti-Bot middleware cho Pricing API.

Pricing request phải vượt qua nhiều lớp:
1. User-Agent
2. Session fingerprint
3. Authentication/session
4. Request signature
5. Timestamp
6. Rate limit
"""

from functools import wraps

from flask import request, jsonify, session

from utils.security import (
    verify_fingerprint,
    verify_request_signature,
    is_suspicious_user_agent,
)


def pricing_security_required(func):

    @wraps(func)
    def wrapper(*args, **kwargs):

        # ----------------------------------------------------------
        # 1. Chặn User-Agent rõ ràng là bot
        # ----------------------------------------------------------

        if is_suspicious_user_agent():
            return jsonify({
                "error": "ACCESS_DENIED",
                "message": "Request bị từ chối"
            }), 403

        # ----------------------------------------------------------
        # 2. Phải có fingerprint session
        # ----------------------------------------------------------

        if not verify_fingerprint():
            return jsonify({
                "error": "INVALID_SESSION",
                "message": "Phiên làm việc không hợp lệ"
            }), 403

        # ----------------------------------------------------------
        # 3. Pricing API phải có authenticated user
        #
        # User ID phải được hệ thống đăng nhập thật ghi vào session.
        # Không lấy user_id từ request body.
        # ----------------------------------------------------------

        user_id = session.get("user_id")

        if not user_id:
            return jsonify({
                "error": "AUTHENTICATION_REQUIRED",
                "message": "Yêu cầu đăng nhập"
            }), 401

        # ----------------------------------------------------------
        # 4. HMAC
        # ----------------------------------------------------------

        timestamp = request.headers.get("X-Timestamp")
        signature = request.headers.get("X-Signature")

        if not timestamp or not signature:
            return jsonify({
                "error": "SIGNATURE_REQUIRED",
                "message": "Thiếu X-Timestamp hoặc X-Signature"
            }), 401

        if not verify_request_signature(
            timestamp,
            signature,
            max_age_seconds=60
        ):
            return jsonify({
                "error": "INVALID_SIGNATURE",
                "message": "Request signature không hợp lệ hoặc đã hết hạn"
            }), 401

        return func(*args, **kwargs)

    return wrapper
```
