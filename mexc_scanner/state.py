from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile

from .config import Config
from .models import D, DataError, jsonable, stable_id


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise DataError("Estado com chaves duplicadas")
        result[key] = value
    return result


def initial_state(config: Config) -> dict:
    return {"schema_version": 1, "config_fingerprint": config.fingerprint, "mode": config.mode,
            "wallet": {"balance": config.initial_balance, "pending": None, "position": None,
                       "pause_until": 0, "review_required": False},
            "plans": {}, "cursors": {}, "outbox": {}, "journal": [], "journal_ids": [],
            "last_summary_date": "", "last_success": 0, "source_status": "NAO_TESTADO"}


def load_state(path: str | Path, config: Config, initialize: bool = False) -> dict:
    p = Path(path)
    if not p.exists():
        if initialize and config.mode == "paper":
            return initial_state(config)
        raise DataError("Estado ausente. Inicialização explícita só é permitida em simulação")
    try:
        data = json.loads(p.read_text(), object_pairs_hook=_unique_pairs)
    except (ValueError, OSError) as exc:
        raise DataError("Estado não pôde ser recuperado; não reinicializado") from exc
    required = {"wallet", "plans", "cursors", "outbox", "journal", "journal_ids"}
    if data.get("schema_version") != 1 or not required <= data.keys():
        raise DataError("Esquema de estado incompatível/incompleto")
    if data.get("config_fingerprint") != config.fingerprint or data.get("mode") != config.mode:
        raise DataError("Configuração mudou. Migrar o estado explicitamente antes de prosseguir")
    if D(data["wallet"]["balance"]) < 0:
        raise DataError("Saldo negativo no estado")
    return data


def atomic_json(path: str | Path, data: dict) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=".state-", dir=target.parent)
    try:
        with os.fdopen(fd, "w") as output:
            json.dump(jsonable(data), output, ensure_ascii=False, indent=2, sort_keys=True)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(temp, target)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def queue_message(state: dict, event_id: str, text: str, now: int, expires_at: int,
                  category: str = "INFO", quote_at: int = 0) -> None:
    previous = state["outbox"].get(event_id)
    if previous and previous["status"] in {"SENT", "EXPIRED"}:
        return
    state["outbox"][event_id] = {"id": event_id, "text": text, "created_at": now,
        "expires_at": expires_at, "category": category, "quote_at": quote_at,
        "status": "PENDING", "attempts": (previous or {}).get("attempts", 0)}


