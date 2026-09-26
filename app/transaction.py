"""
Transaction API – phân quyền theo role HQ / CN_ADMIN / PNV / CUSTOMER
"""

import time
import uuid

from flask import Blueprint, request, jsonify, session

from app.middleware import pricing_security_required, auth_required
from app.customer.service import (
    CustomerService,
    CustomerNotFound,
    CustomerInactive,
)
from app.customer.repository import (
    CustomerAPIError,
    CustomerAPIUnavailable,
    CustomerAPITimeout,
)
from services.market_rate import market_rate_service, MarketRateError
from services.pricing_engine import pricing_engine, PricingError
from services.audit_log import add_log, count_recent_quotes, list_logs
from utils.rate_limit import custom_rate_limit
from utils.security import get_client_ip

transaction_bp = Blueprint(
    "transaction", __name__, url_prefix="/api/transaction"
)

customer_service = CustomerService()
_TRANSACTIONS = []

# KH hỏi giá quá nhiều trong cửa sổ → buộc đăng nhập lại
KH_QUOTE_SOFT_LIMIT = 8   # trong 60s → reject + force re-login
KH_QUOTE_HARD_LIMIT = 20  # trong 60s → coi như bot, blocked


def _current_user():
    return {
        "user_id": session.get("user_id"),
        "role": session.get("role"),
        "customer_id": session.get("customer_id"),
        "permitted_customers": session.get("permitted_customers") or [],
        "branch_id": session.get("branch_id") or "",
    }


