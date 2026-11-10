"""Cronologia ETH de 10/11/2026, sem nova regra ou envio de ordens."""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime
import json
import os
from pathlib import Path
from zoneinfo import ZoneInfo

from mexc_scanner.config import load_config
from mexc_scanner.market import aggregate_two_hours, atr, parse_candles, pivots, structure
from mexc_scanner.mexc import MexcClient
from mexc_scanner.models import Contract, D, jsonable, stable_id
from mexc_scanner.strategies import process_symbol
from scripts.audit_pullback import paper_quote


BRT = ZoneInfo('America/Sao_Paulo')


def stamp(text):
    return int(datetime.fromisoformat(text).replace(tzinfo=BRT).timestamp())


def local(ts):
    return datetime.fromtimestamp(ts, BRT).isoformat()


def ema(candles, period):
    alpha = D(2) / (period + 1)
    value, result = candles[0].close, {}
    for c in candles:
        value = alpha * c.close + (1 - alpha) * value
        result[c.end] = value
    return result


def run(state):
    cfg, client = load_config('config/default.toml'), MexcClient()
    first, requested_start, end = map(stamp, ['2026-11-10T09:00:00', '2026-11-10T10:15:00', '2026-11-10T12:45:00'])
    if client.server_time() < end + 10:
        raise ValueError('O período ainda não terminou')
    q = parse_candles(client.candles('ETH_USDT', 'Min15', 544, end + 10), 900, end + 10, 544)
    h = parse_candles(client.candles('ETH_USDT', 'Min60', 264, end + 10), 3600, end + 10, 264)
    m = parse_candles(client.candles('ETH_USDT', 'Min1', 270, end + 10), 60, end + 10, 270)
    contract = Contract.from_api(next(c for c in client.contracts() if c['symbol'] == 'ETH_USDT'))
    em20, em50 = ema(q, 20), ema(q, 50)
    rows, events, plans, cursor, seen = [], [], [], 0, set()
    for i, c in enumerate(q):
        if c.end < first:
            continue
        past, hourly = q[max(0, i - 479):i + 1], [x for x in h if x.end <= c.end][-240:]
        prior4, prior8, prior20 = q[i-4:i], q[i-8:i], q[i-20:i]
        known = pivots(past, c.end)
        highs, lows = [p for p in known if p.kind == 'HIGH'], [p for p in known if p.kind == 'LOW']
        rows.append({'close_at': local(c.end), 'open': c.open, 'high': c.high, 'low': c.low, 'close': c.close,
            'ema20_15m': em20[c.end], 'ema50_15m': em50[c.end],
            'structure_1h': structure(hourly, c.end), 'structure_2h': structure(aggregate_two_hours(hourly), c.end),
            'prior_1h_low': min(x.low for x in prior4), 'prior_2h_low': min(x.low for x in prior8),
            'closed_below_prior_1h_low': c.close < min(x.low for x in prior4),
            'closed_below_prior_2h_low': c.close < min(x.low for x in prior8),
            'volume_vs_previous_20_mean': c.volume / (sum(x.volume for x in prior20)/20),
            'last_two_confirmed_highs_15m': [{'price': p.price, 'known_at': local(p.known_at)} for p in highs[-2:]],
            'last_confirmed_low_15m': {'price': lows[-1].price, 'known_at': local(lows[-1].known_at)} if lows else None})
        plans, cursor = process_symbol('ETH_USDT', past, hourly, plans, cursor, c.end + 1, contract.tick, cfg)
        for p in plans:
            for kind, v in p.variants.items():
                key = (p.id, kind)
                if key in seen or v.triggered_at != c.end:
                    continue
                seen.add(key)
                following = next((bar for bar in m if bar.ts == c.end), None)
                finance = paper_quote(p, v, contract, following.open, c.end + 1, cfg) if following else {'status': 'SEM_PRECO_POSTERIOR_DENTRO_DA_JANELA'}
                events.append({'signal': local(c.end), 'strategy': p.strategy, 'side': p.side, 'kind': kind,
                    'entry_low': v.entry_low, 'entry_high': v.entry_high, 'reference': v.reference,
                    'stop': v.stop, 'target': v.target, 'origin': v.target_origin, 'finance': finance})
    recorded = []
    for p in state.get('plans', {}).values():
        if p['symbol'] != 'ETH_USDT':
            continue
        for kind, v in p.get('variants', {}).items():
            if not first <= v['triggered_at'] <= end:
                continue
            messages = []
            for label, key in [('OBSERVACAO', stable_id(p['id'], kind, 'OBSERVACAO')),
                               ('GATILHO', stable_id(p['id'], kind, 'GATILHO', 'paper'))]:
                if msg := state.get('outbox', {}).get(key):
                    messages.append({'type': label, 'status': msg['status'], 'created_at': local(msg['created_at'])})
            recorded.append({'signal': local(v['triggered_at']), 'strategy': p['strategy'], 'side': p['side'], 'kind': kind,
                'reference': v['reference'], 'entry_low': v['entry_low'], 'entry_high': v['entry_high'], 'stop': v['stop'],
                'target': v['target'], 'origin': v['target_origin'], 'latest_financial': v.get('financial', {}), 'messages': messages})
    start_bar = next(c for c in m if c.ts == requested_start)
    later = [c for c in m if requested_start <= c.ts < end]
    return jsonable({'kind': 'ETH_INTRADAY_CASE', 'requested_start': local(requested_start), 'requested_end': local(end),
        'start_open': start_bar.open, 'end_close': later[-1].close, 'minimum': min(c.low for c in later),
        'minimum_at': local(min(later, key=lambda c:c.low).ts),
        'change_percent': (later[-1].close / start_bar.open - 1) * 100,
        'candles_15m': rows, 'candles_1h': [c for c in h if first-7200 <= c.end <= end],
        'reconstructed_events': events, 'recorded_events': recorded,
        'limitations': ['Preços de mercado são observados; fills, taxas e livro das entradas reconstruídas são hipóteses.',
            'EMAs, volumes e rompimentos de mínimas são descrições, não uma estratégia validada ou prova de previsão.',
            'Volume OHLC não identifica agressão compradora/vendedora.',
            'Estado registrado pode ter sido atualizado depois do sinal; status financeiro mais recente não é necessariamente o original.',
            'As regras do scanner e alertas não são alterados por esta auditoria.']})


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--state', required=True)
    args = parser.parse_args()
    r = run(json.loads(Path(args.state).read_text()))
    print('ETH_CASE_BEGIN')
    print(json.dumps(r, ensure_ascii=False, indent=2))
    print('ETH_CASE_END')
    if path := os.environ.get('GITHUB_STEP_SUMMARY'):
        lines = ['## ETH: 10h15–12h45, Brasília, 10/11/2026', '',
            '| Fechamento BRT | Abertura | Máxima | Mínima | Fechamento | EMA20 | Estrutura 1h | Perdeu mínima da hora anterior | Volume relativo |',
            '| --- | ---: | ---: | ---: | ---: | ---: | --- | --- | ---: |']
        for c in r['candles_15m']:
            lines.append('| ' + ' | '.join([c['close_at'], c['open'], c['high'], c['low'], c['close'],
                f"{D(c['ema20_15m']):.3f}", c['structure_1h'], str(c['closed_below_prior_1h_low']),
                f"{D(c['volume_vs_previous_20_mean']):.2f}"]) + ' |')
        lines += ['', '```json', json.dumps({k:r[k] for k in ('recorded_events','reconstructed_events','limitations')}, ensure_ascii=False, indent=2), '```']
        Path(path).write_text('\n'.join(lines))
