import time

from flask import (
    Blueprint,
    jsonify,
    request,
    session,
)

from app.middleware import pricing_security_required

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

from services.market_rate import (
    MarketRateService,
    MarketRateError,
)

from services.pricing_engine import (
    PricingEngine,
    PricingError,
)

from utils.rate_limit import custom_rate_limit


pricing_bp = Blueprint(
    "pricing",
    __name__,
    url_prefix="/api/pricing",
)


customer_service = CustomerService()
market_rate_service = MarketRateService()
pricing_engine = PricingEngine()


@pricing_bp.route("/quote", methods=["POST"])
@custom_rate_limit("10 per minute")
@pricing_security_required
def quote():

    # ==========================================================
    # 1. USER AUTHENTICATION
    # ==========================================================

    user_id = session.get("user_id")

    if not user_id:
        return jsonify({
            "error": "AUTHENTICATION_REQUIRED",
            "message": "Yêu cầu đăng nhập.",
        }), 401

    # ==========================================================
    # 2. REQUEST DATA
    # ==========================================================

    data = request.get_json(silent=True) or {}

    currency = str(
        data.get("currency", "")
    ).upper().strip()

    side = str(
        data.get("side", "")
    ).upper().strip()

    amount = data.get("amount")

    if not currency:
        return jsonify({
            "error": "INVALID_CURRENCY",
            "message": "Thiếu currency.",
        }), 400

    if not side:
        return jsonify({
            "error": "INVALID_SIDE",
            "message": "Thiếu side.",
        }), 400

    if amount is None:
        return jsonify({
            "error": "INVALID_AMOUNT",
            "message": "Thiếu amount.",
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

    # ==========================================================
    # 3. CUSTOMER CONTEXT
    # ==========================================================
    #
    # KHÔNG lấy customer_id từ request body.
    #
    # Customer ID phải đến từ authentication / authorization
    # server-side.
    #

    customer_id = session.get(
        "customer_id"
    )

    if not customer_id:

        return jsonify({
            "error": "CUSTOMER_CONTEXT_REQUIRED",
            "message": (
                "Phiên hiện tại chưa được gắn khách hàng."
            ),
        }), 403

    # ==========================================================
    # 4. CUSTOMER API
    # ==========================================================

    try:

        customer = customer_service.get_customer(
            customer_id
        )

    except CustomerNotFound:

        return jsonify({
            "error": "CUSTOMER_NOT_FOUND",
            "message": "Không tìm thấy khách hàng.",
        }), 404

    except CustomerInactive:

        return jsonify({
            "error": "CUSTOMER_INACTIVE",
            "message": "Khách hàng không hoạt động.",
        }), 403

    except CustomerAPITimeout:

        return jsonify({
            "error": "CUSTOMER_SERVICE_TIMEOUT",
            "message": "Customer API timeout.",
        }), 504

    except CustomerAPIUnavailable:

        return jsonify({
            "error": "CUSTOMER_SERVICE_UNAVAILABLE",
            "message": "Customer API không khả dụng.",
        }), 503

    except CustomerAPIError:

        return jsonify({
            "error": "CUSTOMER_SERVICE_ERROR",
            "message": "Customer API trả lỗi.",
        }), 502

    # ==========================================================
    # 5. CHECK CUSTOMER CURRENCY PERMISSION
    # ==========================================================

    if not customer_service.check_currency_permission(
        customer,
        currency,
    ):

        return jsonify({
            "error": "CURRENCY_NOT_PERMITTED",
            "message": (
                "Khách hàng không được phép giao dịch currency này."
            ),
        }), 403

    # ==========================================================
    # 6. CHECK CUSTOMER LIMIT
    # ==========================================================

    if not customer_service.check_amount_limit(
        customer,
        amount_value,
    ):

        return jsonify({
            "error": "AMOUNT_LIMIT_EXCEEDED",
            "message": (
                "Amount vượt hạn mức khách hàng."
            ),
        }), 403

    # ==========================================================
    # 7. MARKET RATE
    # ==========================================================

    try:

        market_rate = market_rate_service.get_rate(
            currency=currency,
            side=side,
        )

    except MarketRateError:

        return jsonify({
            "error": "MARKET_RATE_UNAVAILABLE",
            "message": "Market Rate API không khả dụng.",
        }), 503

    # ==========================================================
    # 8. PRICING ENGINE
    # ==========================================================

    try:

        result = pricing_engine.calculate_price(
            customer=customer,
            currency=currency,
            side=side,
            amount=amount_value,
            market_rate=market_rate,
        )

    except PricingError:

        return jsonify({
            "error": "PRICING_UNAVAILABLE",
            "message": "Không thể tính giá.",
        }), 503

    # ==========================================================
    # 9. CLIENT RESPONSE
    # ==========================================================
    #
    # CHỈ trả FINAL PRICE.
    #
    # Không trả:
    # - market_rate
    # - spread
    # - margin
    # - pricing tier
    # - pricing rule
    # - customer pricing
    #

    return jsonify({
        "status": "success",
        "quote": {
            "currency": result["currency"],
            "side": result["side"],
            "price": result["price"],
            "valid_for_seconds": (
                result["valid_for_seconds"]
            ),
            "issued_at": result["issued_at"],
        },
    }), 200


@pricing_bp.route("/health", methods=["GET"])
def pricing_health():

    return jsonify({
        "status": "healthy",
        "service": "pricing-api",
        "timestamp": int(time.time()),
    }), 200