@transaction_bp.route("/quote", methods=["POST"])
@custom_rate_limit("15 per minute")
@pricing_security_required
def transaction_quote():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({
            "error": "AUTHENTICATION_REQUIRED",
            "message": "Yêu cầu đăng nhập.",
        }), 401

    data = request.get_json(silent=True) or {}
    currency = str(data.get("currency", "")).upper().strip()
    side = str(data.get("side", "")).upper().strip()
    amount = data.get("amount")
    branch_margin = data.get("branch_margin", 0)
    ip = get_client_ip()

    if not currency or not side or amount is None:
        return jsonify({
            "error": "INVALID_REQUEST",
            "message": "Thiếu currency, side hoặc amount.",
        }), 400

    try:
        amount_value = float(amount)
    except (TypeError, ValueError):
        return jsonify({
            "error": "INVALID_AMOUNT",
            "message": "Amount không hợp lệ.",
        }), 400

    if amount_value <= 0:
        return jsonify({
            "error": "INVALID_AMOUNT",
            "message": "Amount phải lớn hơn 0.",
        }), 400

    customer_id = session.get("customer_id")
    if not customer_id:
        return jsonify({
            "error": "CUSTOMER_CONTEXT_REQUIRED",
            "message": "Chưa chọn khách hàng (CIF).",
        }), 403

    user = _current_user()
    role = (session.get("role") or "CUSTOMER").upper()

    # --- Anti-bot / abuse cho KH ---
    if role == "CUSTOMER":
        recent = count_recent_quotes(user_id, window_seconds=60)
        add_log(
            "quote_request",
            user_id=user_id,
            role=role,
            customer_id=customer_id,
            ip=ip,
            detail={"currency": currency, "side": side, "amount": amount_value, "count_60s": recent + 1},
        )
        if recent + 1 >= KH_QUOTE_HARD_LIMIT:
            add_log(
                "bot_blocked",
                user_id=user_id,
                role=role,
                customer_id=customer_id,
                ip=ip,
                level="critical",
                detail={"reason": "quote_flood"},
            )
            session.clear()
            return jsonify({
                "error": "BLOCKED",
                "message": "Phát hiện hành vi bất thường. Truy cập bị chặn.",
                "redirect": "/blocked",
            }), 403
        if recent + 1 >= KH_QUOTE_SOFT_LIMIT:
            add_log(
                "force_relogin",
                user_id=user_id,
                role=role,
                customer_id=customer_id,
                ip=ip,
                level="warn",
                detail={"reason": "too_many_quotes"},
            )
            session.clear()
            return jsonify({
                "error": "SESSION_EXPIRED",
                "message": "Bạn đã hỏi giá quá nhiều lần. Vui lòng đăng nhập lại.",
                "redirect": "/",
            }), 401
    else:
        add_log(
            "quote_request",
            user_id=user_id,
            role=role,
            customer_id=customer_id,
            branch_id=user.get("branch_id", ""),
            ip=ip,
            detail={"currency": currency, "side": side, "amount": amount_value},
        )

    if not customer_service.check_user_access(user, customer_id):
        return jsonify({
            "error": "ACCESS_DENIED",
            "message": "Bạn không có quyền giao dịch CIF này.",
        }), 403

    if role == "CUSTOMER":
        branch_margin = 0
        try:
            from services.cn_margin_store import get_preset
            preset = get_preset(customer_id, currency, side, amount)
            if preset:
                branch_margin = preset["margin"]
            else:
                return jsonify({
                    "error": "WAITING_CN_SETUP",
                    "message": "Chưa có báo giá từ chi nhánh. Vui lòng liên hệ CN hoặc thử lại sau.",
                }), 403
        except Exception:
            return jsonify({
                "error": "WAITING_CN_SETUP",
                "message": "Chưa có báo giá từ chi nhánh. Vui lòng liên hệ CN hoặc thử lại sau.",
            }), 403

    try:
        customer = customer_service.get_customer(customer_id)
    except CustomerNotFound:
        return jsonify({"error": "CUSTOMER_NOT_FOUND", "message": "Không tìm thấy khách hàng."}), 404
    except CustomerInactive:
        return jsonify({"error": "CUSTOMER_INACTIVE", "message": "Khách hàng không hoạt động."}), 403
    except (CustomerAPITimeout, CustomerAPIUnavailable, CustomerAPIError) as e:
        return jsonify({"error": "CUSTOMER_SERVICE_ERROR", "message": str(e)}), 503

    # KH online: chỉ CIF online + đã login mới được quote
    if role == "CUSTOMER" and not customer.get("online", False):
        return jsonify({
            "error": "CIF_OFFLINE",
            "message": "CIF chưa được chi nhánh bật online. Vui lòng liên hệ CN.",
        }), 403

    if not customer_service.check_currency_permission(customer, currency):
        return jsonify({
            "error": "CURRENCY_NOT_PERMITTED",
            "message": "Khách hàng không được phép giao dịch currency này.",
        }), 403

    if not customer_service.check_amount_limit(customer, amount_value):
        return jsonify({
            "error": "AMOUNT_LIMIT_EXCEEDED",
            "message": "Amount vượt hạn mức khách hàng.",
        }), 403

    try:
        base_price = market_rate_service.get_rate(currency=currency, side=side)
    except MarketRateError:
        return jsonify({
            "error": "BASE_PRICE_UNAVAILABLE",
            "message": "Base price HQ không khả dụng.",
        }), 503

    try:
        result = pricing_engine.calculate_price(
            customer=customer,
            currency=currency,
            side=side,
            amount=amount_value,
            base_price=base_price,
            branch_margin=branch_margin,
            viewer_role=role,
        )
    except PricingError as e:
        return jsonify({"error": "PRICING_ERROR", "message": str(e)}), 400

    quote_id = str(uuid.uuid4())
    # Lưu internal full (kể cả margin) để execute / HQ sau deal
    session["last_quote"] = {
        "quote_id": quote_id,
        "currency": result["currency"],
        "side": result["side"],
        "price": result["price"],
        "tgdh": result.get("tgdh"),
        "amount": amount_value,
        "branch_margin": result.get("branch_margin") or result.get("_branch_margin", "0"),
        "customer_id": customer_id,
        "issued_at": result["issued_at"],
        "valid_for_seconds": result["valid_for_seconds"],
        "base_price": result.get("base_price"),
        "hq_base_spread": result.get("hq_base_spread"),
        "tgdh_points": result.get("tgdh_points"),
    }

    quote_payload = {
        "quote_id": quote_id,
        "currency": result["currency"],
        "side": result["side"],
        "price": result["price"],
        "amount": amount_value,
        "valid_for_seconds": result["valid_for_seconds"],
        "issued_at": result["issued_at"],
    }

    # CN: final + margin
    if role in {"PNV", "STAFF", "BRANCH", "CN_ADMIN"}:
        if "branch_margin" in result:
            quote_payload["branch_margin"] = result["branch_margin"]
        if "max_branch_margin" in result:
            quote_payload["max_branch_margin"] = result["max_branch_margin"]

    # HQ: full TRỪ margin CN (chỉ lộ sau deal done)
    if role == "HQ":
        for k in ("base_price", "hq_base_spread", "tgdh", "tgdh_points",
                  "pricing_tier", "total_spread"):
            if k in result:
                quote_payload[k] = result[k]
        # KHÔNG trả branch_margin lúc quote

    return jsonify({"status": "success", "quote": quote_payload}), 200


