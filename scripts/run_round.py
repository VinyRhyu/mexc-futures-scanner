"""Uma rodada: recuperar, analisar, persistir, avisar e persistir confirmações."""
from pathlib import Path
import argparse
import os

from mexc_scanner.cli import main
from mexc_scanner.observability import Timings
from scripts.state_branch import restore, save
from scripts.telegram_commands import process_commands
from mexc_scanner.telegram import TelegramError


def _run(limit: int, timings: Timings) -> int:
    directory = Path(".scanner-state")
    with timings.phase("restore"):
        restore(directory)
    marker = directory / "round-complete.marker"
    marker.unlink(missing_ok=True)
    args = ["scan", "--limit", str(limit), "--migrate-rr-one", "--migrate-leverage-ten"]
    if (directory / "new-state.marker").exists():
        args.append("--init")
    with timings.phase("scan"):
        outcome = main(args)
    if not marker.exists():
        raise RuntimeError("Análise não concluiu com estado validado; envio cancelado")
    with timings.phase("persist_before_notify"):
        save(directory)
    with timings.phase("notify"):
        notify_outcome = main(["notify"])
    with timings.phase("persist_after_notify"):
        save(directory)
    try:
        with timings.phase("telegram_commands"):
            answered = process_commands(directory, os.environ.get("TELEGRAM_BOT_TOKEN", ""),
                                        os.environ.get("TELEGRAM_CHAT_ID", ""))
        if answered:
            print({"telegram_help_responses": answered})
        with timings.phase("persist_after_commands"):
            save(directory)
    except TelegramError as exc:
        # Uma falha no comando não invalida o scan nem os alertas enviados.
        print({"telegram_commands_error": str(exc)})
        with timings.phase("persist_after_command_error"):
            save(directory)
    report = directory / "latest/report.md"
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary and report.exists():
        with open(summary, "a") as output:
            output.write(report.read_text())
    return max(outcome, notify_outcome)


def run(limit: int) -> int:
    timings = Timings()
    with timings.phase("round"):
        return _run(limit, timings)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=50, choices=range(1, 51))
    args = parser.parse_args()
    raise SystemExit(run(args.limit))
