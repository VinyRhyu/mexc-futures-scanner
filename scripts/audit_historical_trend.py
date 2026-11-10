"""Replay anterior à criação do scanner; filtro 1h fixo, sem ordens/alertas.

Recria eventos incrementalmente com janelas 480x15m e 240x1h. A geração não
recebe candles futuros. Desfechos são avaliados separadamente após congelar planos.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from zoneinfo import ZoneInfo

from mexc_scanner.config import load_config
from mexc_scanner.market import parse_candles, select_universe, structure
from mexc_scanner.mexc import MexcClient
from mexc_scanner.models import Contract, D, jsonable
from mexc_scanner.strategies import process_symbol
from scripts.audit_pullback import iso
from scripts.audit_rr import review


BRT = ZoneInfo('America/Sao_Paulo')


def midnight(date):
    return int(datetime.fromisoformat(date).replace(tzinfo=BRT).timestamp())


def collect_signals(symbol, quarter, hourly, contract, config, start, end):
    plans, cursor, records, seen = [], 0, [], set()
    for i, c in enumerate(quarter):
        if c.end < start or i < 479:
            continue
        if c.end >= end:
            break
        known_q = quarter[i - 479:i + 1]
        known_h = [bar for bar in hourly if bar.end <= c.end][-240:]
        if len(known_h) != 240:
            raise ValueError('Histórico de 1h insuficiente no replay')
        plans, cursor = process_symbol(symbol, known_q, known_h, plans, cursor,
                                       c.end + 1, contract.tick, config)
        for p in plans:
            if p.strategy != 'ROMPIMENTO':
                continue
            for kind, v in p.variants.items():
                signature = (p.id, kind)
                if signature in seen or v.triggered_at != c.end:
                    continue
                seen.add(signature)
                direction = structure(known_h, v.triggered_at)
                frozen = jsonable(p)
                frozen['variants'] = {'CONFIRMADA': jsonable(v)}
                records.append({'plan_id': p.id, 'symbol': symbol, 'kind': kind, 'side': p.side,
                    'signal': v.triggered_at, 'structure_1h': direction,
                    'aligned': direction == ('ALTA' if p.side == 'LONG' else 'BAIXA'),
                    'plan': frozen})
        # IDs contêm o instante de formação; planos terminais antigos não podem
        # reaparecer como novos. A poda só reduz memória/tempo do replay.
        plans = [p for p in plans if not p.terminal or p.formed_at >= c.end - 86400]
    return records


def summarize(records):
    out = {'candidates': len(records), 'structure_counts': dict(Counter(r['structure_1h'] for r in records)),
           'models': {}}
    for name, sample in [('ATUAL', records), ('FILTRO_1H', [r for r in records if r['aligned']])]:
        entries = [r['baseline'] for r in sample if 'entered_at' in r['baseline']]
        closed = [v for v in entries if 'net_r' in v]
        positive = sum((D(v['net_r']) for v in closed if D(v['net_r']) > 0), D(0))
        negative = -sum((D(v['net_r']) for v in closed if D(v['net_r']) < 0), D(0))
        total = sum((D(v['net_r']) for v in closed), D(0))
        targets = sum(v['outcome'] == 'ALVO' for v in closed)
        out['models'][name] = {'candidates': len(sample), 'entries': len(entries), 'closed': len(closed),
            'targets': targets, 'stops': sum(v['outcome'] in {'STOP', 'STOP_AMBIGUO'} for v in closed),
            'ambiguous': sum(v['outcome'] == 'STOP_AMBIGUO' for v in closed),
            'open': sum(v['outcome'] == 'ABERTO' for v in entries),
            'win_rate_closed': str(D(targets) / len(closed)) if closed else None,
            'closed_r_independent': str(total), 'mean_closed_r': str(total / len(closed)) if closed else None,
            'marked_r_independent': str(sum((D(v.get('net_r', v.get('mark_to_market_r', 0))) for v in entries), D(0))),
            'profit_factor_r': str(positive / negative) if negative else None,
            'blocked': dict(Counter(t for r in sample for t in r['baseline'].get('reasons', [])))}
    removed = [r['baseline'] for r in records if not r['aligned']]
    out['removed_winners'] = sum(v['outcome'] == 'ALVO' for v in removed)
    out['avoided_stops'] = sum(v['outcome'] in {'STOP', 'STOP_AMBIGUO'} for v in removed)
    return out


def replay_symbol(symbol, q, h, contract, config, start, end):
    records = collect_signals(symbol, q, h, contract, config, start, end)
    observed = end + 14400
    for r in records:
        r['baseline'] = review(r.pop('plan'), q, contract, config, observed, '2')
        r['day_brt'] = datetime.fromtimestamp(r['signal'], timezone.utc).astimezone(BRT).date().isoformat()
    return records


def run(start, end, limit=50, client=None):
    config = replace(load_config('config/default.toml'), mode='paper', fees_verified=False, account_rules_verified=False)
    if start >= end or start % 900 or end % 900:
        raise ValueError('Período inválido/alinhamento de candles')
    q_count = 480 + (end - start + 14400) // 900
    h_count = 240 + (end - start + 14400) // 3600
    if max(q_count, h_count) > 1900:
        raise ValueError('Dividir o histórico em blocos de até 14 dias')
    client = client or MexcClient(config.api_base)
    now = client.server_time()
    observed = end + 14400
    if observed + 10 > now:
        raise ValueError('Período de observação ainda não terminou')
    assets = set(json.loads(Path('config/crypto-assets.json').read_text())['assets'])
    catalog, tickers = client.contracts(), client.tickers()
    selected, _ = select_universe(catalog, tickers, assets, D(config.minimum_turnover), limit)
    rows, errors, datasets = [], {}, []
    for number, raw in enumerate(selected, 1):
        symbol = raw['symbol']
        try:
            c = Contract.from_api(raw)
            q = parse_candles(client.candles(symbol, 'Min15', q_count, observed + 10), 900, observed + 10, q_count)
            h = parse_candles(client.candles(symbol, 'Min60', h_count, observed + 10), 3600, observed + 10, h_count)
            records = replay_symbol(symbol, q, h, c, config, start, end)
            rows.extend(records)
            digest = hashlib.sha256(json.dumps(jsonable({'q': q, 'h': h}), sort_keys=True).encode()).hexdigest()
            datasets.append({'symbol': symbol, 'quarter_bars': len(q), 'hourly_bars': len(h), 'sha256': digest})
            print(json.dumps({'progress': f'{number}/{len(selected)}', 'symbol': symbol,
                              'signals': len(records), 'hypothetical_entries': sum('entered_at' in r['baseline'] for r in records)}), flush=True)
        except Exception as exc:
            errors[symbol] = {'type': type(exc).__name__, 'reason': str(exc)[:200]}
            print(json.dumps({'progress': f'{number}/{len(selected)}', 'symbol': symbol, 'error': errors[symbol]}), flush=True)
    summary = {kind: summarize([r for r in rows if r['kind'] == kind]) for kind in ('ANTECIPADA', 'CONFIRMADA')}
    daily = {day: {kind: summarize([r for r in rows if r['kind'] == kind and r['day_brt'] == day])
                   for kind in ('ANTECIPADA', 'CONFIRMADA')} for day in sorted({r['day_brt'] for r in rows})}
    limits = [
        'Hipótese de alinhamento 1h definida antes deste replay e mantida sem otimização após os resultados.',
        'O universo é o elegível HOJE, não a lista histórica de contratos/volumes. Há possível viés de sobrevivência/seleção.',
        'Regras de contratos e taxas atuais simuladas, não as regras pessoais ou históricas observadas.',
        'Geração incremental recebe apenas 480 candles 15m e 240 candles 1h já fechados, com níveis congelados ao aparecer.',
        'Filtro aplicado aos mesmos candidatos do baseline, após formação do gatilho. Não cria sinais substitutos.',
        'Entrada hipotética na abertura seguinte; taxa 0,06% por lado, spread 0,02%, slippage configurado ou dois ticks, funding zero e livro infinito.',
        'Mantém SL/TP, mínimo 2:1, referência independente 1 USDT, risco até 10%, lote e teto 20x.',
        'Observação de 4h por sinal, stop primeiro na ambiguidade e gaps adversos. Abertas são marcadas separadamente.',
        'Sinais podem se sobrepor. Antecipadas/confirmadas e soma R não representam carteira ou dinheiro realizado.',
        'Este replay histórico exploratório complementa, mas não substitui, o teste prospectivo já em andamento.'
    ]
    return jsonable({'kind': 'HISTORICAL_TREND_COMPARISON', 'start_brt': datetime.fromtimestamp(start, BRT).isoformat(),
        'end_exclusive_brt': datetime.fromtimestamp(end, BRT).isoformat(), 'observed_until': iso(observed),
        'collected_at': iso(now), 'selected_symbols': len(selected), 'analyzed_symbols': len(datasets),
        'summary': summary, 'daily': daily, 'errors': errors, 'datasets': datasets, 'limitations': limits,
        'trades': [r for r in rows if 'entered_at' in r['baseline']]})


def markdown(report):
    lines = ['## Histórico: rompimentos com e sem filtro de estrutura 1h', '',
        'Período (Brasília): ' + report['start_brt'] + ' até ' + report['end_exclusive_brt'] + ' (exclusivo).',
        f"Contratos completos: {report['analyzed_symbols']}/{report['selected_symbols']}.", '',
        '| Modalidade | Regra | Candidatos | Entradas | Alvos | Stops | Abertas | Acerto encerradas | R encerradas |',
        '| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
    for kind, s in report['summary'].items():
        for rule, v in s['models'].items():
            rate = f"{D(v['win_rate_closed']):.1%}" if v['win_rate_closed'] is not None else '—'
            lines.append(f"| {kind} | {rule} | {v['candidates']} | {v['entries']} | {v['targets']} | {v['stops']} | {v['open']} | {rate} | {D(v['closed_r_independent']):.3f} |")
    lines += ['', '### Limites', ''] + ['- ' + x for x in report['limitations']]
    lines += ['', '```json', json.dumps({k: report[k] for k in ('summary', 'daily', 'errors')}, ensure_ascii=False, indent=2), '```']
    return '\n'.join(lines) + '\n'


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--start', default='2026-11-01')
    parser.add_argument('--end', default='2026-11-08')
    parser.add_argument('--limit', type=int, default=50)
    args = parser.parse_args()
    report = run(midnight(args.start), midnight(args.end), args.limit)
    print('HISTORY_RESULT_BEGIN', flush=True)
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
    print('HISTORY_RESULT_END', flush=True)
    if path := os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(path, 'a') as out:
            out.write(markdown(report))
    if not report['analyzed_symbols']:
        raise SystemExit('Nenhum histórico completo disponível')
