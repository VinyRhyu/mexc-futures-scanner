"""Own-clock timings and an append-only, price-only decision ledger.

No message contents, account balances, Telegram identifiers or remote errors are
accepted by the ledger. It is written before the existing serialized Git save.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time


def utc(timestamp):
    return datetime.fromtimestamp(timestamp, timezone.utc).isoformat()


def run_context():
    return {"run_id": os.environ.get("GITHUB_RUN_ID", "local"),
            "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT", "1"),
            "commit": os.environ.get("GITHUB_SHA", "local")}


class Timings:
    def __init__(self, *, clock=time.time, monotonic=time.monotonic, emit=None):
        self.clock, self.monotonic = clock, monotonic
        self.emit = emit or (lambda row: print(json.dumps(row), flush=True))
        self.rows = []

    @contextmanager
    def phase(self, name):
        started, tick = self.clock(), self.monotonic()
        common = {"telemetry": "phase_v1", "phase": name, **run_context()}
        self.emit({**common, "event": "start", "at_utc": utc(started)})
        status, error_type = "OK", None
        try:
            yield
        except BaseException as exc:
            status, error_type = "ERROR", type(exc).__name__
            raise
        finally:
            finished = self.clock()
            row = {**common, "event": "end", "started_at_utc": utc(started),
                   "finished_at_utc": utc(finished),
                   "duration_s": round(max(0, self.monotonic() - tick), 6),
                   "status": status}
            if error_type:
                row["error_type"] = error_type
            self.rows.append(row)
            self.emit(row)


class DecisionLog:
    FIELDS = frozenset({"plan_id", "variant", "symbol", "side", "strategy",
        "signal_at", "observed_at", "expires_at", "plan_status", "variant_status",
        "reason", "entry_low", "entry_high", "stop", "target", "financial",
        "event_id", "created_at", "quote_at", "attempt", "status", "sent_at",
        "failure_type", "decision_at", "last_price", "fair_price", "bid", "ask",
        "book_at", "funding_rate", "funding_next_at"})
    FINANCIAL_FIELDS = frozenset({"status", "reasons", "quote_at", "entry_vwap",
        "net_rr", "costs_usdt", "loss_usdt", "gain_usdt", "fee_rate",
        "funding_cost_rate", "leverage", "contract_size", "contracts", "evaluated_at"})

    def __init__(self, directory, *, mode, fingerprint, clock=time.time):
        self.directory, self.mode = Path(directory), mode
        self.fingerprint, self.clock, self.pending = fingerprint, clock, []

    def record(self, event, **fields):
        unknown = fields.keys() - self.FIELDS
        if unknown:
            raise ValueError("Unapproved decision ledger field")
        fields = dict(fields)
        if "financial" in fields:
            fields["financial"] = {k: v for k, v in fields["financial"].items()
                                   if k in self.FINANCIAL_FIELDS}
        from .models import jsonable
        self.pending.append({"schema": "decision_v1", "event": event,
            "recorded_at_utc": utc(self.clock()), **run_context(),
            "mode": self.mode, "config_fingerprint": self.fingerprint, **jsonable(fields)})

    def flush(self):
        if not self.pending:
            return
        self.directory.mkdir(parents=True, exist_ok=True)
        day = utc(self.clock())[:10]
        path = self.directory / ("decisions-" + day + ".jsonl")
        # One writer is enforced by the workflow and the existing state lock.
        # Batched fsync avoids adding a sync for each individual decision.
        from .models import jsonable
        payload = "".join(json.dumps(jsonable(r), ensure_ascii=False, sort_keys=True)
                          + "\n" for r in self.pending)
        with path.open("a") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        self.pending.clear()


def record_plan(observer, event, plan, variant, at, **extra):
    if observer is None:
        return
    observer(event, plan_id=plan.id, variant=variant.kind, symbol=plan.symbol,
        side=plan.side, strategy=plan.strategy, signal_at=variant.triggered_at,
        observed_at=at, expires_at=plan.expires_at, plan_status=plan.status,
        variant_status=variant.status, reason=plan.reason,
        entry_low=variant.entry_low, entry_high=variant.entry_high,
        stop=variant.stop, target=variant.target, **extra)


def record_source_gate(observer, row, at):
    if observer is None or row['status'] in {'INVALIDADO', 'EXPIRADO', 'AMBIGUO', 'EVENTO_PASSADO'}:
        return
    from .models import Plan
    plan = Plan.from_dict(row)
    for variant in plan.variants.values():
        if variant.triggered_at:
            record_plan(observer, 'source_gate', plan, variant, at, financial=variant.financial)
