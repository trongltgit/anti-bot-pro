"""
Transaction API – phân quyền theo role HQ / PNV / CUSTOMER
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
from services.market_rate import MarketRateService, MarketRateError
from services.pricing_engine import PricingEngine, PricingError
from utils.rate_limit import custom_rate_limit

transaction_bp = Blueprint(
    "transaction", __name__, url_prefix="/api/transaction"
)

customer_service = CustomerService()
market_rate_service = MarketRateService()
pricing_engine = PricingEngine()
_TRANSACTIONS = []


def _current_user():
    return {
        "user_id": session.get("user_id"),
        "role": session.get("role"),
        "customer_id": session.get("customer_id"),
        "permitted_customers": session.get("permitted_customers") or [],
    }


@transaction_bp.route("/quote", methods=["POST"])
@custom_rate_limit("10 per minute")
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
    if not customer_service.check_user_access(user, customer_id):
        return jsonify({
            "error": "ACCESS_DENIED",
            "message": "Bạn không có quyền giao dịch CIF này.",
        }), 403

    role = (session.get("role") or "CUSTOMER").upper()
    # Khách hàng không được tự set margin
    if role == "CUSTOMER":
        branch_margin = 0

    try:
        customer = customer_service.get_customer(customer_id)
    except CustomerNotFound:
        return jsonify({"error": "CUSTOMER_NOT_FOUND", "message": "Không tìm thấy khách hàng."}), 404
    except CustomerInactive:
        return jsonify({"error": "CUSTOMER_INACTIVE", "message": "Khách hàng không hoạt động."}), 403
    except (CustomerAPITimeout, CustomerAPIUnavailable, CustomerAPIError) as e:
        return jsonify({"error": "CUSTOMER_SERVICE_ERROR", "message": str(e)}), 503

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
        market_rate = market_rate_service.get_rate(currency=currency, side=side)
    except MarketRateError:
        return jsonify({
            "error": "MARKET_RATE_UNAVAILABLE",
            "message": "Market Rate không khả dụng.",
        }), 503

    try:
        result = pricing_engine.calculate_price(
            customer=customer,
            currency=currency,
            side=side,
            amount=amount_value,
            market_rate=market_rate,
            branch_margin=branch_margin,
            viewer_role=role,
        )
    except PricingError as e:
        return jsonify({"error": "PRICING_ERROR", "message": str(e)}), 400

    quote_id = str(uuid.uuid4())
    session["last_quote"] = {
        "quote_id": quote_id,
        "currency": result["currency"],
        "side": result["side"],
        "price": result["price"],
        "amount": amount_value,
        "branch_margin": result.get("branch_margin", "0"),
        "customer_id": customer_id,
        "issued_at": result["issued_at"],
        "valid_for_seconds": result["valid_for_seconds"],
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

    # CN + HQ: market + margin
    if role in {"PNV", "STAFF", "BRANCH", "HQ"}:
        if "market_rate" in result:
            quote_payload["market_rate"] = result["market_rate"]
        if "branch_margin" in result:
            quote_payload["branch_margin"] = result["branch_margin"]
        if "max_branch_margin" in result:
            quote_payload["max_branch_margin"] = result["max_branch_margin"]

    # Chỉ HQ thấy chính sách cấp 1
    if role == "HQ":
        if "hq_base_spread" in result:
            quote_payload["hq_base_spread"] = result["hq_base_spread"]
        if "pricing_tier" in result:
            quote_payload["pricing_tier"] = result["pricing_tier"]
        if "total_spread" in result:
            quote_payload["total_spread"] = result["total_spread"]

    return jsonify({"status": "success", "quote": quote_payload}), 200


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
        "currency": last_quote["currency"],
        "side": last_quote["side"],
        "amount": last_quote["amount"],
        "price": last_quote["price"],
        "branch_margin": last_quote.get("branch_margin", "0"),
        "status": "COMPLETED",
        "created_at": int(time.time()),
    }
    _TRANSACTIONS.append(txn)
    session.pop("last_quote", None)

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
    if role in {"PNV", "STAFF", "BRANCH", "HQ"}:
        txn_view["branch_margin"] = txn["branch_margin"]

    return jsonify({"status": "success", "transaction": txn_view}), 200


@transaction_bp.route("/history", methods=["GET"])
@custom_rate_limit("20 per minute")
@auth_required
def transaction_history():
    user_id = session.get("user_id")
    customer_id = session.get("customer_id")
    role = (session.get("role") or "").upper()
    items = [
        t for t in _TRANSACTIONS
        if t.get("user_id") == user_id or t.get("customer_id") == customer_id
    ]
    safe = []
    for t in items[-20:]:
        row = {
            "transaction_id": t["transaction_id"],
            "currency": t["currency"],
            "side": t["side"],
            "amount": t["amount"],
            "price": t["price"],
            "status": t["status"],
            "created_at": t["created_at"],
        }
        if role in {"PNV", "STAFF", "BRANCH", "HQ"}:
            row["branch_margin"] = t.get("branch_margin", "0")
        safe.append(row)
    return jsonify({"status": "success", "transactions": safe}), 200
