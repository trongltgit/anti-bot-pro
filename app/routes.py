"""
Main routes + Auth + API công khai / bảo vệ
"""

import time
import secrets

from flask import (
    Blueprint,
    render_template,
    request,
    jsonify,
    session,
)

from utils.security import (
    get_client_fingerprint,
    verify_fingerprint,
    is_suspicious_user_agent,
    get_client_ip,
    generate_pricing_signature,
)
from utils.rate_limit import custom_rate_limit
from app.customer.service import CustomerService
from app.middleware import auth_required
from services.hq_policy import hq_policy_service, HQPolicyError
from functools import wraps

main_bp = Blueprint("main", __name__)
api_bp = Blueprint("api", __name__)

customer_service = CustomerService()


@main_bp.route("/")
@custom_rate_limit("30 per minute")
def index():
    """Trang chủ – gắn fingerprint vào session"""
    fingerprint = get_client_fingerprint()
    session["fingerprint"] = fingerprint
    session["first_seen"] = int(time.time())
    session["page_views"] = session.get("page_views", 0) + 1
    return render_template(
        "index.html",
        fingerprint=fingerprint,
        client_ip=get_client_ip(),
        logged_in=bool(session.get("user_id")),
        user_name=session.get("user_name"),
        role=session.get("role"),
    )


@main_bp.route("/dashboard")
@custom_rate_limit("20 per minute")
def dashboard():
    """Dashboard giao dịch – yêu cầu fingerprint + login"""
    if not verify_fingerprint():
        return render_template("blocked.html", reason="Fingerprint không hợp lệ"), 403
    if not session.get("user_id"):
        return render_template("index.html", need_login=True), 401
    return render_template(
        "dashboard.html",
        user_name=session.get("user_name"),
        role=session.get("role"),
        customer_id=session.get("customer_id"),
        cif=session.get("cif"),
    )


@main_bp.route("/blocked")
def blocked():
    return render_template("blocked.html", reason="Truy cập bị chặn"), 403


# ============================================================
# AUTH (Demo)
# ============================================================

@api_bp.route("/auth/login", methods=["POST"])
@custom_rate_limit("10 per minute")
def login():
    """
    Demo login.
    Production: LDAP / OAuth2 / JWT + MFA.
    Body: { "username": "staff01", "password": "demo123" }
    """
    if is_suspicious_user_agent():
        return jsonify({"error": "ACCESS_DENIED", "message": "Request bị từ chối"}), 403

    # Đảm bảo có fingerprint
    if not session.get("fingerprint"):
        session["fingerprint"] = get_client_fingerprint()

    data = request.get_json(silent=True) or {}
    username = str(data.get("username", "")).strip()
    password = str(data.get("password", "")).strip()

    if not username or not password:
        return jsonify({
            "error": "INVALID_REQUEST",
            "message": "Thiếu username hoặc password.",
        }), 400

    user = customer_service.authenticate(username, password)
    if not user:
        return jsonify({
            "error": "INVALID_CREDENTIALS",
            "message": "Sai tên đăng nhập hoặc mật khẩu.",
        }), 401

    # Ghi session server-side
    session["user_id"] = user["user_id"]
    session["user_name"] = user.get("name")
    session["role"] = user.get("role")
    session["permitted_customers"] = user.get("permitted_customers") or []
    session.permanent = True

    # Customer portal tự gắn CIF
    if user.get("role") == "CUSTOMER" and user.get("customer_id"):
        session["customer_id"] = user["customer_id"]
        try:
            c = customer_service.get_customer(user["customer_id"])
            session["cif"] = c.get("cif")
        except Exception:
            session["cif"] = None
    else:
        # Staff phải chọn CIF sau
        session.pop("customer_id", None)
        session.pop("cif", None)

    return jsonify({
        "status": "success",
        "user": {
            "user_id": user["user_id"],
            "name": user.get("name"),
            "role": user.get("role"),
            "permitted_customers": user.get("permitted_customers") or [],
        },
    }), 200


