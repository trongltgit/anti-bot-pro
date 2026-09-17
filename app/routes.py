from flask import Blueprint, render_template, request, jsonify, session, current_app
from utils.security import (
    get_client_fingerprint,
    verify_fingerprint,
    generate_request_signature,
    verify_request_signature,
    is_suspicious_user_agent,
    get_client_ip
)
from utils.rate_limit import custom_rate_limit
import time
import os

main_bp = Blueprint("main", __name__)
api_bp = Blueprint("api", __name__)


@main_bp.route("/")
@custom_rate_limit("30 per minute")
def index():
    """Trang chủ demo - gắn fingerprint vào session"""
    fingerprint = get_client_fingerprint()
    session["fingerprint"] = fingerprint
    session["first_seen"] = int(time.time())
    session["page_views"] = session.get("page_views", 0) + 1

    return render_template(
        "index.html",
        fingerprint=fingerprint,
        client_ip=get_client_ip()
    )


@main_bp.route("/dashboard")
@custom_rate_limit("20 per minute")
def dashboard():
    """Trang giả lập dashboard khách hàng - yêu cầu fingerprint hợp lệ"""
    if not verify_fingerprint():
        return render_template("blocked.html", reason="Fingerprint không hợp lệ"), 403

    return render_template("dashboard.html")


@api_bp.route("/public-data")
@custom_rate_limit("20 per minute")
def public_data():
    """API công khai - giới hạn vừa phải"""
    if is_suspicious_user_agent():
        return jsonify({"error": "User-Agent bị nghi ngờ"}), 403

    return jsonify({
        "status": "ok",
        "message": "Dữ liệu công khai",
        "timestamp": int(time.time()),
        "server": "anti-bot-pro"
    })


@api_bp.route("/user-data")
@custom_rate_limit("8 per minute")
def user_data():
    """
    API dữ liệu người dùng - bảo vệ chặt:
    - Kiểm tra fingerprint
    - Kiểm tra chữ ký request (HMAC)
    - Rate limit thấp
    """
    # 1. Kiểm tra fingerprint
    if not verify_fingerprint():
        return jsonify({"error": "Phiên làm việc không hợp lệ hoặc nghi bot"}), 403

    # 2. Kiểm tra chữ ký HMAC (client phải gửi header X-Signature + X-Timestamp)
    timestamp = request.headers.get("X-Timestamp")
    signature = request.headers.get("X-Signature")

    if not timestamp or not signature:
        return jsonify({"error": "Thiếu chữ ký bảo mật (X-Timestamp + X-Signature)"}), 401

    if not verify_request_signature(timestamp, signature):
        return jsonify({"error": "Chữ ký không hợp lệ hoặc request quá hạn"}), 401

    # 3. Giả lập dữ liệu khách hàng (trong thực tế lấy từ DB theo user_id)
    return jsonify({
        "status": "success",
        "user": {
            "id": "user_demo_001",
            "balance": "********",          # đã mask
            "last_login": "2026-09-17 10:00:00",
            "note": "Dữ liệu đã được bảo vệ bởi nhiều lớp"
        },
        "timestamp": int(time.time())
    })


@api_bp.route("/sensitive")
@custom_rate_limit("3 per minute")
def sensitive():
    """Endpoint cực kỳ nhạy cảm - giới hạn rất thấp"""
    if not verify_fingerprint():
        return jsonify({"error": "Access denied"}), 403

    return jsonify({
        "warning": "Đây là endpoint nhạy cảm nhất",
        "message": "Trong production phải có JWT + MFA + phân quyền chi tiết",
        "recommendation": "Không bao giờ để endpoint này public"
    })


@api_bp.route("/health")
def health():
    """Health check cho Render / monitoring"""
    return jsonify({"status": "healthy", "service": "anti-bot-pro"})
