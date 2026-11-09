"""Uma amostra fictícia do formato; sem MEXC, diário ou alteração da banca."""
from __future__ import annotations

import argparse
import os
import time

from mexc_scanner.config import Config
from mexc_scanner.demo import DemoClient
from mexc_scanner.engine import run_scan
from mexc_scanner.models import Plan
from mexc_scanner.reporting import plan_message
from mexc_scanner.state import initial_state
from mexc_scanner.telegram import send_text


def preview_message(now: int) -> str:
    config = Config()
    client = DemoClient(now)
    report, _ = run_scan(client, config, initial_state(config), {"DEMO"}, now=client.now)
    for row in report["plans"]:
        plan = Plan.from_dict(row)
        for variant in plan.variants.values():
            if not plan.terminal and variant.status == "VALIDA" and variant.financial.get("status") == "VIAVEL_SIMULADO":
                return ("EXEMPLO FICTÍCIO — NÃO OPERAR\nAtivo e preços inventados para testar o formato.\n\n" +
                        plan_message(plan, "paper", client.now, variant))
    raise RuntimeError("A demonstração não produziu uma amostra viável")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--send", action="store_true", help="Enviar UMA demonstração ao Telegram configurado")
    args = parser.parse_args()
    message = preview_message(int(time.time()))
    if args.send:
        send_text(os.environ.get("TELEGRAM_BOT_TOKEN", ""), os.environ.get("TELEGRAM_CHAT_ID", ""), message)
        print("Amostra fictícia do novo formato confirmada pelo Telegram. Nenhuma ordem executada.")
    else:
        print(message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
