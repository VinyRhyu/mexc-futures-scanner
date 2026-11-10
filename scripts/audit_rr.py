"""Sensibilidade ao filtro RR em confirmações históricas; não altera o scanner.

Mesma entrada imediata, stop, alvo, custos e banca em todos os cenários.
O cenário zero remove o mínimo RR, mas exige ganho líquido estritamente positivo.
Configurações inferiores a 2 existem apenas neste teste isolado, sem validação/live.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
from dataclasses import replace
from datetime import datetime
import json
import os
from pathlib import Path

from mexc_scanner.config import Config, load_config
from mexc_scanner.market import parse_candles
from mexc_scanner.mexc import MexcClient
from mexc_scanner.models import Contract, D, Plan, jsonable
from scripts.audit_pullback import close_outcome, iso, paper_quote


THRESHOLDS = ('2', '1.5', '1', '0.5', '0')


def review(row, quarter, contract, config, observed_at, minimum_rr, horizon=14400):
    # replace não executa Config.validate(): exceção exclusivamente do teste.
    cfg = replace(config, mode='paper', minimum_rr=minimum_rr,
                  fees_verified=False, account_rules_verified=False)
    p = Plan.from_dict(row)
    v = deepcopy(p.variants['CONFIRMADA'])
    p.status, p.reason, v.status, v.reason, v.financial = 'ATIVO', '', 'VALIDA', '', {}
    start = v.triggered_at
    bars = [c for c in quarter if start <= c.ts < start + horizon and c.end <= observed_at]
    complete = bool(bars) and bars[-1].end >= start + horizon
    result = {'window_complete': complete}
    if not bars or bars[0].ts != start or any(a.end != b.ts for a, b in zip(bars, bars[1:])):
        return dict(result, outcome='SEM_DADOS')
    f = paper_quote(p, v, contract, bars[0].open, start + 1, cfg)
    if f['status'] != 'VIAVEL_SIMULADO':
        return dict(result, outcome='BLOQUEADA', reasons=f['reasons'])
    if D(f['gain_usdt']) <= 0:
        return dict(result, outcome='BLOQUEADA', reasons=['GANHO_LIQUIDO_NAO_POSITIVO'])
    result.update(close_outcome(bars, p, v, contract, f, bars[0].open, cfg, complete))
    sign = 1 if p.side == 'LONG' else -1
    entry = bars[0].open * (1 + sign * D('0.0001'))
    slip, fee, tick = D(cfg.slippage_rate), D(cfg.taker_fee), contract.tick
    cost_entry = max(2 * tick, slip * entry)
    risk = sign * (entry - v.stop) + cost_entry + max(2 * tick, slip * v.stop) + fee * (entry + v.stop)
    gain = sign * (v.target - entry) - cost_entry - max(2 * tick, slip * v.target) - fee * (entry + v.target)
    if gain <= 0:
        return {'window_complete': complete, 'outcome': 'BLOQUEADA', 'reasons': ['GANHO_LIQUIDO_NAO_POSITIVO']}
    result.update(entered_at=iso(start), worst_band_rr=f['net_rr'], entry_net_rr=gain / risk,
                  planned_loss_usdt=f['loss_usdt'], quantity=f['base_quantity'])
    if result['outcome'] == 'ABERTO':
        mark = bars[-1].close
        mark_gain = sign * (mark - entry) - cost_entry - max(2 * tick, slip * mark) - fee * (entry + mark)
        result.update(mark_to_market_r=mark_gain / risk, marked_at=iso(bars[-1].end))
    return jsonable(result)


def summary(rows, complete_only=False):
    sample = [r for r in rows if not complete_only or r['scenarios']['2']['window_complete']]
    out = {'signals': len(sample), 'scenarios': {}}
    for threshold in THRESHOLDS:
        values = [r['scenarios'][threshold] for r in sample]
        entries = [v for v in values if 'entered_at' in v]
        closed = [v for v in entries if 'net_r' in v]
        wins = sum(v['outcome'] == 'ALVO' for v in closed)
        out['scenarios'][threshold] = {
            'entries': len(entries), 'closed': len(closed), 'targets': wins,
            'stops': sum(v['outcome'] in {'STOP', 'STOP_AMBIGUO'} for v in closed),
            'ambiguous': sum(v['outcome'] == 'STOP_AMBIGUO' for v in closed),
            'open': sum(v['outcome'] == 'ABERTO' for v in entries),
            'win_rate_closed': str(D(wins) / len(closed)) if closed else None,
            'sum_r_closed_independent': str(sum((D(v['net_r']) for v in closed), D(0))),
            'sum_r_with_open_marks_independent': str(sum((D(v.get('net_r', v.get('mark_to_market_r', 0))) for v in entries), D(0))),
            'outcomes': dict(Counter(v['outcome'] for v in values)),
            'blocked_reasons': dict(Counter(t for v in values for t in v.get('reasons', []))),
            'mean_entry_net_rr': str(sum((D(v['entry_net_rr']) for v in entries), D(0)) / len(entries)) if entries else None,
        }
    return out


def run(report, observed_at, config=None, client=None):
    config = config or Config()
    client = client or MexcClient(config.api_base)
    now = client.server_time()
    cutoff = int(report['analyzed_at'])
    if report.get('source_status') != 'OK' or not cutoff <= observed_at <= now:
        raise ValueError('Corte histórico inválido; não usar dados futuros')
    signals = [r for r in report['plans'] if (v := r.get('variants', {}).get('CONFIRMADA'))
               and cutoff - 86400 <= v['triggered_at'] <= cutoff]
    catalog = {r['symbol']: r for r in client.contracts()}
    data, errors, rows = {}, {}, []
    for symbol in sorted({r['symbol'] for r in signals}):
        try:
            c = Contract.from_api(catalog[symbol])
            q = parse_candles(client.candles(symbol, 'Min15', 480, now), 900, now, 480)
            data[symbol] = q, c
        except Exception as exc:
            errors[symbol] = type(exc).__name__
    for row in signals:
        result = {'plan_id': row['id'], 'symbol': row['symbol'], 'side': row['side'],
                  'signal': iso(row['variants']['CONFIRMADA']['triggered_at']), 'scenarios': {}}
        for threshold in THRESHOLDS:
            if row['symbol'] in errors:
                result['scenarios'][threshold] = {'outcome': 'SEM_DADOS', 'window_complete': False}
            else:
                q, c = data[row['symbol']]
                result['scenarios'][threshold] = review(row, q, c, config, observed_at, threshold)
        rows.append(result)
    limits = [
        'Mesmos sinais, horário de observação, SL/TP, custos e entrada na abertura seguinte do teste A/B anterior. Só varia o mínimo RR.',
        'Zero significa ganho líquido positivo, sem relação mínima com o risco; não significa remover stop ou limites de risco.',
        'Saldo independente de 1 USDT, risco planejado até 10%, teto 20x, incrementos/margem/custos pelo validador atual.',
        'Taxa 0,06% por lado, spread 0,02%, deslizamento configurado ou dois ticks; funding zero é hipótese.',
        'Livro histórico não observado, profundidade infinita e ausência de latência são hipóteses; regras atuais do contrato.',
        '4h de observação, janelas incompletas separadas. Stops primeiro na ambiguidade; gaps podem superar -1R.',
        'Planos sobrepostos são testes independentes. Soma R não é saldo/retorno de uma carteira de 1 USDT.',
        'Marcação das abertas estima encerramento ao preço final com custos; é separada dos resultados realizados.',
        'Amostra pequena e retrospectiva já usada para formular hipóteses; não valida rentabilidade futura.',
    ]
    return jsonable({'kind': 'READ_ONLY_RR_SENSITIVITY', 'report_cutoff': iso(cutoff),
                     'observed_at_frozen': iso(observed_at), 'collected_at': iso(now),
                     'summary_all': summary(rows), 'summary_complete': summary(rows, True),
                     'errors': errors, 'limitations': limits, 'signals': rows})


def markdown(result):
    lines = ['## Teste isolado do mínimo de retorno/risco', '',
             'Relatório: ' + result['report_cutoff'] + '; observação congelada: ' + result['observed_at_frozen'] + '.', '',
             '| Amostra | RR mínimo | Entradas | Alvos | Stops | Abertas | R encerradas | R com abertas marcadas |',
             '| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    for label, s in [('Todas', result['summary_all']), ('4h completas', result['summary_complete'])]:
        for threshold, v in s['scenarios'].items():
            vals = [label, threshold if threshold != '0' else 'Sem mínimo (ganho líquido > 0)',
                    str(v['entries']), str(v['targets']), str(v['stops']), str(v['open']),
                    f"{D(v['sum_r_closed_independent']):.3f}", f"{D(v['sum_r_with_open_marks_independent']):.3f}"]
            lines.append('| ' + ' | '.join(vals) + ' |')
    lines += ['', '### Limites', ''] + ['- ' + x for x in result['limitations']]
    lines += ['', '```json', json.dumps({k: result[k] for k in ('summary_all', 'summary_complete', 'errors')}, ensure_ascii=False, indent=2), '```']
    return '\n'.join(lines) + '\n'


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--report', required=True)
    parser.add_argument('--as-of', default='2026-11-10T10:58:54+00:00')
    args = parser.parse_args()
    observed = int(datetime.fromisoformat(args.as_of).timestamp())
    result = run(json.loads(Path(args.report).read_text()), observed, load_config('config/default.toml'))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if path := os.environ.get('GITHUB_STEP_SUMMARY'):
        Path(path).write_text(markdown(result))
