```python
"""
Pricing Engine
==============
Logic tính giá nằm hoàn toàn phía server.

KHÔNG trả về:
- base_rate
- spread
- margin
- cost
- pricing rule
- công thức nội bộ

Chỉ trả về final price.
"""

from decimal import Decimal, ROUND_HALF_UP
import os
import time


# ------------------------------------------------------------------
# Cấu hình mặc định DEMO
# Production: thay bằng DB / market-rate service / pricing service
# ------------------------------------------------------------------

DEFAULT_MARKET_RATES = {
    "USD": Decimal("26200"),
    "EUR": Decimal("30600"),
    "GBP": Decimal("35400"),
    "JPY": Decimal("175"),
    "AUD": Decimal("17400"),
}


DEFAULT_SPREADS = {
    "USD": {
        "BUY": Decimal("35"),
        "SELL": Decimal("35"),
    },
    "EUR": {
        "BUY": Decimal("60"),
        "SELL": Decimal("60"),
    },
    "GBP": {
        "BUY": Decimal("80"),
        "SELL": Decimal("80"),
    },
    "JPY": {
        "BUY": Decimal("0.50"),
        "SELL": Decimal("0.50"),
    },
    "AUD": {
        "BUY": Decimal("45"),
        "SELL": Decimal("45"),
    },
}


class PricingError(Exception):
    """Lỗi nghiệp vụ Pricing Engine."""


class PricingEngine:

    SUPPORTED_CURRENCIES = set(DEFAULT_MARKET_RATES.keys())
    SUPPORTED_SIDES = {"BUY", "SELL"}

    def __init__(self):
        self.environment = os.environ.get(
            "PRICING_ENVIRONMENT",
            "demo"
        )

    # --------------------------------------------------------------
    # Market rate
    # --------------------------------------------------------------

    def get_market_rate(self, currency: str) -> Decimal:
        currency = currency.upper()

        if currency not in self.SUPPORTED_CURRENCIES:
            raise PricingError("Currency không được hỗ trợ")

        # TODO PRODUCTION:
        # Thay bằng truy vấn market-rate service / database.
        return DEFAULT_MARKET_RATES[currency]

    # --------------------------------------------------------------
    # Customer pricing rule
    # --------------------------------------------------------------

    def get_customer_spread(
        self,
        customer_id: str,
        currency: str,
        side: str,
        amount: Decimal,
    ) -> Decimal:

        currency = currency.upper()
        side = side.upper()

        # TODO PRODUCTION:
        # Truy vấn pricing rule theo customer_id / segment / amount.
        #
        # Ví dụ:
        #
        # customer_id
        #       ↓
        # customer segment
        #       ↓
        # currency
        #       ↓
        # amount tier
        #       ↓
        # customer-specific spread
        #
        # Không trả rule này ra frontend.

        return DEFAULT_SPREADS[currency][side]

    # --------------------------------------------------------------
    # Tính giá
    # --------------------------------------------------------------

    def calculate_price(
        self,
        customer_id: str,
        currency: str,
        side: str,
        amount,
    ) -> dict:

        currency = currency.upper()
        side = side.upper()

        try:
            amount = Decimal(str(amount))
        except Exception:
            raise PricingError("Amount không hợp lệ")

        if amount <= 0:
            raise PricingError("Amount phải lớn hơn 0")

        if currency not in self.SUPPORTED_CURRENCIES:
            raise PricingError("Currency không được hỗ trợ")

        if side not in self.SUPPORTED_SIDES:
            raise PricingError("Side phải là BUY hoặc SELL")

        if not customer_id:
            raise PricingError("Thiếu customer_id")

        market_rate = self.get_market_rate(currency)

        spread = self.get_customer_spread(
            customer_id=customer_id,
            currency=currency,
            side=side,
            amount=amount,
        )

        if side == "BUY":
            final_price = market_rate - spread
        else:
            final_price = market_rate + spread

        final_price = final_price.quantize(
            Decimal("0.0001"),
            rounding=ROUND_HALF_UP
        )

        # Chỉ trả dữ liệu mà frontend thực sự cần.
        return {
            "currency": currency,
            "side": side,
            "price": str(final_price),
            "valid_for_seconds": 30,
            "issued_at": int(time.time()),
        }


pricing_engine = PricingEngine()
```
