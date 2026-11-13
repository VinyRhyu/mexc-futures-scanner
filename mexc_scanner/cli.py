from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime
import json
import os
from pathlib import Path
import sys
import time

from .config import load_config
from .demo import DemoClient
from .engine import run_scan
from .mexc import MexcClient
from .models import DataError, jsonable
from .reporting import markdown_report
from .state import atomic_json, initial_state, journal_event, load_state, queue_message
from .telegram import drain_outbox


@contextmanager
def state_lock(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = Path(str(path) + ".lock")
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise DataError("Outra operação usa o estado; verificar o processo antes de remover o lock") from exc
    try:
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        yield
    finally:
        lock.unlink(missing_ok=True)


def write_report(directory: Path, report: dict, snapshot: dict | None = None):
    directory.mkdir(parents=True, exist_ok=True)
    atomic_json(directory / "report.json", report)
    (directory / "report.md").write_text(markdown_report(report))
    if snapshot is not None:
        atomic_json(directory / "snapshot.json", snapshot)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Scanner MEXC: dados públicos, sem envio de ordens")
    parser.add_argument("--config", default="config/default.toml")
    sub = parser.add_subparsers(dest="command", required=True)
    scan = sub.add_parser("scan", help="Coletar dados reais e avaliar regras")
    scan.add_argument("--state", default=".scanner-state/state.json")
    scan.add_argument("--output", default=".scanner-state/latest")
    scan.add_argument("--init", action="store_true", help="Criar estado novo, somente paper")
    scan.add_argument("--limit", type=int, default=0)
    scan.add_argument("--migrate-rr-one", action="store_true",
                      help="Migrar somente paper de RR mínimo 2 para 1, preservando diário e níveis")
    scan.add_argument('--model',choices=['legacy','m1_volume50_v1'],
                      default=os.environ.get('SCANNER_STRATEGY','legacy'))
    demo = sub.add_parser("demo", help="Executar exemplo SINTÉTICO sem conexão à MEXC")
    demo.add_argument("--output", default="reports/demo")
    notify = sub.add_parser("notify", help="Entregar outbox já persistida; não coleta preços")
    notify.add_argument("--state", default=".scanner-state/state.json")
    journal = sub.add_parser("journal", help="Registrar manualmente uma execução/saída")
    journal.add_argument("action", choices=["enter", "skip", "close", "balance"])
    journal.add_argument("--state", default=".scanner-state/state.json")
    journal.add_argument("--event-id", required=True)
    journal.add_argument("--plan-id", default="")
    journal.add_argument("--variant", default="ANTECIPADA", choices=["ANTECIPADA", "CONFIRMADA"])
    journal.add_argument("--price", default="0")
    journal.add_argument("--contracts", default="0")
    journal.add_argument("--contract-size", default="0")
    journal.add_argument("--fees", default="0")
    journal.add_argument("--funding", default="0")
    journal.add_argument("--balance", default="0")
    journal.add_argument("--executed-at", default="", help="ISO 8601 com fuso; vazio usa horário do registro")
    replay = sub.add_parser("replay", help="Simular uma captura salva, com custos explicitamente assumidos")
    replay.add_argument("snapshot")
    replay.add_argument("--output", default="reports/replay")
    args = parser.parse_args(argv)
    try:
        config = load_config(args.config)
        now = int(time.time())
        if args.command == "demo":
            if config.mode != "paper":
                raise DataError("Demo só existe em modo paper")
            client = DemoClient(now)
            state = initial_state(config)
            report, snapshot = run_scan(client, config, state, {"DEMO"}, now=client.now)
            report["data_origin"] = "SINTETICO_NAO_E_MERCADO"
            snapshot["source"] = "SYNTHETIC_DEMO"
            report["source_status"] += "_DEMO_SINTETICO"
            for msg in state["outbox"].values():
                msg["text"] = "DEMONSTRAÇÃO SINTÉTICA — NÃO OPERAR\n" + msg["text"]
            write_report(Path(args.output), report, snapshot)
            atomic_json(Path(args.output) / "state.json", state)
            print(json.dumps({"status": "DEMO_SINTETICO", "plans": len(report["plans"]), "output": args.output}))
            return 0
        if args.command == "replay":
            from .replay import replay_snapshot
            result = replay_snapshot(json.loads(Path(args.snapshot).read_text()), config)
            Path(args.output).mkdir(parents=True, exist_ok=True)
            atomic_json(Path(args.output) / "replay.json", result)
            (Path(args.output) / "replay.md").write_text(result["markdown"])
            print(json.dumps({"status": "SIMULACAO_COM_HIPOTESES", "output": args.output}))
            return 0
        path = Path(args.state)
        with state_lock(path):
            state = load_state(path, config, getattr(args, "init", False),
                               migrate_rr_one=getattr(args, "migrate_rr_one", False), migration_at=now)
            if config.mode == "real" and os.environ.get("REPOSITORY_IS_PRIVATE", "").lower() != "true":
                raise DataError("Modo real exige destino privado confirmado")
            if args.command == "scan":
                assets = set(json.loads(Path("config/crypto-assets.json").read_text())["assets"])
                report, snapshot = run_scan(MexcClient(config.api_base), config, state, assets,
                                            symbol_limit=args.limit or None,signal_model=args.model)
                atomic_json(path, state)
                write_report(Path(args.output), report, snapshot)
                (path.parent / "round-complete.marker").write_text(str(report["analyzed_at"]))
                print(json.dumps({"source_status": report["source_status"],
                                  "coverage": f"{report['analyzed_symbols']}/{report['selected_symbols']}",
                                  "plans": len(report["plans"]), "error": report.get("error")}))
                return 1 if report["source_status"] == "FALHA" else 0
            if args.command == "notify":
                result = drain_outbox(state, now, os.environ.get("TELEGRAM_BOT_TOKEN", ""),
                                      os.environ.get("TELEGRAM_CHAT_ID", ""))
                atomic_json(path, state)
                print(json.dumps(result))
                return 1 if result["failed"] else 0
            executed_at = None
            if args.executed_at:
                stamp = datetime.fromisoformat(args.executed_at.replace("Z", "+00:00"))
                if stamp.tzinfo is None:
                    raise DataError("Informe o fuso no horário real, por exemplo -03:00")
                executed_at = int(stamp.timestamp())
            result = journal_event(state, config, args.action, args.event_id, now,
                plan_id=args.plan_id, variant=args.variant, price=args.price, contracts=args.contracts,
                contract_size=args.contract_size, fees=args.fees, funding=args.funding, balance=args.balance,
                repository_private=os.environ.get("REPOSITORY_IS_PRIVATE", "").lower() == "true",
                executed_at=executed_at)
            queue_message(state, "journal:" + args.event_id,
                          f"DIÁRIO | {config.mode.upper()} | {args.action}\nID: {args.event_id}\nSaldo registrado: {state['wallet']['balance']} USDT.",
                          now, now + 3600)
            atomic_json(path, state)
            print(json.dumps(jsonable(result), ensure_ascii=False))
            return 0
    except (DataError, OSError, ValueError) as exc:
        print(json.dumps({"status": "ERROR", "message": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
