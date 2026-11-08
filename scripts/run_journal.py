from pathlib import Path
import os

from mexc_scanner.cli import main
from scripts.state_branch import restore, save


if __name__ == "__main__":
    directory = Path(".scanner-state")
    restore(directory)
    args = ["journal", os.environ["JOURNAL_ACTION"], "--event-id", os.environ["GITHUB_RUN_ID"]]
    for option, name in [("--plan-id", "PLAN_ID"), ("--variant", "VARIANT"), ("--price", "PRICE"),
                         ("--contracts", "CONTRACTS"), ("--fees", "FEES"), ("--funding", "FUNDING"),
                         ("--balance", "BALANCE"), ("--executed-at", "EXECUTED_AT")]:
        value = os.environ.get(name, "")
        if value:
            args.extend([option, value])
    outcome = main(args)
    if outcome:
        raise SystemExit(outcome)
    save(directory)
    notify_outcome = main(["notify"])
    save(directory)
    raise SystemExit(notify_outcome)
