"""Dados explicitamente sintéticos para testar o encadeamento, sem cotações reais."""
from __future__ import annotations

from copy import deepcopy
from decimal import Decimal

from .models import Candle, D, jsonable


def api_bars(candles: list[Candle]) -> dict:
    mapping = {"time": "ts", "open": "open", "high": "high", "low": "low", "close": "close", "vol": "volume"}
    return {k: [jsonable(getattr(c, field)) for c in candles] for k, field in mapping.items()}


class DemoClient:
    def __init__(self, at: int):
        self.now = ((at - 30) // 900) * 900 + 30
        end = self.now - 30
        self.quarter = [Candle(end - (480 - i) * 900, 900, D(100), D("100.5"), D("99.5"), D(100), D(1000)) for i in range(480)]
        centers = ["98.3", "98.4", "99.5", "100.5", "101.5", "101.4", "100.5", "99.5"]
        for i, center in enumerate(centers):
            old = self.quarter[-10 + i]
            c = D(center)
            self.quarter[-10 + i] = Candle(old.ts, 900, c, c + D("0.5"), c - D("0.5"), c, D(1000))
        old = self.quarter[-2]
        self.quarter[-2] = Candle(old.ts, 900, D("101.3"), D("102.35"), D("101.2"), D("102.2"), D(1500))
        old = self.quarter[-1]
        self.quarter[-1] = Candle(old.ts, 900, D("102.2"), D("102.4"), D("102.1"), D("102.24"), D(1300))
        hour_end = (end // 3600) * 3600
        self.hourly = [Candle(hour_end - (240 - i) * 3600, 3600, D(100), D(102), D(98), D(100), D(4000)) for i in range(240)]

    def server_time(self):
        return self.now

    def contracts(self):
        return [{"symbol": "DEMO_USDT", "baseCoin": "DEMO", "quoteCoin": "USDT", "settleCoin": "USDT",
                 "state": 0, "futureType": 1, "typeLabel": 0, "contractSize": "0.001", "minVol": "1",
                 "volUnit": "1", "priceUnit": "0.001", "maxLeverage": 20, "maxVol": "10000000",
                 "maintenanceMarginRate": "0.005", "liquidationFeeRate": "0.0004", "stopOnlyFair": False}]

    def ticker(self, symbol):
        return {"symbol": symbol, "bid1": "102.23", "ask1": "102.25", "lastPrice": "102.24",
                "amount24": "10000000", "timestamp": self.now * 1000, "fundingRate": "0"}

    def tickers(self):
        return [self.ticker("DEMO_USDT")]

    def candles(self, symbol, interval, count, now):
        return api_bars(self.hourly if interval == "Min60" else self.quarter)

    def depth(self, symbol):
        return {"asks": [["102.25", "1000000", 1]], "bids": [["102.23", "1000000", 1]], "timestamp": self.now * 1000}

    def funding(self, symbol):
        return {"symbol": symbol, "fundingRate": "0", "collectCycle": 8,
                "nextSettleTime": (self.now + 8 * 3600) * 1000, "timestamp": self.now * 1000}
