"""Audita as 19 entradas previamente congeladas, sem escolher níveis novos."""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from dataclasses import replace
from datetime import datetime
import json
import os
from pathlib import Path

from mexc_scanner.config import load_config
from mexc_scanner.market import parse_candles
from mexc_scanner.mexc import MexcClient
from mexc_scanner.models import Contract, D, Plan, jsonable
from scripts.audit_historical_trend import collect_signals, midnight
from scripts.audit_pullback import close_outcome, iso, paper_quote


def candle_consistency(quarter, minute, signal):
    mismatches = []
    for q in quarter:
        if not signal <= q.ts < signal + 14400:
            continue
        group = [c for c in minute if q.ts <= c.ts < q.end]
        if len(group) != 15 or group[0].ts != q.ts or group[-1].end != q.end:
            mismatches.append({'ts': q.ts, 'reason': 'MINUTOS_INCOMPLETOS'})
            continue
        values = (group[0].open, max(c.high for c in group), min(c.low for c in group), group[-1].close)
        if values != (q.open, q.high, q.low, q.close):
            mismatches.append({'ts': q.ts, 'reason': 'OHLC_DIVERGENTE'})
    if len([q for q in quarter if signal <= q.ts < signal + 14400]) != 16:
        mismatches.append({'reason': 'JANELA_15M_INCOMPLETA'})
    return mismatches


def audit_delay(row, minute, contract, config, delay):
    p = Plan.from_dict(row)
    v = deepcopy(p.variants['CONFIRMADA'])
    p.status, v.status = 'ATIVO', 'VALIDA'
    start, end = v.triggered_at + delay, v.triggered_at + 14400
    bars = [c for c in minute if start <= c.ts < end]
    if not bars or bars[0].ts != start or bars[-1].end != end or any(a.end != b.ts for a, b in zip(bars, bars[1:])):
        return {'outcome': 'SEM_DADOS'}
    sign = 1 if p.side == 'LONG' else -1
    before = [c for c in minute if v.triggered_at <= c.ts < start]
    for c in before:
        if c.low <= v.stop if sign == 1 else c.high >= v.stop:
            return {'outcome': 'SEM_ENTRADA_STOP_ANTES', 'at': iso(c.end)}
        if c.high >= v.target if sign == 1 else c.low <= v.target:
            return {'outcome': 'SEM_ENTRADA_ALVO_ANTES', 'at': iso(c.end)}
    f = paper_quote(p, v, contract, bars[0].open, start + 1, config)
    if f['status'] != 'VIAVEL_SIMULADO':
        return {'outcome': 'BLOQUEADA', 'reasons': f['reasons'], 'entry_mid': bars[0].open}
    r = close_outcome(bars, p, v, contract, f, bars[0].open, config, True)
    r.update(entered_at=iso(start), entry_mid=bars[0].open, net_rr=f['net_rr'], planned_loss=f['loss_usdt'])
    return jsonable(r)


def summarize(records):
    out = {'cases': len(records)}
    for delay in (0, 60, 120):
        vals = [r['delays'][str(delay)] for r in records]
        entries = [v for v in vals if 'entered_at' in v]
        closed = [v for v in entries if 'net_r' in v]
        out[str(delay)] = {'entries': len(entries), 'targets': sum(v['outcome'] == 'ALVO' for v in closed),
            'stops': sum(v['outcome'] in {'STOP', 'STOP_AMBIGUO'} for v in closed),
            'ambiguous': sum(v['outcome'] == 'STOP_AMBIGUO' for v in closed),
            'open': sum(v['outcome'] == 'ABERTO' for v in entries),
            'outcomes': dict(Counter(v['outcome'] for v in vals)),
            'blocked_reasons': dict(Counter(t for v in vals for t in v.get('reasons', []))),
            'closed_r_independent': str(sum((D(v['net_r']) for v in closed), D(0)))}
    return out


