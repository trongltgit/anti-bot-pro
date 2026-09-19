"""
Pricing Engine
HQ base_price (ex-market) chỉ HQ thấy.
CN / KH chỉ nhận final price.
"""

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Dict
import os
import time
from services.hq_policy import hq_policy_service, HQPolicyError


class PricingError(Exception):
    pass


class PricingEngine:
    SUPPORTED_CURRENCIES = {"USD", "EUR", "GBP", "JPY", "AUD", "SGD"}
    SUPPORTED_SIDES = {"BUY", "SELL"}
    DEFAULT_VALID_SECONDS = 30

    def __init__(self):
        try:
            self.valid_for_seconds = int(
                os.environ.get("PRICING_QUOTE_VALID_SECONDS", str(self.DEFAULT_VALID_SECONDS))
            )
        except (TypeError, ValueError):
            self.valid_for_seconds = self.DEFAULT_VALID_SECONDS
        if self.valid_for_seconds <= 0:
            self.valid_for_seconds = self.DEFAULT_VALID_SECONDS

    def validate_request(self, currency, side, amount) -> Decimal:
        currency = str(currency or "").upper().strip()
        side = str(side or "").upper().strip()
        if currency not in self.SUPPORTED_CURRENCIES:
            raise PricingError("Currency không được hỗ trợ.")
        if side not in self.SUPPORTED_SIDES:
            raise PricingError("Side phải là BUY hoặc SELL.")
        try:
            amount = Decimal(str(amount))
        except Exception as exc:
            raise PricingError("Amount không hợp lệ.") from exc
        if not amount.is_finite() or amount <= 0:
            raise PricingError("Amount phải lớn hơn 0.")
        return amount

    def validate_base_price(self, base_price) -> Decimal:
        try:
            rate = Decimal(str(base_price))
        except Exception as exc:
            raise PricingError("Base price không hợp lệ.") from exc
        if not rate.is_finite() or rate <= 0:
            raise PricingError("Base price phải lớn hơn 0.")
        return rate

    def calculate_price(
        self,
        customer: Dict[str, Any],
        currency: str,
        side: str,
        amount: Any,
        base_price: Any,
        branch_margin: Any = 0,
        viewer_role: str = "CUSTOMER",
    ) -> Dict[str, Any]:
        currency = str(currency).upper().strip()
        side = str(side).upper().strip()
        role = (viewer_role or "CUSTOMER").upper()
        amount = self.validate_request(currency, side, amount)
        base_price = self.validate_base_price(base_price)

        if not customer.get("customer_id"):
            raise PricingError("Thiếu customer_id.")
        status = str(customer.get("status", "")).upper()
        if status not in {"ACTIVE", "ACTIVATED", "OPEN"}:
            raise PricingError("Customer không hoạt động.")

        pricing_tier = str(
            customer.get("pricing_tier") or customer.get("segment") or "BRONZE"
        ).upper().strip()

        try:
            hq_spread = hq_policy_service.get_base_spread(pricing_tier, currency, side)
        except HQPolicyError as exc:
            raise PricingError(str(exc)) from exc

        try:
            branch_m = hq_policy_service.validate_branch_margin(
                pricing_tier, currency, branch_margin if branch_margin is not None else 0
            )
        except HQPolicyError as exc:
            raise PricingError(str(exc)) from exc

        total_spread = hq_spread + branch_m
        if side == "BUY":
            final_price = base_price - total_spread
        else:
            final_price = base_price + total_spread
        if final_price <= 0:
            raise PricingError("Final price không hợp lệ.")

        final_price = final_price.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
        issued_at = int(time.time())

        # CN + KH: CHỈ final price (+ branch_margin cho CN)
        result = {
            "currency": currency,
            "side": side,
            "price": str(final_price),
            "valid_for_seconds": self.valid_for_seconds,
            "issued_at": issued_at,
        }

        if role in {"PNV", "STAFF", "BRANCH"}:
            result["branch_margin"] = str(branch_m)
            try:
                result["max_branch_margin"] = str(
                    hq_policy_service.get_max_branch_margin(pricing_tier, currency)
                )
            except HQPolicyError:
                pass

        if role == "HQ":
            result["base_price"] = str(base_price)
            result["hq_base_spread"] = str(hq_spread)
            result["branch_margin"] = str(branch_m)
            result["pricing_tier"] = pricing_tier
            result["total_spread"] = str(total_spread)
            try:
                result["max_branch_margin"] = str(
                    hq_policy_service.get_max_branch_margin(pricing_tier, currency)
                )
            except HQPolicyError:
                pass

        return result


pricing_engine = PricingEngine()