@transaction_bp.route("/quote-batch", methods=["POST"])
@custom_rate_limit("10 per minute")
@pricing_security_required
def transaction_quote_batch():
    """
    CN staff: xem giá nhiều CIF / nhiều dòng (ccy + side) cùng lúc.
    Body: {
      "items": [
        {"customer_id": "CUST001", "currency": "USD", "side": "SELL", "amount": 100000, "branch_margin": 5},
        ...
      ]
    }
    Không giới hạn số dòng cùng CIF.
    """
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "AUTHENTICATION_REQUIRED", "message": "Yêu cầu đăng nhập."}), 401

    role = (session.get("role") or "").upper()
    if role not in {"PNV", "STAFF", "BRANCH", "CN_ADMIN", "HQ"}:
        return jsonify({"error": "FORBIDDEN", "message": "Chỉ CN/HQ dùng batch quote."}), 403

    data = request.get_json(silent=True) or {}
    items = data.get("items") or []
    if not isinstance(items, list) or not items:
        return jsonify({"error": "INVALID", "message": "Thiếu items[]."}), 400
    if len(items) > 50:
        return jsonify({"error": "TOO_MANY", "message": "Tối đa 50 dòng / lần."}), 400

    user = _current_user()
    results = []
    for raw in items:
        cid = str(raw.get("customer_id") or session.get("customer_id") or "").strip()
        currency = str(raw.get("currency", "")).upper().strip()
        side = str(raw.get("side", "")).upper().strip()
        amount = raw.get("amount")
        branch_margin = raw.get("branch_margin", 0)
        row = {"customer_id": cid, "currency": currency, "side": side, "amount": amount}

        if not cid or not currency or not side or amount is None:
            row["error"] = "Thiếu trường"
            results.append(row)
            continue
        if not customer_service.check_user_access(user, cid):
            row["error"] = "Không có quyền CIF"
            results.append(row)
            continue
        try:
            amount_value = float(amount)
            if amount_value <= 0:
                raise ValueError()
        except (TypeError, ValueError):
            row["error"] = "Amount không hợp lệ"
            results.append(row)
            continue

        try:
            customer = customer_service.get_customer(cid)
            base_price = market_rate_service.get_rate(currency=currency, side=side)
            result = pricing_engine.calculate_price(
                customer=customer,
                currency=currency,
                side=side,
                amount=amount_value,
                base_price=base_price,
                branch_margin=branch_margin,
                viewer_role=role if role != "HQ" else "PNV",  # HQ batch cũng chỉ final+margin
            )
            row["price"] = result["price"]
            row["branch_margin"] = result.get("branch_margin", "0")
            row["max_branch_margin"] = result.get("max_branch_margin")
            row["valid_for_seconds"] = result["valid_for_seconds"]
            row["issued_at"] = result["issued_at"]
        except Exception as e:
            row["error"] = str(e)
        results.append(row)

    add_log(
        "quote_batch",
        user_id=user_id,
        role=role,
        branch_id=user.get("branch_id", ""),
        ip=get_client_ip(),
        detail={"count": len(items)},
    )
    return jsonify({"status": "success", "quotes": results}), 200