def journal_event(state: dict, config: Config, action: str, event_id: str, now: int,
                  plan_id: str = "", variant: str = "ANTECIPADA", price: str = "0",
                  contracts: str = "0", contract_size: str = "0", fees: str = "0",
                  funding: str = "0", balance: str = "0", repository_private: bool = False,
                  executed_at: int | None = None) -> dict:
    if config.mode == "real" and not repository_private:
        raise DataError("Diário real exige armazenamento privado confirmado")
    if not event_id or len(event_id) > 100:
        raise DataError("Identificação da operação ausente/inválida")
    if event_id in state["journal_ids"]:
        return {"status": "ALREADY_RECORDED", "event_id": event_id}
    actual_time = now if executed_at is None else executed_at
    if type(actual_time) is not int or actual_time <= 0 or actual_time > now + 60:
        raise DataError("Horário real inválido ou futuro")
    wallet = state["wallet"]
    before = D(wallet["balance"])
    fee, fund = D(fees), D(funding)
    if fee < 0:
        raise DataError("Taxas devem ser zero ou positivas")
    entry = {"event_id": event_id, "action": action, "recorded_at": now, "mode": config.mode,
             "balance_before": before, "plan_id": plan_id, "fees_usdt": fee, "funding_usdt": fund,
             "executed_at": actual_time,
             "time_source": "INFORMADO" if executed_at is not None else "HORARIO_DO_REGISTRO"}
    if action == "skip":
        if wallet.get("position"):
            raise DataError("Não declarar ausência de execução enquanto há posição registrada")
        if wallet.get("pending") and wallet["pending"]["plan_id"] != plan_id:
            raise DataError("Plano não corresponde à indicação aguardando registro")
        wallet["pending"] = None
    elif action == "enter":
        if wallet.get("position"):
            raise DataError("Já existe uma posição registrada")
        if plan_id not in state["plans"] or variant not in state["plans"][plan_id]["variants"]:
            raise DataError("Plano/modalidade não encontrados")
        p = state["plans"][plan_id]
        v = p["variants"][variant]
        actual_price, volume = D(price), D(contracts)
        size = D(v.get("financial", {}).get("contract_size", contract_size))
        if min(actual_price, volume, size) <= 0 or fee >= before:
            raise DataError("Preço, quantidade, tamanho ou taxa inválidos")
        projected = v.get("financial", {})
        deviations = []
        if not D(v["entry_low"]) <= actual_price <= D(v["entry_high"]):
            deviations.append("ENTRADA_FORA_DA_FAIXA")
        if actual_time >= p["expires_at"]:
            deviations.append("EXECUCAO_APOS_VALIDADE")
        if actual_time < v["triggered_at"]:
            deviations.append("EXECUCAO_ANTES_DO_GATILHO")
        wallet["position"] = {"plan_id": plan_id, "variant": variant, "side": p["side"],
            "entry": actual_price, "contracts": volume, "contract_size": size,
            "entry_fee": fee, "entered_at": actual_time, "balance_before": before,
            "planned_risk": projected.get("loss_usdt", before * D(config.risk_fraction)),
            "stop": v["stop"], "target": v["target"], "deviations": deviations}
        wallet["balance"] = str(before - fee)
        wallet["pending"] = None
        entry.update(wallet["position"])
    elif action == "close":
        pos = wallet.get("position")
        if not pos:
            raise DataError("Não existe posição registrada")
        if plan_id and pos["plan_id"] != plan_id:
            raise DataError("Plano de fechamento diferente da posição aberta")
        if actual_time < pos["entered_at"]:
            raise DataError("Saída anterior à entrada registrada")
        actual_price = D(price)
        if actual_price <= 0:
            raise DataError("Preço de saída inválido")
        sign = 1 if pos["side"] == "LONG" else -1
        quantity = D(pos["contracts"]) * D(pos["contract_size"])
        gross = sign * quantity * (actual_price - D(pos["entry"]))
        net_total = gross - D(pos["entry_fee"]) - fee - fund
        after = max(D("0"), before + gross - fee - fund)
        original_balance = D(pos["balance_before"])
        full_budget = D(pos["planned_risk"]) >= D("0.95") * D(config.risk_fraction) * original_balance
        stopped = actual_price <= D(pos["stop"]) if sign == 1 else actual_price >= D(pos["stop"])
        if net_total <= -D(config.risk_fraction) * original_balance or (stopped and full_budget):
            wallet["pause_until"] = actual_time + 86400
        wallet["balance"], wallet["position"] = str(after), None
        wallet["review_required"] = after >= D(config.phase_target)
        entry.update({"plan_id": pos["plan_id"], "exit": actual_price, "gross_usdt": gross,
                      "net_usdt": net_total, "return_fraction": net_total / original_balance,
                      "balance_after": after, "position": pos})
    elif action == "balance":
        if wallet.get("position") or wallet.get("pending"):
            raise DataError("Reconciliação de saldo exige posição e indicação resolvidas")
        after = D(balance)
        if after < 0:
            raise DataError("Saldo negativo")
        wallet["balance"] = str(after)
        wallet["review_required"] = after >= D(config.phase_target)
        entry.update({"balance_after": after, "adjustment_usdt": after - before,
                      "classification": "RECONCILIACAO_NAO_E_LUCRO"})
    else:
        raise DataError("Ação de registro desconhecida")
    entry = jsonable(entry)
    state["journal"].append(entry)
    state["journal_ids"].append(event_id)
    return entry