@api_bp.route("/auth/logout", methods=["POST"])
@custom_rate_limit("20 per minute")
def logout():
    keys = list(session.keys())
    for k in keys:
        if k != "fingerprint":
            session.pop(k, None)
    return jsonify({"status": "success", "message": "Đã đăng xuất"}), 200


@api_bp.route("/auth/me", methods=["GET"])
@custom_rate_limit("30 per minute")
def me():
    if not session.get("user_id"):
        return jsonify({"error": "NOT_AUTHENTICATED"}), 401
    return jsonify({
        "status": "success",
        "user": {
            "user_id": session.get("user_id"),
            "name": session.get("user_name"),
            "role": session.get("role"),
            "customer_id": session.get("customer_id"),
            "cif": session.get("cif"),
            "permitted_customers": session.get("permitted_customers") or [],
        },
    }), 200


@api_bp.route("/auth/select-customer", methods=["POST"])
@custom_rate_limit("20 per minute")
@auth_required
def select_customer():
    """
    Staff chọn CIF được phép.
    Body: { "customer_id": "CUST001" }
    """
    data = request.get_json(silent=True) or {}
    customer_id = str(data.get("customer_id", "")).strip()
    if not customer_id:
        return jsonify({"error": "INVALID_REQUEST", "message": "Thiếu customer_id"}), 400

    user = {
        "user_id": session.get("user_id"),
        "role": session.get("role"),
        "customer_id": session.get("customer_id"),
        "permitted_customers": session.get("permitted_customers") or [],
    }
    if not customer_service.check_user_access(user, customer_id):
        return jsonify({
            "error": "ACCESS_DENIED",
            "message": "Bạn không có quyền với CIF này.",
        }), 403

    try:
        customer = customer_service.get_customer(customer_id)
    except Exception as e:
        return jsonify({"error": "CUSTOMER_ERROR", "message": str(e)}), 400

    session["customer_id"] = customer["customer_id"]
    session["cif"] = customer.get("cif")

    return jsonify({
        "status": "success",
        "customer": {
            "customer_id": customer["customer_id"],
            "cif": customer.get("cif"),
            "customer_name": customer.get("customer_name"),
            "segment": customer.get("segment"),
            "pricing_tier": customer.get("pricing_tier"),
        },
    }), 200


@api_bp.route("/customers/permitted", methods=["GET"])
@custom_rate_limit("20 per minute")
@auth_required
def permitted_customers():
    user = {
        "user_id": session.get("user_id"),
        "role": session.get("role"),
        "permitted_customers": session.get("permitted_customers") or [],
    }
    items = customer_service.list_permitted_customers(user)
    return jsonify({"status": "success", "customers": items}), 200




# ============================================================
# HQ POLICY API (chỉ role HQ)
# ============================================================

def hq_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            return jsonify({"error": "AUTHENTICATION_REQUIRED", "message": "Yêu cầu đăng nhập"}), 401
        if (session.get("role") or "").upper() != "HQ":
            return jsonify({
                "error": "HQ_ONLY",
                "message": "Chỉ Hội sở được truy cập chính sách giá cấp 1.",
            }), 403
        return func(*args, **kwargs)
    return wrapper


@api_bp.route("/hq/policy", methods=["GET"])
@custom_rate_limit("20 per minute")
@auth_required
@hq_required
def hq_get_policy():
    """Xem toàn bộ chính sách HQ – chỉ HQ."""
    data = hq_policy_service.get_all_policies()
    return jsonify({"status": "success", "policy": data}), 200


