"""
Pricing Engine – 2 cấp + phân quyền xem
=======================================

HQ:      thấy market + HQ_base + branch_margin + final
CN:      thấy market + branch_margin + final  (KHÔNG thấy HQ_base)
Customer: chỉ thấy final
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
        self.environment = os.environ.get(
            "PRICING_ENVIRONMENT", "production"
        ).strip().lower()
        try:
            self.valid_for_seconds = int(
                os.environ.get(
                    "PRICING_QUOTE_VALID_SECONDS",
                    str(self.DEFAULT_VALID_SECONDS),
                )
            )
        except (TypeError, ValueError):
            self.valid_for_seconds = self.DEFAULT_VALID_SECONDS
        if self.valid_for_seconds <= 0:
            self.valid_for_seconds = self.DEFAULT_VALID_SECONDS

    def validate_request(self, currency: str, side: str, amount: Any) -> Decimal:
        if not currency:
            raise PricingError("Thiếu currency.")
        if not side:
            raise PricingError("Thiếu side.")
        currency = str(currency).upper().strip()
        side = str(side).upper().strip()
        if currency not in self.SUPPORTED_CURRENCIES:
            raise PricingError("Currency không được hỗ trợ.")
        if side not in self.SUPPORTED_SIDES:
            raise PricingError("Side phải là BUY hoặc SELL.")
        try:
            amount = Decimal(str(amount))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise PricingError("Amount không hợp lệ.") from exc
        if not amount.is_finite() or amount <= 0:
            raise PricingError("Amount phải lớn hơn 0.")
        return amount

    def validate_market_rate(self, market_rate: Any) -> Decimal:
        try:
            rate = Decimal(str(market_rate))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise PricingError("Market rate không hợp lệ.") from exc
        if not rate.is_finite() or rate <= 0:
            raise PricingError("Market rate phải lớn hơn 0.")
        return rate

    def calculate_price(
        self,
        customer: Dict[str, Any],
        currency: str,
        side: str,
        amount: Any,
        market_rate: Any,
        branch_margin: Any = 0,
        viewer_role: str = "CUSTOMER",
    ) -> Dict[str, Any]:
        """
        viewer_role:
          HQ       → full (market, hq_base, branch_margin, final)
          PNV/STAFF→ market + branch_margin + final (không HQ_base)
          CUSTOMER → chỉ final
        """
        currency = str(currency).upper().strip()
        side = str(side).upper().strip()
        role = (viewer_role or "CUSTOMER").upper()

        amount = self.validate_request(currency, side, amount)
        market_rate = self.validate_market_rate(market_rate)

        if not customer.get("customer_id"):
            raise PricingError("Customer profile thiếu customer_id.")

        status = str(customer.get("status", "")).upper()
        if status not in {"ACTIVE", "ACTIVATED", "OPEN"}:
            raise PricingError("Customer không ở trạng thái hoạt động.")

        pricing_tier = str(
            customer.get("pricing_tier")
            or customer.get("segment")
            or "BRONZE"
        ).upper().strip()

        try:
            hq_spread = hq_policy_service.get_base_spread(
                pricing_tier=pricing_tier,
                currency=currency,
                side=side,
            )
        except HQPolicyError as exc:
            raise PricingError(str(exc)) from exc

        try:
            branch_m = hq_policy_service.validate_branch_margin(
                pricing_tier=pricing_tier,
                currency=currency,
                branch_margin=branch_margin if branch_margin is not None else 0,
            )
        except HQPolicyError as exc:
            raise PricingError(str(exc)) from exc

        total_spread = hq_spread + branch_m

        if side == "BUY":
            final_price = market_rate - total_spread
        else:
            final_price = market_rate + total_spread

        if final_price <= 0:
            raise PricingError("Final price không hợp lệ.")

        final_price = final_price.quantize(
            Decimal("0.0001"), rounding=ROUND_HALF_UP
        )
        issued_at = int(time.time())

        # ---- Response theo role ----
        result: Dict[str, Any] = {
            "currency": currency,
            "side": side,
            "price": str(final_price),
            "valid_for_seconds": self.valid_for_seconds,
            "issued_at": issued_at,
        }

        if role in {"PNV", "STAFF", "BRANCH", "HQ"}:
            # Market price công khai – CN và HQ được xem
            result["market_rate"] = str(market_rate)
            result["branch_margin"] = str(branch_m)
            try:
                result["max_branch_margin"] = str(
                    hq_policy_service.get_max_branch_margin(
                        pricing_tier, currency
                    )
                )
            except HQPolicyError:
                pass

        if role == "HQ":
            # Chỉ HQ thấy chính sách cấp 1
            result["hq_base_spread"] = str(hq_spread)
            result["pricing_tier"] = pricing_tier
            result["total_spread"] = str(total_spread)

        return result


pricing_engine = PricingEngine()
