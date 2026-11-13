from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import tomllib

from .models import D, DataError, stable_id


@dataclass(frozen=True)
class Config:
    mode: str = "paper"
    universe_size: int = 50
    minimum_turnover: str = "5000000"
    hourly_bars: int = 240
    quarter_bars: int = 480
    atr_period: int = 14
    ttl_seconds: int = 1800
    max_leverage: int = 20
    risk_fraction: str = "0.30"
    gain_fraction: str = "0.60"
    minimum_rr: str = "2"
    taker_fee: str = "0.0006"
    fees_verified: bool = False
    account_rules_verified: bool = False
    fair_trigger_verified: bool = False
    slippage_rate: str = "0.0002"
    funding_hours: int = 6
    assumed_funding_cycle: int = 8
    max_cost_fraction: str = "0.10"
    liquidation_buffer: str = "1.5"
    quote_max_age: int = 120
    initial_balance: str = "1"
    phase_target: str = "100"
    replay_bars: int = 16
    max_alerts: int = 6
    api_base: str = "https://api.mexc.com"

    def validate(self) -> Config:
        for field in ("fees_verified", "account_rules_verified", "fair_trigger_verified"):
            if not isinstance(getattr(self, field), bool):
                raise DataError(f"{field} deve ser booleano")
        if self.mode not in {"paper", "real"}:
            raise DataError("mode deve ser paper ou real")
        if not 1 <= self.universe_size <= 50 or not 1 <= self.max_leverage <= 20:
            raise DataError("Universo/alavancagem acima da especificação")
        if not 0 < D(self.risk_fraction) <= D("0.30"):
            raise DataError("Risco deve ser positivo e no máximo 30%")
        if D(self.gain_fraction) <= 0 or D(self.minimum_rr) < 1:
            raise DataError("Ganho/retorno-risco inválido")
        for field in ("taker_fee", "slippage_rate", "minimum_turnover", "max_cost_fraction"):
            if D(getattr(self, field)) < 0:
                raise DataError(f"{field} negativo")
        if not 0 <= D(self.taker_fee) < D("0.05"):
            raise DataError("Taxa inválida: informar fração, não porcentagem")
        if D(self.initial_balance) <= 0 or D(self.phase_target) <= 0:
            raise DataError("Saldo/meta inválidos")
        if self.ttl_seconds != 1800 or self.atr_period != 14:
            raise DataError("Mudança de regra requer nova versão da estratégia")
        if self.hourly_bars < 240 or self.quarter_bars < 480:
            raise DataError("Histórico abaixo da especificação")
        if self.assumed_funding_cycle < 1 or self.funding_hours < 1:
            raise DataError("Horizonte/ciclo inválido")
        if not 0 < self.quote_max_age <= 300 or not 1 <= self.replay_bars <= 480:
            raise DataError("Atualidade/reconciliação inválida")
        return self

    @property
    def fingerprint(self) -> str:
        return stable_id(asdict(self))


def load_config(path: str | Path) -> Config:
    data = tomllib.loads(Path(path).read_text())
    allowed = set(Config.__dataclass_fields__)
    unknown = set(data) - allowed
    if unknown:
        raise DataError("Configurações desconhecidas: " + ", ".join(sorted(unknown)))
    return Config(**data).validate()
