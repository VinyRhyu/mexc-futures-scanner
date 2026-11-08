from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from decimal import Decimal, InvalidOperation, ROUND_CEILING, ROUND_FLOOR
from typing import Any
import hashlib
import json


class DataError(ValueError):
    pass


def D(value: Any) -> Decimal:
    if isinstance(value, bool):
        raise DataError("Booleano não é um número de mercado")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise DataError("Número inválido") from exc
    if not result.is_finite():
        raise DataError("Número não finito")
    return result


def ceil_step(value: Decimal, step: Decimal) -> Decimal:
    if step <= 0:
        raise DataError("Incremento deve ser positivo")
    return (value / step).to_integral_value(rounding=ROUND_CEILING) * step


def floor_step(value: Decimal, step: Decimal) -> Decimal:
    if step <= 0:
        raise DataError("Incremento deve ser positivo")
    return (value / step).to_integral_value(rounding=ROUND_FLOOR) * step


def seconds(value: Any) -> int:
    result = int(D(value))
    return result // 1000 if result > 100_000_000_000 else result


def jsonable(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if is_dataclass(value):
        return jsonable(asdict(value))
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(v) for v in value]
    return value


def stable_id(*values: Any) -> str:
    text = json.dumps(jsonable(values), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode()).hexdigest()[:20]


@dataclass(frozen=True)
class Candle:
    ts: int
    tf: int
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal = Decimal("0")

    @property
    def end(self) -> int:
        return self.ts + self.tf

    def validate(self) -> None:
        if self.tf <= 0 or self.ts % self.tf:
            raise DataError("Candle fora do alinhamento UTC")
        if min(self.open, self.high, self.low, self.close) <= 0:
            raise DataError("Preço não positivo")
        if self.high < max(self.open, self.close, self.low):
            raise DataError("Máxima inconsistente")
        if self.low > min(self.open, self.close, self.high) or self.volume < 0:
            raise DataError("Mínima/volume inconsistente")

    @classmethod
    def from_dict(cls, row: dict) -> Candle:
        return cls(int(row["ts"]), int(row["tf"]), *[D(row[k]) for k in
                   ("open", "high", "low", "close")], D(row.get("volume", 0)))


@dataclass(frozen=True)
class Pivot:
    kind: str
    price: Decimal
    ts: int
    known_at: int


@dataclass
class Variant:
    kind: str
    triggered_at: int
    reference: Decimal
    entry_low: Decimal
    entry_high: Decimal
    stop: Decimal
    target: Decimal
    target_origin: str
    status: str = "VALIDA"
    reason: str = ""
    financial: dict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, row: dict) -> Variant:
        data = dict(row)
        for k in ("reference", "entry_low", "entry_high", "stop", "target"):
            data[k] = D(data[k])
        return cls(**data)


@dataclass
class Plan:
    id: str
    symbol: str
    strategy: str
    side: str
    formed_at: int
    detected_at: int
    expires_at: int
    atr: Decimal
    level: Decimal
    lower: Decimal
    upper: Decimal
    stop: Decimal | None
    family: str
    status: str = "POSSIVEL"
    reaction_at: int = 0
    reaction_extreme: Decimal | None = None
    revision: int = 0
    last_bar: int = 0
    reason: str = ""
    variants: dict[str, Variant] = field(default_factory=dict)
    observations: list[str] = field(default_factory=list)
    preparation_expires_at: int = 0
    entry_started_at: int = 0

    def __post_init__(self):
        if not self.preparation_expires_at:
            self.preparation_expires_at = self.expires_at

    @property
    def terminal(self) -> bool:
        return self.status in {"INVALIDADO", "EXPIRADO", "AMBIGUO", "EVENTO_PASSADO"}

    @classmethod
    def from_dict(cls, row: dict) -> Plan:
        data = dict(row)
        for k in ("atr", "level", "lower", "upper", "stop", "reaction_extreme"):
            if data.get(k) is not None:
                data[k] = D(data[k])
        data["variants"] = {k: Variant.from_dict(v) for k, v in data.get("variants", {}).items()}
        return cls(**data)


@dataclass(frozen=True)
class Contract:
    symbol: str
    size: Decimal
    min_volume: Decimal
    volume_step: Decimal
    tick: Decimal
    max_leverage: int
    maintenance_rate: Decimal
    liquidation_fee: Decimal | None
    stop_only_fair: bool = False
    max_volume: Decimal = Decimal("1E20")
    tiers: tuple = ()

    @classmethod
    def from_api(cls, row: dict) -> Contract:
        max_l = int(row["maxLeverage"])
        regional = int(row.get("countryConfigContractMaxLeverage", 0) or 0)
        if regional > 0:
            max_l = min(max_l, regional)
        result = cls(str(row["symbol"]), D(row["contractSize"]), D(row["minVol"]),
                     D(row["volUnit"]), D(row["priceUnit"]), max_l,
                     D(row["maintenanceMarginRate"]),
                     D(row["liquidationFeeRate"]) if row.get("liquidationFeeRate") is not None else None,
                     bool(row.get("stopOnlyFair", False)), D(row.get("maxVol", "1E20")),
                     tuple(row.get("riskLimitCustom", [])))
        if min(result.size, result.min_volume, result.volume_step, result.tick) <= 0:
            raise DataError("Regras de contrato inválidas")
        if result.max_leverage < 1 or not (0 <= result.maintenance_rate < 1):
            raise DataError("Margem/alavancagem inválida")
        return result

    def margin_tier(self, contracts: Decimal) -> tuple[Decimal, int]:
        if self.tiers:
            valid = [t for t in self.tiers if D(t["maxVol"]) >= contracts]
            if not valid:
                raise DataError("Quantidade acima dos níveis de risco")
            tier = min(valid, key=lambda t: D(t["maxVol"]))
            rate, leverage = D(tier["mmr"]), min(self.max_leverage, int(tier["maxLeverage"]))
            if not 0 <= rate < 1 or leverage < 1:
                raise DataError("Nível de margem inválido")
            return rate, leverage
        return self.maintenance_rate, self.max_leverage
