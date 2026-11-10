"""Auditoria de pivôs/alvos e confirmação, sem alterar decisões ao vivo.

Hipóteses fixadas antes do replay: ignorar pivôs previamente atravessados por
fechamento de 1h; e projeção original sem corte (limite otimista, não proposta live).
Todas as modalidades presentes no relatório são incluídas, mesmo sem confirmação.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
from dataclasses import replace
from datetime import datetime
import json
import math
import os
from pathlib import Path
from statistics import median

from mexc_scanner.config import Config, load_config
from mexc_scanner.market import aggregate_two_hours, parse_candles, pivots
from mexc_scanner.mexc import MexcClient
from mexc_scanner.models import Contract, D, Plan, ceil_step, floor_step, jsonable
from mexc_scanner.strategies import make_variant
from scripts.audit_pullback import iso
from scripts.audit_rr import review


MODES = ('REGISTRADO', 'PIVOS_NAO_ATRAVESSADOS', 'PROJECAO_SEM_CORTE')


def target_options(row, kind, quarter, hourly, contract):
    p = Plan.from_dict(row)
    v = p.variants[kind]
    sign = 1 if p.side == 'LONG' else -1
    c = next((c for c in quarter if c.end == v.triggered_at), None)
    h = [c for c in hourly if c.end <= v.triggered_at][-240:]
    if c is None or len(h) != 240 or c.close != v.reference:
        return {'reconstructed': False, 'reason': 'HISTORICO_DA_FORMACAO_INCOMPLETO'}
    projected = (v.reference + sign * D('2.5') * abs(v.reference - v.stop) if p.strategy == 'CONTINUACAO'
                 else p.level + sign * (p.upper - p.lower))
    known = [(pv, tf) for bars, tf in ((h, '1h'), (aggregate_two_hours(h), '2h'))
             for pv in pivots(bars, v.triggered_at)]
    obstacles = [(pv, tf) for pv, tf in known if pv.kind == ('HIGH' if sign == 1 else 'LOW')
                 and sign * (pv.price - v.reference) > 0 and sign * (projected - pv.price) > 0]

    def crossed(pv):
        # Usa apenas fechamentos já conhecidos após a confirmação do próprio pivô.
        return any(pv.known_at < bar.end <= v.triggered_at and
                   sign * (bar.close - pv.price) > D('0.10') * p.atr for bar in h)

    ordered = sorted(obstacles, key=lambda x: sign * x[0].price)
    meta = [{'price': pv.price, 'tf': tf, 'pivot_at': pv.ts, 'known_at': pv.known_at,
             'age_hours': D(v.triggered_at - pv.ts) / 3600, 'crossed_before_signal': crossed(pv)} for pv, tf in ordered]
    rebuilt = make_variant(p, kind, c, h, contract.tick)
    matches = ((rebuilt.target, rebuilt.entry_low, rebuilt.entry_high) ==
               (v.target, v.entry_low, v.entry_high))
    if not matches:
        return jsonable({'reconstructed': False, 'reason': 'ALVO_OU_FAIXA_RECONSTRUIDOS_DIFEREM',
                         'registered': v.target, 'rebuilt': rebuilt.target, 'obstacles': meta})
    rounding = floor_step if sign == 1 else ceil_step
    active = [(pv, tf) for pv, tf in ordered if not crossed(pv)]
    new = projected if not active else active[0][0].price - sign * D('0.10') * p.atr
    return jsonable({'reconstructed': True, 'reason': 'REPRODUZIDO',
                     'registered': v.target, 'projected': rounding(projected, contract.tick),
                     'filtered': rounding(new, contract.tick), 'obstacles': meta,
                     'selected': meta[0] if meta else None})


def reference_rr(v, side, tick, config):
    sign = 1 if side == 'LONG' else -1
    entry, stop, target = map(D, (v['reference'], v['stop'], v['target']))
    risk = sign * (entry - stop)
    if risk <= 0:
        return None
    fee, slip = D(config.taker_fee), D(config.slippage_rate)
    cost_entry = max(2 * tick, entry * slip)
    loss = risk + cost_entry + max(2 * tick, stop * slip) + fee * (entry + stop)
    gain = sign * (target - entry) - cost_entry - max(2 * tick, target * slip) - fee * (entry + target)
    return gain / loss


def paired_diagnostics(plans, variants, contracts, config):
    by = {(r['plan_id'], r['kind']): r for r in variants}
    rows = []
    for p in plans:
        a, c = by.get((p['id'], 'ANTECIPADA')), by.get((p['id'], 'CONFIRMADA'))
        if not a or not c or p['symbol'] not in contracts:
            continue
        va, vc = p['variants']['ANTECIPADA'], p['variants']['CONFIRMADA']
        tick = contracts[p['symbol']].tick
        ra, rc = reference_rr(va, p['side'], tick, config), reference_rr(vc, p['side'], tick, config)
        sign = 1 if p['side'] == 'LONG' else -1
        rows.append(jsonable({'plan_id': p['id'], 'symbol': p['symbol'],
            'wait_seconds': vc['triggered_at'] - va['triggered_at'],
            'move_in_direction_atr': sign * (D(vc['reference']) - D(va['reference'])) / D(p['atr']),
            'anticipada_rr_at_reference': ra, 'confirmada_rr_at_reference': rc,
            'rr_worsened': ra is not None and rc is not None and rc < ra,
            'early_entry': 'entered_at' in a['cases']['REGISTRADO'],
            'confirmed_entry': 'entered_at' in c['cases']['REGISTRADO'],
            'both_windows_complete': a['cases']['REGISTRADO'].get('window_complete', False) and c['cases']['REGISTRADO'].get('window_complete', False)}))
    return {'pairs': len(rows), 'rr_worsened': sum(r['rr_worsened'] for r in rows),
            'price_advanced_in_trade_direction': sum(D(r['move_in_direction_atr']) > 0 for r in rows),
            'early_viable_confirmed_not': sum(r['early_entry'] and not r['confirmed_entry'] for r in rows),
            'confirmed_viable_early_not': sum(r['confirmed_entry'] and not r['early_entry'] for r in rows),
            'median_move_atr': str(median([D(r['move_in_direction_atr']) for r in rows])) if rows else None,
            'records': rows}


def summarize(rows, kind, matched_complete=False):
    sample = [r for r in rows if r['kind'] == kind and (not matched_complete or
              (r['target_audit'].get('reconstructed') and r['cases']['REGISTRADO'].get('window_complete')))]
    out = {'signals': len(sample), 'reconstructed': sum(r['target_audit'].get('reconstructed', False) for r in sample),
           'reconstruction_reasons': dict(Counter(r['target_audit']['reason'] for r in sample)),
           'selected_pivot': sum(r['target_audit'].get('selected') is not None for r in sample),
           'selected_pivot_previously_crossed': sum(bool((r['target_audit'].get('selected') or {}).get('crossed_before_signal')) for r in sample),
           'cases': {}}
    ages = [D(r['target_audit']['selected']['age_hours']) for r in sample if r['target_audit'].get('selected')]
    out['median_selected_pivot_age_hours'] = str(median(ages)) if ages else None
    for mode in MODES:
        vals = [r['cases'][mode] for r in sample]
        entries = [v for v in vals if 'entered_at' in v]
        closed = [v for v in entries if 'net_r' in v]
        out['cases'][mode] = {
            'entries': len(entries), 'targets': sum(v['outcome'] == 'ALVO' for v in closed),
            'stops': sum(v['outcome'] in {'STOP', 'STOP_AMBIGUO'} for v in closed),
            'ambiguous': sum(v['outcome'] == 'STOP_AMBIGUO' for v in closed),
            'open': sum(v['outcome'] == 'ABERTO' for v in entries),
            'closed_r': str(sum((D(v['net_r']) for v in closed), D(0))),
            'r_with_open_marks': str(sum((D(v.get('net_r', v.get('mark_to_market_r', 0))) for v in entries), D(0))),
            'outcomes': dict(Counter(v['outcome'] for v in vals)),
            'blocked': dict(Counter(t for v in vals for t in v.get('reasons', []))),
            'new_entries': sum('entered_at' in r['cases'][mode] and 'entered_at' not in r['cases']['REGISTRADO'] for r in sample)}
    return out


def run(report, observed_at, config=None, client=None):
    config = replace(config or Config(), mode='paper')
    client = client or MexcClient(config.api_base)
    now, cutoff = client.server_time(), int(report['analyzed_at'])
    if report.get('source_status') != 'OK' or not cutoff <= observed_at <= now:
        raise ValueError('Corte histórico inválido')
    plans = [p for p in report['plans'] if any(cutoff - 86400 <= v['triggered_at'] <= cutoff for v in p.get('variants', {}).values())]
    catalog = {r['symbol']: r for r in client.contracts()}
    data, errors, rows, contracts = {}, {}, [], {}
    for symbol in sorted({p['symbol'] for p in plans}):
        try:
            earliest = min(v['triggered_at'] for p in plans if p['symbol'] == symbol for v in p['variants'].values())
            count = 240 + math.ceil((now - earliest) / 3600) + 4
            if count > 1900:
                raise ValueError('Amostra antiga demais para recompor o histórico')
            c = Contract.from_api(catalog[symbol])
            q = parse_candles(client.candles(symbol, 'Min15', 480, now), 900, now, 480)
            h = parse_candles(client.candles(symbol, 'Min60', count, now), 3600, now, count)
            data[symbol], contracts[symbol] = (q, h, c), c
        except Exception as exc:
            errors[symbol] = type(exc).__name__
    for p in plans:
        for kind, v in p['variants'].items():
            if not cutoff - 86400 <= v['triggered_at'] <= cutoff:
                continue
            r = {'plan_id': p['id'], 'symbol': p['symbol'], 'strategy': p['strategy'], 'side': p['side'],
                 'kind': kind, 'signal': iso(v['triggered_at']), 'cases': {}}
            if p['symbol'] in errors:
                r['target_audit'] = {'reconstructed': False, 'reason': 'SEM_DADOS'}
                r['cases'] = {m: {'outcome': 'SEM_DADOS', 'window_complete': False} for m in MODES}
            else:
                q, h, c = data[p['symbol']]
                r['target_audit'] = audit = target_options(p, kind, q, h, c)
                # Adapta a função de replay ao tipo, sem selecionar apenas os
                # gatilhos iniciais que mais tarde receberam confirmação.
                base = deepcopy(p)
                base['variants']['CONFIRMADA'] = deepcopy(v)
                r['cases']['REGISTRADO'] = review(base, q, c, config, observed_at, '2')
                for mode, key in [('PIVOS_NAO_ATRAVESSADOS', 'filtered'), ('PROJECAO_SEM_CORTE', 'projected')]:
                    if not audit.get('reconstructed'):
                        r['cases'][mode] = {'outcome': 'RECONSTRUCAO_NAO_VALIDADA', 'window_complete': False}
                    else:
                        trial = deepcopy(base)
                        trial['variants']['CONFIRMADA']['target'] = audit[key]
                        r['cases'][mode] = review(trial, q, c, config, observed_at, '2')
            rows.append(r)
    limitations = [
        'Relatório e observação congelados do teste anterior. Inclui todas as antecipadas retidas, inclusive sem confirmação posterior.',
        'Alternativas de TP só são comparadas quando alvo/faixa originais foram reproduzidos exatamente com os 240 candles de 1h disponíveis na formação.',
        'Pivô atravessado = fechamento conhecido de 1h além do nível por mais de 0,10 ATR após o pivô ser confirmado.',
        'Um pivô atravessado pode voltar a atuar como suporte/resistência. Removê-lo é hipótese experimental, não correção demonstrada.',
        'Projeção sem corte ignora obstáculos; serve como diagnóstico otimista, não como autorização para afastar TP.',
        'SL, faixa, risco até 10%, mínimo 2:1, taxas/spread/slippage e validação financeira da main permanecem iguais.',
        'Taxa 0,06% por lado, spread 0,02%, deslizamento configurado ou dois ticks, funding zero e livro infinito hipotéticos.',
        'Entrada na abertura seguinte sem a latência real. Regras atuais do contrato; observação de 4h e abertas marcadas separadamente.',
        'Pares descrevem somente planos que confirmaram; comparação de desempenho principal inclui todas as variantes para reduzir seleção pelo futuro.',
        'Todos os sinais são testes independentes, podem se sobrepor e usam a mesma amostra já explorada. Soma R não é carteira nem validação prospectiva.'
    ]
    return jsonable({'kind': 'READ_ONLY_TARGET_TIMING_AUDIT', 'report_cutoff': iso(cutoff), 'observed_at': iso(observed_at),
                     'collected_at': iso(now), 'errors': errors, 'limitations': limitations,
                     'summary_all': {k: summarize(rows, k) for k in ('ANTECIPADA', 'CONFIRMADA')},
                     'summary_matched_complete': {k: summarize(rows, k, True) for k in ('ANTECIPADA', 'CONFIRMADA')},
                     'timing': paired_diagnostics(plans, rows, contracts, config), 'variants': rows})


def markdown(result):
    lines = ['## Auditoria de alvos, pivôs e momento da confirmação', '',
             'Fonte: ' + result['report_cutoff'] + '; observação congelada: ' + result['observed_at'] + '.', '',
             'Comparação principal: apenas reconstruções exatas e janelas completas de 4h.', '',
             '| Modalidade | TP | Amostra | Entradas | Alvos | Stops | Abertas | R encerradas |',
             '| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    for kind, summary in result['summary_matched_complete'].items():
        for mode, s in summary['cases'].items():
            lines.append(f"| {kind} | {mode} | {summary['signals']} | {s['entries']} | {s['targets']} | {s['stops']} | {s['open']} | {D(s['closed_r']):.3f} |")
    lines += ['', '### Diagnóstico de confirmação (pares, não carteira)', '', '```json',
              json.dumps({k: v for k, v in result['timing'].items() if k != 'records'}, ensure_ascii=False, indent=2), '```', '',
              '### Hipóteses e limites', ''] + ['- ' + v for v in result['limitations']]
    lines += ['', '```json', json.dumps({k: result[k] for k in ('summary_all', 'summary_matched_complete', 'errors')}, ensure_ascii=False, indent=2), '```']
    return '\n'.join(lines) + '\n'


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--report', required=True)
    parser.add_argument('--as-of', default='2026-11-10T10:58:54+00:00')
    args = parser.parse_args()
    result = run(json.loads(Path(args.report).read_text()), int(datetime.fromisoformat(args.as_of).timestamp()), load_config('config/default.toml'))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if path := os.environ.get('GITHUB_STEP_SUMMARY'):
        Path(path).write_text(markdown(result))
