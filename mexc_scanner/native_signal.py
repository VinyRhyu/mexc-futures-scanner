"""Paper signals derived from the scanner's confirmed market plans."""

from .external_signal import TARGET_STEP, evaluate
from .minute_breakout import STRATEGY
from .models import D


def screen_native_plans(plans, now):
    candidates = {}
    for plan in plans:
        variant = plan["variants"].get("CONFIRMADA")
        if (plan["strategy"] != STRATEGY or plan["status"] != "ATIVO"
                or not variant or variant["status"] != "VALIDA"
                or not variant["triggered_at"] <= now < plan["expires_at"]):
            continue
        symbol, side, trigger = plan["symbol"], plan["side"], variant["triggered_at"]
        row = {"contrato": symbol, "direcao": side, "confirmado_em": trigger,
               "plano": plan["id"], "status": "DESCARTADO", "motivos": []}
        financial = variant["financial"]
        if financial.get("status") not in {"VIAVEL_SIMULADO", "VIAVEL_REAL"}:
            row["motivos"] = ["PLANO_FINANCEIRO_INDISPONIVEL"]
        else:
            try:
                entry = D(financial["worst_entry"])
                tp1 = D(variant["target"])
                leverage = int(financial["leverage"])
                direction = 1 if side == "LONG" else -1
                anchor = tp1 / (1 + direction * TARGET_STEP)
                targets = (tp1,) + tuple(anchor * (1 + direction * TARGET_STEP * step)
                                         for step in (2, 3, 4))
                row.update(evaluate(side, leverage, entry, targets),
                           alavancagem=leverage, alvos_projetados=targets)
                if not row["motivos"]:
                    row["status"] = "ELEGIVEL_EM_SIMULACAO"
            except (KeyError, TypeError, ValueError):
                row["motivos"] = ["NIVEIS_DO_PLANO_INDISPONIVEIS"]
        key = (symbol, side, trigger)
        score = (
            row["status"] == "ELEGIVEL_EM_SIMULACAO",
            row.get("retorno_sobre_risco", D("-999999")),
            plan["id"],
        )
        if key not in candidates or score > candidates[key][0]:
            candidates[key] = (score, row)
    return {"modo": "SIMULACAO", "candidatos": [row for _, row in candidates.values()]}
