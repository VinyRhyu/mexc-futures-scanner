"""Telegram-only grouping of conditional M1 plans; never changes a plan."""
from collections import defaultdict

from .models import stable_id
from .minute_breakout import STRATEGY
from .reporting import waiting_entries_message
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
        groups[p.symbol].append(p)
    result = []
    for symbol, candidates in groups.items():
        stage = min(map(phase, candidates))
        candidates = [p for p in candidates if phase(p) == stage]
        if stage == 2:
            latest = max(p.formed_at for p in candidates)
            candidates = [p for p in candidates if p.formed_at == latest]
        sides = {}
        for p in candidates:
            recency = (p.entry_started_at, p.formed_at, p.id)
            if p.side not in sides or recency > (sides[p.side].entry_started_at, sides[p.side].formed_at, sides[p.side].id):
                sides[p.side] = p
        chosen = [sides[s] for s in ('LONG', 'SHORT') if s in sides]
        result.append((stage, symbol, chosen))
    return sorted(result, key=lambda x: (x[0], -max(p.formed_at for p in x[2]), x[1]))


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
    wanted = {symbol: stable_id('WAITING_ENTRY_V1', symbol, stage, sorted(p.id for p in chosen), config.mode)
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
        expires = min(p.expires_at for p in chosen)
        queue_message(state, event_id, waiting_entries_message(chosen, config.mode, now, stage), now, expires)
        state['outbox'][event_id].update(watch_symbol=symbol, watch_stage=stage,
                                        plan_ids=[p.id for p in chosen])
        count += 1
    return count
