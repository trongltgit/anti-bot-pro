"""
Pricing Engine
==============

Pricing calculation is performed entirely server-side.

IMPORTANT SECURITY RULES
------------------------
Frontend MUST NOT receive:
- market_rate
- spread
- margin
- cost
- pricing_rule
- pricing_tier
- internal pricing formula

Frontend receives FINAL PRICE only.

Architecture:

Customer API
     ↓
Customer Profile
     ↓
Pricing Engine
     ↑
Market Rate Service
"""

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Dict

import os
import time


class PricingError(Exception):
    """Business error raised by Pricing Engine."""


class PricingEngine:
    """
    Server-side pricing engine.

    This class does NOT own Customer DB.
    This class does NOT contain demo market rates.
    This class does NOT contain demo customer spreads.

    Customer information must come from Customer Service/API.
    Market rate must come from Market Rate Service/API.
    """

    SUPPORTED_CURRENCIES = {
        "USD",
        "EUR",
        "GBP",
        "JPY",
        "AUD",
        "SGD",
    }

    SUPPORTED_SIDES = {
        "BUY",
        "SELL",
    }

    DEFAULT_VALID_SECONDS = 30

    def __init__(self):
        self.environment = os.environ.get(
            "PRICING_ENVIRONMENT",
            "production",
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

    # ==============================================================
    # VALIDATION
    # ==============================================================

    def validate_request(
        self,
        currency: str,
        side: str,
        amount: Any,
    ) -> Decimal:

        if not currency:
            raise PricingError(
                "Thiếu currency."
            )

        if not side:
            raise PricingError(
                "Thiếu side."
            )

        currency = str(currency).upper().strip()
        side = str(side).upper().strip()

        if currency not in self.SUPPORTED_CURRENCIES:
            raise PricingError(
                "Currency không được hỗ trợ."
            )

        if side not in self.SUPPORTED_SIDES:
            raise PricingError(
                "Side phải là BUY hoặc SELL."
            )

        try:
            amount = Decimal(str(amount))
        except (
            InvalidOperation,
            TypeError,
            ValueError,
        ) as exc:
            raise PricingError(
                "Amount không hợp lệ."
            ) from exc

        if not amount.is_finite():
            raise PricingError(
                "Amount không hợp lệ."
            )

        if amount <= 0:
            raise PricingError(
                "Amount phải lớn hơn 0."
            )

        return amount

    # ==============================================================
    # CUSTOMER PRICING PROFILE
    # ==============================================================

    def get_customer_spread(
        self,
        customer: Dict[str, Any],
        currency: str,
        side: str,
        amount: Decimal,
    ) -> Decimal:
        """
        Obtain customer-specific pricing spread.

        IMPORTANT:
        This method intentionally does NOT contain demo pricing rules.

        The Customer Service / Customer API should provide the pricing
        information required by the business system.

        Expected customer profile can contain, for example:

            {
                "customer_id": "...",
                "pricing_tier": "GOLD",
                "pricing": {
                    "USD": {
                        "BUY": "...",
                        "SELL": "..."
                    }
                }
            }

        The exact mapping can later be adjusted to the real
        Customer API response.
        """

        if not customer:
            raise PricingError(
                "Thiếu customer profile."
            )

        pricing = customer.get("pricing")

        if not isinstance(pricing, dict):
            raise PricingError(
                "Customer profile chưa có pricing configuration."
            )

        currency_config = pricing.get(
            currency
        )

        if not isinstance(currency_config, dict):
            raise PricingError(
                f"Chưa có pricing cho {currency}."
            )

        spread_value = currency_config.get(
            side
        )

        if spread_value is None:
            raise PricingError(
                f"Chưa có pricing rule cho "
                f"{currency}/{side}."
            )

        try:
            spread = Decimal(
                str(spread_value)
            )
        except (
            InvalidOperation,
            TypeError,
            ValueError,
        ) as exc:
            raise PricingError(
                "Customer pricing spread không hợp lệ."
            ) from exc

        if not spread.is_finite():
            raise PricingError(
                "Customer pricing spread không hợp lệ."
            )

        if spread < 0:
            raise PricingError(
                "Customer pricing spread không được âm."
            )

        return spread

    # ==============================================================
    # MARKET RATE
    # ==============================================================

    def validate_market_rate(
        self,
        market_rate: Any,
    ) -> Decimal:
        """
        Validate a market rate supplied by the server-side
        Market Rate Service.
        """

        try:
            rate = Decimal(
                str(market_rate)
            )
        except (
            InvalidOperation,
            TypeError,
            ValueError,
        ) as exc:
            raise PricingError(
                "Market rate không hợp lệ."
            ) from exc

        if not rate.is_finite():
            raise PricingError(
                "Market rate không hợp lệ."
            )

        if rate <= 0:
            raise PricingError(
                "Market rate phải lớn hơn 0."
            )

        return rate

    # ==============================================================
    # CALCULATE
    # ==============================================================

    def calculate_price(
        self,
        customer: Dict[str, Any],
        currency: str,
        side: str,
        amount: Any,
        market_rate: Any,
    ) -> Dict[str, Any]:
        """
        Calculate final customer price.

        Parameters
        ----------
        customer:
            Customer profile returned from Customer API.

        currency:
            Currency requested by the authenticated user.

        side:
            BUY or SELL.

        amount:
            Transaction amount.

        market_rate:
            Market rate obtained from server-side Market Rate API.

        Returns
        -------
        dict
            Only safe client-facing quote information.
        """

        currency = str(
            currency
        ).upper().strip()

        side = str(
            side
        ).upper().strip()

        amount = self.validate_request(
            currency=currency,
            side=side,
            amount=amount,
        )

        market_rate = self.validate_market_rate(
            market_rate
        )

        # ----------------------------------------------------------
        # Customer identity validation
        # ----------------------------------------------------------

        customer_id = customer.get(
            "customer_id"
        )

        if not customer_id:
            raise PricingError(
                "Customer profile thiếu customer_id."
            )

        customer_status = str(
            customer.get(
                "status",
                ""
            )
        ).upper()

        if customer_status not in {
            "ACTIVE",
            "ACTIVATED",
            "OPEN",
        }:
            raise PricingError(
                "Customer không ở trạng thái hoạt động."
            )

        # ----------------------------------------------------------
        # Customer-specific pricing
        # ----------------------------------------------------------

        spread = self.get_customer_spread(
            customer=customer,
            currency=currency,
            side=side,
            amount=amount,
        )

        # ----------------------------------------------------------
        # Final price
        # ----------------------------------------------------------

        if side == "BUY":
            final_price = market_rate - spread
        else:
            final_price = market_rate + spread

        if final_price <= 0:
            raise PricingError(
                "Final price không hợp lệ."
            )

        # ----------------------------------------------------------
        # Precision
        # ----------------------------------------------------------

        final_price = final_price.quantize(
            Decimal("0.0001"),
            rounding=ROUND_HALF_UP,
        )

        issued_at = int(
            time.time()
        )

        # ----------------------------------------------------------
        # SECURITY:
        # NEVER return market_rate/spread/customer pricing.
        # ----------------------------------------------------------

        return {
            "currency": currency,
            "side": side,
            "price": str(final_price),
            "valid_for_seconds": self.valid_for_seconds,
            "issued_at": issued_at,
        }


# Singleton used by Pricing API
pricing_engine = PricingEngine()
