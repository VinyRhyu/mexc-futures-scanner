from __future__ import annotations

import json
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from decimal import Decimal
from typing import Callable

from .models import D, DataError, seconds


class SourceError(RuntimeError):
    pass


class MexcClient:
    """Cliente exclusivamente GET para os endpoints públicos documentados."""

    def __init__(self, base: str = "https://api.mexc.com", timeout: int = 15,
                 transport: Callable | None = None):
        parsed = urllib.parse.urlsplit(base)
        if parsed.scheme != "https" or parsed.netloc != "api.mexc.com" or parsed.path not in {"", "/"}:
            raise DataError("Usar o host oficial documentado https://api.mexc.com")
        self.base, self.timeout = base.rstrip("/"), timeout
        self.transport = transport
        self._lock = threading.Lock()
        self._last_request = 0.0

    def _get(self, path: str, params: dict | None = None):
        if not path.startswith("/api/v1/contract/"):
            raise DataError("Endpoint não autorizado pelo coletor público")
        if any(x in path for x in ("private", "order", "account", "position", "transfer")):
            raise DataError("Este cliente não acessa negociação/conta")
        query = urllib.parse.urlencode(params or {})
        url = self.base + path + ("?" + query if query else "")
        last_error = ""
        for attempt in range(3):
            with self._lock:
                wait = 0.22 - (time.monotonic() - self._last_request)
                if wait > 0:
                    time.sleep(wait)
                self._last_request = time.monotonic()
            try:
                if self.transport:
                    payload = self.transport(path, params or {})
                else:
                    request = urllib.request.Request(url, headers={
                        "Accept": "application/json", "User-Agent": "mexc-futures-scanner/0.1"
                    }, method="GET")
                    with urllib.request.urlopen(request, timeout=self.timeout) as response:
                        raw = response.read(20_000_001)
                    if len(raw) > 20_000_000:
                        raise SourceError("Resposta excedeu o limite do coletor")
                    try:
                        payload = json.loads(raw, parse_float=Decimal)
                    except (ValueError, UnicodeError) as exc:
                        raise SourceError("A fonte retornou conteúdo não JSON (possível indisponibilidade/bloqueio)") from exc
                if not isinstance(payload, dict) or payload.get("success") is not True:
                    code = payload.get("code", "formato") if isinstance(payload, dict) else "formato"
                    raise SourceError(f"MEXC não confirmou sucesso: {code}")
                if "data" not in payload:
                    raise SourceError("Resposta sem campo data")
                return payload["data"]
            except urllib.error.HTTPError as exc:
                last_error = f"MEXC HTTP {exc.code}"
                if exc.code not in {429, 500, 502, 503, 504}:
                    raise SourceError(last_error) from None
                retry = exc.headers.get("Retry-After", "0")
                try:
                    delay = float(retry)
                except ValueError:
                    delay = 0
                if delay > 10:
                    raise SourceError(last_error + "; Retry-After excede esta rodada") from None
                time.sleep(max(delay, attempt + 1))
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                last_error = "Falha de conexão à MEXC: " + type(exc).__name__
                if attempt < 2:
                    time.sleep(attempt + 1)
        raise SourceError(last_error or "Falha na fonte")

    @staticmethod
    def _symbol(symbol: str) -> str:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.()\-]{0,79}_[A-Z0-9]+", symbol):
            raise DataError("Símbolo inválido")
        return urllib.parse.quote(symbol, safe="")

    def server_time(self) -> int:
        return seconds(self._get("/api/v1/contract/ping"))

    def contracts(self) -> list[dict]:
        data = self._get("/api/v1/contract/detail/country")
        if isinstance(data, dict):
            data = [data]
        if not isinstance(data, list) or not data:
            raise SourceError("Catálogo de contratos vazio/inválido")
        return data

    def tickers(self) -> list[dict]:
        data = self._get("/api/v1/contract/ticker")
        return data if isinstance(data, list) else [data]

    def ticker(self, symbol: str) -> dict:
        data = self._get("/api/v1/contract/ticker", {"symbol": symbol})
        if isinstance(data, list):
            data = next((d for d in data if d.get("symbol") == symbol), None)
        if not isinstance(data, dict) or data.get("symbol") != symbol:
            raise SourceError("Ticker de outro símbolo/ausente")
        return data

    def candles(self, symbol: str, interval: str, count: int, now: int) -> dict:
        intervals = {"Min1": 60, "Min15": 900, "Min60": 3600}
        if interval not in intervals or not 1 <= count <= 1900:
            raise DataError("Intervalo/quantidade não suportado")
        tf = intervals[interval]
        return self._get("/api/v1/contract/kline/" + self._symbol(symbol), {
            "interval": interval, "start": now - (count + 3) * tf, "end": now
        })

    def depth(self, symbol: str) -> dict:
        return self._get("/api/v1/contract/depth/" + self._symbol(symbol), {"limit": 50})

    def funding(self, symbol: str) -> dict:
        return self._get("/api/v1/contract/funding_rate/" + self._symbol(symbol))


def quote_is_fresh(ticker: dict, now: int, max_age: int) -> bool:
    try:
        ts = seconds(ticker["timestamp"])
        bid, ask = D(ticker["bid1"]), D(ticker["ask1"])
        return -10 <= now - ts <= max_age and 0 < bid <= ask
    except (KeyError, ValueError, DataError, TypeError):
        return False
