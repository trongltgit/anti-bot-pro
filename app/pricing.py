```python
"""
Pricing API
===========

API dành cho hệ thống giá.

Frontend chỉ nhận FINAL PRICE.

Không expose:
- market rate
- spread
- margin
- pricing rule
- cost
- internal calculation
"""

from decimal import Decimal

from flask import Blueprint, request, jsonify, session

from utils.rate_limit import custom_rate_limit
from app.middleware import pricing_security_required
from services.pricing_engine import pricing_engine, PricingError


pricing_bp = Blueprint(
    "pricing",
    __name__,
    url_prefix="/api/pricing"
)


@pricing_bp.route("/quote", methods=["POST"])
@custom_rate_limit("10 per minute")
@pricing_security_required
def quote():

    data = request.get_json(silent=True) or {}

    currency = str(
        data.get("currency", "")
    ).strip().upper()

    side = str(
        data.get("side", "")
    ).strip().upper()

    amount = data.get("amount")

    # --------------------------------------------------------------
    # Không nhận customer_id từ frontend.
    #
    # customer_id phải lấy từ authenticated session.
    # --------------------------------------------------------------

    customer_id = session.get("customer_id")

    if not customer_id:
        return jsonify({
            "error": "CUSTOMER_CONTEXT_REQUIRED",
            "message": "Không xác định được khách hàng"
        }), 403

    if not currency or not side or amount is None:
        return jsonify({
            "error": "INVALID_REQUEST",
            "message": "Thiếu currency, side hoặc amount"
        }), 400

    try:
        amount_decimal = Decimal(str(amount))

    except Exception:
        return jsonify({
            "error": "INVALID_AMOUNT",
            "message": "Amount không hợp lệ"
        }), 400

    # --------------------------------------------------------------
    # Giới hạn amount ở API layer.
    # Production nên lấy limit từ DB/customer policy.
    # --------------------------------------------------------------

    max_amount = Decimal("10000000")

    if amount_decimal <= 0:
        return jsonify({
            "error": "INVALID_AMOUNT",
            "message": "Amount phải lớn hơn 0"
        }), 400

    if amount_decimal > max_amount:
        return jsonify({
            "error": "AMOUNT_LIMIT_EXCEEDED",
            "message": "Vượt hạn mức báo giá"
        }), 403

    try:

        result = pricing_engine.calculate_price(
            customer_id=customer_id,
            currency=currency,
            side=side,
            amount=amount_decimal,
        )

    except PricingError as exc:

        return jsonify({
            "error": "PRICING_ERROR",
            "message": str(exc)
        }), 400

    # --------------------------------------------------------------
    # Chỉ trả FINAL PRICE.
    #
    # TUYỆT ĐỐI không return pricing_engine internals.
    # --------------------------------------------------------------

    return jsonify({
        "status": "success",
        "quote": result
    }), 200


@pricing_bp.route("/health", methods=["GET"])
def pricing_health():

    return jsonify({
        "service": "pricing-api",
        "status": "healthy"
    })
```