@api_bp.route("/hq/policy/base-spread", methods=["POST"])
@custom_rate_limit("20 per minute")
@auth_required
@hq_required
def hq_update_base_spread():
    """
    Cập nhật base_spread.
    Body: { "tier": "GOLD", "currency": "USD", "side": "SELL", "value": "14" }
    """
    data = request.get_json(silent=True) or {}
    try:
        hq_policy_service.update_base_spread(
            tier=data.get("tier", ""),
            currency=data.get("currency", ""),
            side=data.get("side", ""),
            value=data.get("value"),
        )
    except HQPolicyError as e:
        return jsonify({"error": "POLICY_ERROR", "message": str(e)}), 400
    return jsonify({
        "status": "success",
        "message": "Đã cập nhật base_spread.",
        "policy": hq_policy_service.get_all_policies(),
    }), 200


@api_bp.route("/hq/policy/max-branch-margin", methods=["POST"])
@custom_rate_limit("20 per minute")
@auth_required
@hq_required
def hq_update_max_margin():
    """
    Cập nhật trần margin chi nhánh.
    Body: { "tier": "GOLD", "currency": "USD", "value": "25" }
    """
    data = request.get_json(silent=True) or {}
    try:
        hq_policy_service.update_max_branch_margin(
            tier=data.get("tier", ""),
            currency=data.get("currency", ""),
            value=data.get("value"),
        )
    except HQPolicyError as e:
        return jsonify({"error": "POLICY_ERROR", "message": str(e)}), 400
    return jsonify({
        "status": "success",
        "message": "Đã cập nhật max_branch_margin.",
        "policy": hq_policy_service.get_all_policies(),
    }), 200


# ============================================================
# Public / protected demo APIs
# ============================================================

@api_bp.route("/public-data")
@custom_rate_limit("20 per minute")
def public_data():
    if is_suspicious_user_agent():
        return jsonify({"error": "User-Agent bị nghi ngờ"}), 403
    return jsonify({
        "status": "ok",
        "message": "Dữ liệu công khai",
        "timestamp": int(time.time()),
        "server": "anti-bot-pro",
    })


@api_bp.route("/user-data")
@custom_rate_limit("8 per minute")
def user_data():
    if not verify_fingerprint():
        return jsonify({"error": "Phiên làm việc không hợp lệ hoặc nghi bot"}), 403
    if not session.get("user_id"):
        return jsonify({"error": "AUTHENTICATION_REQUIRED"}), 401
    return jsonify({
        "status": "success",
        "user": {
            "id": session.get("user_id"),
            "name": session.get("user_name"),
            "role": session.get("role"),
            "note": "Dữ liệu đã được bảo vệ bởi nhiều lớp",
        },
        "timestamp": int(time.time()),
    })


@api_bp.route("/sensitive")
@custom_rate_limit("3 per minute")
def sensitive():
    if not verify_fingerprint():
        return jsonify({"error": "Access denied"}), 403
    if not session.get("user_id"):
        return jsonify({"error": "AUTHENTICATION_REQUIRED"}), 401
    return jsonify({
        "warning": "Endpoint nhạy cảm",
        "message": "Production phải có JWT + MFA + phân quyền chi tiết",
    })


@api_bp.route("/health")
def health():
    return jsonify({"status": "healthy", "service": "anti-bot-pro"})


@api_bp.route("/sign-helper", methods=["POST"])
@custom_rate_limit("30 per minute")
@auth_required
def sign_helper():
    """
    Demo helper: server tạo signature cho client.
    Production: client dùng session token hoặc mTLS, không lộ secret.
    Body: { "method": "POST", "path": "/api/pricing/quote", "body": "{...}" }
    """
    data = request.get_json(silent=True) or {}
    method = str(data.get("method", "POST")).upper()
    path = str(data.get("path", ""))
    body = data.get("body", "")
    if isinstance(body, dict):
        import json
        body = json.dumps(body, separators=(",", ":"), ensure_ascii=False)

    timestamp = str(int(time.time()))
    nonce = secrets.token_hex(16)

    signature = generate_pricing_signature(
        timestamp=timestamp,
        method=method,
        path=path,
        body=body,
        nonce=nonce,
    )

    return jsonify({
        "status": "success",
        "headers": {
            "X-Timestamp": timestamp,
            "X-Nonce": nonce,
            "X-Signature": signature,
        },
    }), 200