@transaction_bp.route("/execute", methods=["POST"])
@custom_rate_limit("5 per minute")
@pricing_security_required
def transaction_execute():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({
            "error": "AUTHENTICATION_REQUIRED",
            "message": "Yêu cầu đăng nhập.",
        }), 401

    data = request.get_json(silent=True) or {}
    quote_id = str(data.get("quote_id", "")).strip()
    last_quote = session.get("last_quote")

    if not last_quote or last_quote.get("quote_id") != quote_id:
        return jsonify({
            "error": "INVALID_QUOTE",
            "message": "Quote không hợp lệ hoặc đã hết hạn.",
        }), 400

    if int(time.time()) - last_quote.get("issued_at", 0) > last_quote.get("valid_for_seconds", 30):
        return jsonify({
            "error": "QUOTE_EXPIRED",
            "message": "Quote đã hết hạn. Vui lòng lấy giá mới.",
        }), 400

    customer_id = last_quote.get("customer_id")
    user = _current_user()
    if not customer_service.check_user_access(user, customer_id):
        return jsonify({
            "error": "ACCESS_DENIED",
            "message": "Không có quyền thực hiện giao dịch.",
        }), 403

    txn_id = f"TXN{int(time.time())}{uuid.uuid4().hex[:6].upper()}"
    txn = {
        "transaction_id": txn_id,
        "quote_id": quote_id,
        "customer_id": customer_id,
        "user_id": user_id,
        "branch_id": user.get("branch_id", ""),
        "currency": last_quote["currency"],
        "side": last_quote["side"],
        "amount": last_quote["amount"],
        "price": last_quote["price"],
        "tgdh": last_quote.get("tgdh"),
        "branch_margin": last_quote.get("branch_margin", "0"),
        "base_price": last_quote.get("base_price"),
        "hq_base_spread": last_quote.get("hq_base_spread"),
        "tgdh_points": last_quote.get("tgdh_points"),
        "status": "COMPLETED",
        "created_at": int(time.time()),
    }
    _TRANSACTIONS.append(txn)
    session.pop("last_quote", None)

    add_log(
        "deal_done",
        user_id=user_id,
        role=(session.get("role") or ""),
        customer_id=customer_id,
        branch_id=user.get("branch_id", ""),
        ip=get_client_ip(),
        detail={"txn": txn_id, "price": txn["price"], "margin": txn["branch_margin"]},
    )

    role = (session.get("role") or "").upper()
    txn_view = {
        "transaction_id": txn_id,
        "currency": txn["currency"],
        "side": txn["side"],
        "amount": txn["amount"],
        "price": txn["price"],
        "status": txn["status"],
        "created_at": txn["created_at"],
    }
    # CN: thấy margin
    if role in {"PNV", "STAFF", "BRANCH", "CN_ADMIN"}:
        txn_view["branch_margin"] = txn["branch_margin"]
    # HQ: sau deal mới thấy margin CN + full
    if role == "HQ":
        txn_view["branch_margin"] = txn["branch_margin"]
        txn_view["base_price"] = txn.get("base_price")
        txn_view["tgdh"] = txn.get("tgdh")
        txn_view["tgdh_points"] = txn.get("tgdh_points")
        txn_view["hq_base_spread"] = txn.get("hq_base_spread")

    return jsonify({"status": "success", "transaction": txn_view}), 200


@transaction_bp.route("/history", methods=["GET"])
@custom_rate_limit("20 per minute")
@auth_required
def transaction_history():
    user_id = session.get("user_id")
    customer_id = session.get("customer_id")
    role = (session.get("role") or "").upper()
    branch_id = session.get("branch_id") or ""

    if role == "HQ":
        items = list(_TRANSACTIONS)
    elif role == "CN_ADMIN":
        items = [t for t in _TRANSACTIONS if t.get("branch_id") == branch_id]
    else:
        items = [
            t for t in _TRANSACTIONS
            if t.get("user_id") == user_id or t.get("customer_id") == customer_id
        ]

    safe = []
    for t in items[-50:]:
        row = {
            "transaction_id": t["transaction_id"],
            "currency": t["currency"],
            "side": t["side"],
            "amount": t["amount"],
            "price": t["price"],
            "status": t["status"],
            "created_at": t["created_at"],
            "customer_id": t.get("customer_id"),
        }
        if role in {"PNV", "STAFF", "BRANCH", "CN_ADMIN"}:
            row["branch_margin"] = t.get("branch_margin", "0")
        if role == "HQ":
            # Sau deal: HQ thấy margin CN
            row["branch_margin"] = t.get("branch_margin", "0")
            row["base_price"] = t.get("base_price")
            row["tgdh"] = t.get("tgdh")
        safe.append(row)
    return jsonify({"status": "success", "transactions": safe}), 200


@transaction_bp.route("/audit-logs", methods=["GET"])
@custom_rate_limit("20 per minute")
@auth_required
def audit_logs():
    role = (session.get("role") or "").upper()
    if role not in {"HQ", "CN_ADMIN"}:
        return jsonify({"error": "FORBIDDEN", "message": "Chỉ TSC hoặc Admin CN xem log."}), 403
    logs = list_logs(
        role_viewer=role,
        branch_id=session.get("branch_id") or "",
        user_id=session.get("user_id") or "",
        limit=200,
    )
    return jsonify({"status": "success", "logs": logs}), 200
