"""
HQ Base Price
Demo: dao động nhẹ theo thời gian (giả realtime).
Production: HQ autotrade hoặc cập nhật manual qua MARKET_RATE_API_URL.
"""
import os
import time
import random
from decimal import Decimal
import requests


class MarketRateError(Exception):
    pass


DEMO_BASE = {
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
        # biên độ dao động demo (%), HQ có thể set env
        try:
            self.demo_jitter_pct = float(os.environ.get("HQ_BASE_JITTER_PCT", "0.05"))
        except ValueError:
            self.demo_jitter_pct = 0.05

    def get_rate(self, currency, side):
        currency = currency.upper()
        side = side.upper()

        if self.demo_mode:
            if currency not in DEMO_BASE:
                raise MarketRateError(f"Currency {currency} không hỗ trợ.")
            base = DEMO_BASE[currency]
            # Dao động nhẹ theo giây (demo realtime)
            seed = int(time.time()) // 5  # đổi mỗi ~5s
            random.seed(f"{currency}-{seed}")
            jitter = Decimal(str(1 + random.uniform(-self.demo_jitter_pct, self.demo_jitter_pct) / 100))
            return float((base * jitter).quantize(Decimal("0.0001")))

        headers = {"Accept": "application/json", "User-Agent": "Anti-Bot-Pro/1.0"}
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
            raise MarketRateError(f"Không kết nối base price: {exc}") from exc
        if response.status_code >= 400:
            raise MarketRateError(f"Base price HTTP {response.status_code}")
        data = response.json()
        rate = data.get("rate")
        if rate is None:
            raise MarketRateError("Không có rate.")
        return float(rate)
