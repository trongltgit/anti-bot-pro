"""
Market Rate Service
===================

- Demo mode: trả rate cố định (khi MARKET_RATE_API_URL trống)
- Production: gọi Market Rate API thật
"""

import os
from decimal import Decimal

import requests


class MarketRateError(Exception):
    pass


# Demo rates (VND per unit) – chỉ dùng local demo
DEMO_RATES = {
    "USD": Decimal("26200"),
    "EUR": Decimal("30600"),
    "GBP": Decimal("35400"),
    "JPY": Decimal("175"),
    "AUD": Decimal("17400"),
    "SGD": Decimal("19800"),
}


class MarketRateService:

    def __init__(self):
        self.base_url = os.environ.get("MARKET_RATE_API_URL", "").strip().rstrip("/")
        self.api_key = os.environ.get("MARKET_RATE_API_KEY", "").strip()
        self.timeout = float(os.environ.get("MARKET_RATE_API_TIMEOUT", "5"))
        self.demo_mode = not bool(self.base_url)

    def get_rate(self, currency, side):
        currency = currency.upper()
        side = side.upper()

        if self.demo_mode:
            if currency not in DEMO_RATES:
                raise MarketRateError(f"Currency {currency} không có trong demo rates.")
            return float(DEMO_RATES[currency])

        headers = {
            "Accept": "application/json",
            "User-Agent": "Anti-Bot-Pro/1.0",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        try:
            response = requests.get(
                f"{self.base_url}/rate",
                params={"currency": currency, "side": side},
                headers=headers,
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise MarketRateError(
                f"Không thể kết nối Market Rate API: {exc}"
            ) from exc

        if response.status_code >= 400:
            raise MarketRateError(
                f"Market Rate API HTTP {response.status_code}"
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise MarketRateError(
                "Market Rate API không trả JSON hợp lệ."
            ) from exc

        rate = data.get("rate")
        if rate is None:
            raise MarketRateError("Market Rate API không trả rate.")

        try:
            return float(rate)
        except (TypeError, ValueError) as exc:
            raise MarketRateError("Market rate không hợp lệ.") from exc
