import os
import requests


class MarketRateError(Exception):
    pass


class MarketRateService:

    def __init__(self):
        self.base_url = os.environ.get(
            "MARKET_RATE_API_URL",
            ""
        ).strip().rstrip("/")

        self.api_key = os.environ.get(
            "MARKET_RATE_API_KEY",
            ""
        ).strip()

        self.timeout = float(
            os.environ.get(
                "MARKET_RATE_API_TIMEOUT",
                "5"
            )
        )

        if not self.base_url:
            raise MarketRateError(
                "MARKET_RATE_API_URL chưa được cấu hình."
            )

    def get_rate(self, currency, side):
        currency = currency.upper()
        side = side.upper()

        headers = {
            "Accept": "application/json",
            "User-Agent": "Anti-Bot-Pro/1.0"
        }

        if self.api_key:
            headers["Authorization"] = (
                f"Bearer {self.api_key}"
            )

        try:
            response = requests.get(
                f"{self.base_url}/rate",
                params={
                    "currency": currency,
                    "side": side
                },
                headers=headers,
                timeout=self.timeout
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
            raise MarketRateError(
                "Market Rate API không trả rate."
            )

        try:
            return float(rate)
        except (TypeError, ValueError) as exc:
            raise MarketRateError(
                "Market rate không hợp lệ."
            ) from exc