def run(client=None):
    cohort = json.loads(Path('config/audit-m1-cohort.json').read_text())
    cfg = replace(load_config('config/default.toml'), mode='paper', fees_verified=False, account_rules_verified=False)
    client = client or MexcClient(cfg.api_base)
    start, end = midnight(cohort['start']), midnight(cohort['end'])
    observed = end + 14400
    catalog = {r['symbol']: r for r in client.contracts()}
    records, errors = [], {}
    for symbol in sorted({r['symbol'] for r in cohort['trades']}):
        try:
            contract = Contract.from_api(catalog[symbol])
            qn, hn = 480 + (observed - start) // 900, 240 + (observed - start) // 3600
            q = parse_candles(client.candles(symbol, 'Min15', qn, observed + 10), 900, observed + 10, qn)
            h = parse_candles(client.candles(symbol, 'Min60', hn, observed + 10), 3600, observed + 10, hn)
            signals = {(r['plan_id'], r['kind']): r for r in collect_signals(symbol, q, h, contract, cfg, start, end)}
        except Exception as exc:
            errors[symbol] = type(exc).__name__
            continue
        for original in [r for r in cohort['trades'] if r['symbol'] == symbol]:
            try:
                frozen = signals[(original['plan_id'], original['kind'])]
                if frozen['signal'] != original['signal'] or frozen['side'] != original['side']:
                    raise ValueError('Reconstrução diferente da entrada congelada')
                signal = original['signal']
                minute = parse_candles(client.candles(symbol, 'Min1', 270, signal + 14400 + 10), 60, signal + 14400 + 10, 270)
                v = frozen['plan']['variants']['CONFIRMADA']
                r = {'symbol': symbol, 'kind': original['kind'], 'signal': iso(signal), 'plan_id': original['plan_id'],
                     'side': original['side'], 'stop': v['stop'], 'target': v['target'],
                     'entry_low': v['entry_low'], 'entry_high': v['entry_high'],
                     'old_15m': original['baseline'], 'ohlc_mismatches': candle_consistency(q, minute, signal),
                     'delays': {str(delay): audit_delay(frozen['plan'], minute, contract, cfg, delay) for delay in (0, 60, 120)}}
                r['same_immediate_outcome'] = r['delays']['0']['outcome'] == original['baseline']['outcome']
                records.append(jsonable(r))
                print(json.dumps({'progress': len(records), 'symbol': symbol, 'original': original['baseline']['outcome'],
                                  'minute': r['delays']['0']['outcome'], 'mismatches': len(r['ohlc_mismatches'])}), flush=True)
            except Exception as exc:
                errors[original['plan_id']] = type(exc).__name__
    comparable = [r for r in records if not r['ohlc_mismatches']]
    limits = [
        'Todas as 19 entradas do replay anterior, sem selecionar pelo resultado; níveis reconstruídos com o mesmo gerador.',
        'Consistência compara 16 candles 15m com seus 240 candles 1m. Divergências ficam fora do resumo principal.',
        'Atrasos de 0/60/120 segundos são hipóteses pré-definidas, não a latência histórica observada.',
        'SL/TP tocado antes da entrada atrasada cancela essa tentativa; não é contabilizado como trade perdido.',
        'Mantém SL/TP/faixa/custos/RR mínimo 2/lote/risco até 10%/teto 20x. Preço fora da faixa ou gate financeiro rejeita a entrada.',
        'Janela comum termina 4h após o sinal original; modelos atrasados têm até dois minutos a menos de posição.',
        'Stop e alvo no mesmo minuto continuam ambíguos; usa stop primeiro. Sem livro histórico, preenchimento não é demonstrado.',
        'Mesmas hipóteses de taxa 0,06% por lado, spread 0,02%, slippage configurado ou dois ticks, funding zero.',
        'Regras atuais dos contratos; soma R de sinais independentes não é carteira nem dinheiro realizado.'
    ]
    return jsonable({'kind': 'MINUTE_EXECUTION_AUDIT', 'expected_cases': len(cohort['trades']), 'reconstructed_cases': len(records),
        'consistent_cases': len(comparable), 'same_immediate_outcomes': sum(r['same_immediate_outcome'] for r in comparable),
        'summary': summarize(comparable), 'errors': errors, 'limitations': limits, 'cases': records})


def markdown(r):
    lines = ['## Auditoria das 19 entradas com candles 1m', '',
        f"Reconstruídas: {r['reconstructed_cases']}/{r['expected_cases']}; OHLC consistente: {r['consistent_cases']}; desfecho imediato igual: {r['same_immediate_outcomes']}.", '',
        '| Atraso | Entradas | Alvos | Stops | Abertas | R encerradas |', '| --- | ---: | ---: | ---: | ---: | ---: |']
    for delay in (0, 60, 120):
        v = r['summary'][str(delay)]
        lines.append(f"| {delay}s | {v['entries']} | {v['targets']} | {v['stops']} | {v['open']} | {D(v['closed_r_independent']):.3f} |")
    lines += ['', '| Ativo | Tipo | Sinal UTC | 15m | 1m sem atraso | +1min | +2min |', '| --- | --- | --- | --- | --- | --- | --- |']
    for c in r['cases']:
        lines.append('| ' + ' | '.join([c['symbol'], c['kind'], c['signal'], c['old_15m']['outcome']] + [c['delays'][str(d)]['outcome'] for d in (0,60,120)]) + ' |')
    lines += ['', '### Limites', ''] + ['- ' + x for x in r['limitations']]
    lines += ['', '```json', json.dumps({'summary': r['summary'], 'errors': r['errors']}, ensure_ascii=False, indent=2), '```']
    return '\n'.join(lines) + '\n'


if __name__ == '__main__':
    r = run()
    print('MINUTE_RESULT_BEGIN')
    print(json.dumps(r, ensure_ascii=False, indent=2))
    print('MINUTE_RESULT_END')
    if path := os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(path, 'a') as out:
            out.write(markdown(r))
    if r['reconstructed_cases'] != r['expected_cases']:
        raise SystemExit('Auditoria incompleta: consultar erros')
