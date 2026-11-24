"""Telegram-only preparation and observed M1 alerts; never changes a plan."""
from collections import defaultdict

from .models import stable_id
from .minute_breakout import STRATEGY, MAX_SIGNAL_AGE
from .reporting import movement_candidate_message
from .state import queue_message

FIRST_CANDLE_NOTICE_AGE = 60


def notice_age(stage):
    return FIRST_CANDLE_NOTICE_AGE if stage == 1 else MAX_SIGNAL_AGE

def phase(plan):
    confirmed = plan.variants.get('CONFIRMADA')
    first = plan.variants.get('ANTECIPADA')
    if confirmed and confirmed.status == 'VALIDA':
        return 0  # Technical confirmation with a financial condition outstanding.
    if first and first.status == 'AGUARDANDO_CONFIRMACAO':
        return 1
    return 2


def grouped_candidates(plans, now, viable_symbols, verified_symbols=None):
    groups = defaultdict(list)
    observed_symbols = set()
    for p in plans:
        if (p.strategy != STRATEGY or p.terminal or now >= p.expires_at
                or p.symbol in viable_symbols
                or (verified_symbols is not None and p.symbol not in verified_symbols)):
            continue
        stage = phase(p)
        if stage == 2:
            if not p.variants:
                groups[p.symbol].append(p)
            continue
        observed_symbols.add(p.symbol)
        variant = p.variants['CONFIRMADA' if stage == 0 else 'ANTECIPADA']
        if not 0 <= now - variant.triggered_at < notice_age(stage):
            continue
        groups[p.symbol].append(p)
    result = []
    for symbol, candidates in groups.items():
        observed = [p for p in candidates if phase(p) < 2]
        if not observed:
            if symbol in observed_symbols:
                continue  # Do not replace an aging movement with a neutral watch.
            latest = max(p.formed_at for p in candidates)
            candidates = [p for p in candidates if p.formed_at == latest]
            sides = {}
            for p in sorted(candidates, key=lambda p: p.id):
                sides[p.side] = p
            result.append((2, symbol, [sides[s] for s in ('LONG', 'SHORT') if s in sides]))
            continue
        candidates = observed
        def recency(p):
            v = p.variants['CONFIRMADA' if phase(p) == 0 else 'ANTECIPADA']
            return v.triggered_at, p.formed_at
        latest = max(map(recency, candidates))
        candidates = [p for p in candidates if recency(p) == latest]
        stage = min(map(phase, candidates))
        candidates = [p for p in candidates if phase(p) == stage]
        if len({p.side for p in candidates}) != 1:
            continue  # Do not invent a direction for tied contradictory contexts.
        chosen = [max(candidates, key=lambda p: p.id)]
        result.append((stage, symbol, chosen))
    def notification_order(group):
        stage, symbol, chosen = group
        if stage == 2:
            return 1, -max(p.formed_at for p in chosen), stage, symbol
        v = chosen[0].variants['CONFIRMADA' if stage == 0 else 'ANTECIPADA']
        return 0, -v.triggered_at, stage, symbol
    return sorted(result, key=notification_order)


def queue_waiting_entries(state, plans, config, now, viable_symbols, *, limit, verified_symbols=None):
    """Notify ONLY first observed M1 with a possible entry; never preparations.

    Confirmed+financially viable plans are handled by ENTRY in the engine.
    Confirmed+blocked plans are not an actionable movement and stay in logs.
    """
    for p in plans:
        if p.strategy != STRATEGY:
            continue
        old_ids = [stable_id(p.id, "POSSIVEL")]
        old_ids += [stable_id(p.id, kind, "OBSERVACAO") for kind in p.variants]
        for event_id in old_ids:
            m = state["outbox"].get(event_id)
            if m and m["status"] == "PENDING":
                m["status"] = "EXPIRED"

    groups = [(stage, symbol, chosen)
              for stage, symbol, chosen in
              grouped_candidates(plans, now, viable_symbols, verified_symbols)
              if stage == 1]
    wanted = {
        symbol: stable_id("MOVEMENT_V1", symbol, chosen[0].side, 1,
                          chosen[0].variants["ANTECIPADA"].triggered_at, config.mode)
        for _, symbol, chosen in groups
    }
    # Suppress old preparation, blocked confirmation and verbose movement rows
    # already persisted in the existing state branch (preserve sent history).
    for m in state["outbox"].values():
        if m["status"] != "PENDING" or not m.get("watch_symbol"):
            continue
        if (m.get("notification_format") != "movement_only_v2" or
                wanted.get(m["watch_symbol"]) != m["id"]):
            m["status"] = "EXPIRED"

    count = 0
    for _, symbol, chosen in groups:
        if count >= limit:
            break
        event_id = wanted[symbol]
        if event_id in state["outbox"]:
            continue
        plan = chosen[0]
        first = plan.variants["ANTECIPADA"]
        expires = min(plan.expires_at, first.triggered_at + FIRST_CANDLE_NOTICE_AGE)
        text = movement_candidate_message(plan)
        if not text:
            continue
        queue_message(state, event_id, text, now, expires)
        state["outbox"][event_id].update(
            notification_format="movement_only_v2",
            watch_symbol=symbol, watch_stage=1, plan_ids=[plan.id],
            movement_at=first.triggered_at, movement_side=plan.side)
        count += 1
    return count
