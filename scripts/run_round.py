"""Uma rodada: recuperar, analisar, persistir, avisar e persistir confirmações."""
from pathlib import Path
import argparse
import os

from mexc_scanner.cli import main
from scripts.state_branch import restore, save
from scripts.telegram_commands import process_commands
from mexc_scanner.telegram import TelegramError


def run(limit: int) -> int:
    directory = Path(".scanner-state")
    restore(directory)
    marker = directory / "round-complete.marker"
    marker.unlink(missing_ok=True)
    args = ["scan", "--limit", str(limit), "--migrate-rr-one"]
    if (directory / "new-state.marker").exists():
        args.append("--init")
    outcome = main(args)
    if not marker.exists():
        raise RuntimeError("Análise não concluiu com estado validado; envio cancelado")
    save(directory)
    notify_outcome = main(["notify"])
    save(directory)
    try:
        answered = process_commands(directory, os.environ.get("TELEGRAM_BOT_TOKEN", ""),
                                    os.environ.get("TELEGRAM_CHAT_ID", ""))
        if answered:
            print({"telegram_help_responses": answered})
        save(directory)
    except TelegramError as exc:
        # Uma falha no comando não invalida o scan nem os alertas enviados.
        print({"telegram_commands_error": str(exc)})
        save(directory)
    report = directory / "latest/report.md"
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary and report.exists():
        with open(summary, "a") as output:
            output.write(report.read_text())
    return max(outcome, notify_outcome)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=50, choices=range(1, 51))
    args = parser.parse_args()
    raise SystemExit(run(args.limit))
