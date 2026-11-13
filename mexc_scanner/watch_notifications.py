"""Telegram-only alerts for a fresh observed M1 breakout; never changes a plan."""
from collections import defaultdict

from .models import stable_id
from .minute_breakout import STRATEGY, MAX_SIGNAL_AGE
from .reporting import movement_message
from .state import queue_message

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
    for p in plans:
        if (p.strategy != STRATEGY or p.terminal or now >= p.expires_at
                or p.symbol in viable_symbols
                or (verified_symbols is not None and p.symbol not in verified_symbols)):
            continue
        stage = phase(p)
        if stage == 2:
            continue  # A consolidation alone is not an observed movement.
        variant = p.variants['CONFIRMADA' if stage == 0 else 'ANTECIPADA']
        if not 0 <= now - variant.triggered_at < MAX_SIGNAL_AGE:
            continue
        groups[p.symbol].append(p)
    result = []
    for symbol, candidates in groups.items():
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
        v = chosen[0].variants['CONFIRMADA' if stage == 0 else 'ANTECIPADA']
        return -v.triggered_at, stage, symbol
    return sorted(result, key=notification_order)


def queue_waiting_entries(state, plans, config, now, viable_symbols, *, limit, verified_symbols=None):
    plans_by_id = {p.id: p for p in plans if p.strategy == STRATEGY}
    # Retire only pending individual M1 observations from the previous format.
    # Sent messages and all ENTRY messages retain their IDs and delivery history.
    for p in plans_by_id.values():
        old_ids = [stable_id(p.id, 'POSSIVEL')]
        old_ids += [stable_id(p.id, kind, 'OBSERVACAO') for kind in p.variants]
        for event_id in old_ids:
            m = state['outbox'].get(event_id)
            if m and m['status'] == 'PENDING' and m['category'] == 'INFO':
                m['status'] = 'EXPIRED'
    groups = grouped_candidates(plans, now, viable_symbols, verified_symbols)
    wanted = {symbol: stable_id('MOVEMENT_V1', symbol, chosen[0].side, stage,
                               chosen[0].variants['CONFIRMADA' if stage == 0 else 'ANTECIPADA'].triggered_at, config.mode)
              for stage, symbol, chosen in groups}
    for event_id, m in state['outbox'].items():
        symbol = m.get('watch_symbol')
        if symbol and m['status'] == 'PENDING' and wanted.get(symbol) != event_id:
            m['status'] = 'EXPIRED'
    count = 0
    for stage, symbol, chosen in groups:
        if count >= limit:
            break
        event_id = wanted[symbol]
        if event_id in state['outbox']:
            continue
        p = chosen[0]
        v = p.variants['CONFIRMADA' if stage == 0 else 'ANTECIPADA']
        expires = min(p.expires_at, v.triggered_at + MAX_SIGNAL_AGE)
        queue_message(state, event_id, movement_message(p, config.mode, now, stage, expires,
                                                       illustrative_leverage=config.minimum_leverage), now, expires)
        state['outbox'][event_id].update(watch_symbol=symbol, watch_stage=stage,
                                        movement_at=v.triggered_at, movement_side=p.side,
                                        plan_ids=[p.id for p in chosen])
        count += 1
    return count
