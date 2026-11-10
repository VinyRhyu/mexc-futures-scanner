"""Diagnóstico isolado de SL, taxa e validação da faixa em sinais congelados.

Nenhuma regra ao vivo é alterada. Stops locais são hipóteses de invalidação;
nunca são escolhidos olhando o resultado nem para alcançar um RR específico.
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
from mexc_scanner.models import Contract, D, Plan, ceil_step, floor_step, jsonable
from scripts.audit_pullback import iso, paper_quote
from scripts.audit_rr import review


STOPS = ('ORIGINAL', 'REACAO', 'CONFIRMACAO')
FEES = ('0.0006', '0.0002', '0')


def stop_case(row, quarter, contract, rule):
    result = deepcopy(row)
    v = result['variants']['CONFIRMADA']
    if rule == 'ORIGINAL':
        return result, {'changed': False, 'reason': 'ORIGINAL'}
    stamp = row['reaction_at'] if rule == 'REACAO' else v['triggered_at']
    known = next((c for c in quarter if c.end == stamp), None)
    if known is None or stamp > v['triggered_at']:
        return result, {'changed': False, 'reason': 'SEM_CANDLE_CONHECIDO'}
    sign = 1 if row['side'] == 'LONG' else -1
    old = D(v['stop'])
    buffer = D(row['atr']) * D('0.10')
    candidate = (floor_step(known.low - buffer, contract.tick) if sign == 1 else
                 ceil_step(known.high + buffer, contract.tick))
    if sign * (candidate - old) <= 0:
        return result, {'changed': False, 'reason': 'STOP_LOCAL_NAO_E_MAIS_CURTO', 'candidate': candidate}
    best = D(v['entry_low'] if sign == 1 else v['entry_high'])
    if candidate <= 0 or sign * (best - candidate) <= 0:
        return result, {'changed': False, 'reason': 'STOP_LOCAL_DENTRO_DA_FAIXA', 'candidate': candidate}
    result['stop'] = v['stop'] = str(candidate)
    return result, {'changed': True, 'reason': 'EXTREMO_DO_CANDLE_MAIS_BUFFER',
                    'old_stop': old, 'new_stop': candidate, 'known_at': stamp}


def compare_quote(row, quarter, contract, config):
    """Mesma cotação em duas avaliações: faixa original e ponto atual nela."""
    p = Plan.from_dict(row)
    p.status = 'ATIVO'
    v = deepcopy(p.variants['CONFIRMADA'])
    v.status = 'VALIDA'
    first = next((c for c in quarter if c.ts == v.triggered_at), None)
    if first is None:
        return {'comparable': False, 'reason': 'SEM_CANDLE'}
    sign = 1 if p.side == 'LONG' else -1
    price = first.open * (1 + sign * D('0.0001'))
    # Cotação sintética arredondada contra a entrada, ao tick do contrato.
    quote = ceil_step(price, contract.tick) if sign == 1 else floor_step(price, contract.tick)
    if not v.entry_low <= quote <= v.entry_high:
        return {'comparable': False, 'reason': 'COTACAO_FORA_DA_FAIXA'}
    cfg = replace(config, mode='paper', fees_verified=False, account_rules_verified=False)
    band = paper_quote(p, v, contract, quote, v.triggered_at + 1, cfg, quoted=True)
    narrow = deepcopy(v)
    narrow.entry_low = narrow.entry_high = quote
    point = paper_quote(p, narrow, contract, quote, v.triggered_at + 1, cfg, quoted=True)
    return jsonable({'comparable': True, 'quote': quote, 'band_status': band['status'],
                     'band_reasons': band['reasons'], 'point_status': point['status'],
                     'point_reasons': point['reasons'], 'point_rr': point.get('net_rr'),
                     'point_risk': point.get('loss_usdt'),
                     'band_blocked_point_viable': band['status'] != 'VIAVEL_SIMULADO' and point['status'] == 'VIAVEL_SIMULADO'})


def summarize(rows, complete=False):
    sample = [r for r in rows if not complete or r['cases']['ORIGINAL:0.0006'].get('window_complete')]
    result = {'signals': len(sample), 'cases': {}}
    for stop in STOPS:
        for fee in FEES:
            key = stop + ':' + fee
            values = [r['cases'][key] for r in sample]
            entries = [v for v in values if 'entered_at' in v]
            closed = [v for v in entries if 'net_r' in v]
            result['cases'][key] = {
                'entries': len(entries), 'targets': sum(v['outcome'] == 'ALVO' for v in closed),
                'stops': sum(v['outcome'] in {'STOP', 'STOP_AMBIGUO'} for v in closed),
                'ambiguous': sum(v['outcome'] == 'STOP_AMBIGUO' for v in closed),
                'open': sum(v['outcome'] == 'ABERTO' for v in entries),
                'closed_r': str(sum((D(v['net_r']) for v in closed), D(0))),
                'r_with_open_marks': str(sum((D(v.get('net_r', v.get('mark_to_market_r', 0))) for v in entries), D(0))),
                'stop_changes': sum(r['stop_notes'][stop]['changed'] for r in sample),
                'stop_notes': dict(Counter(r['stop_notes'][stop]['reason'] for r in sample)),
                'blocked': dict(Counter(t for v in values for t in v.get('reasons', []))),
                'new_entries_vs_original_same_fee': sum('entered_at' in r['cases'][key] and
                    'entered_at' not in r['cases']['ORIGINAL:' + fee] for r in sample),
            }
    result['quote_comparison'] = {fee: {
        'comparable': sum(r['quote_checks'][fee].get('comparable', False) for r in sample),
        'band_blocked_point_viable': sum(r['quote_checks'][fee].get('band_blocked_point_viable', False) for r in sample)
    } for fee in FEES}
    return result


def run(report, observed_at, config=None, client=None):
    config = config or Config()
    client = client or MexcClient(config.api_base)
    now = client.server_time()
    cutoff = int(report['analyzed_at'])
    if report.get('source_status') != 'OK' or not cutoff <= observed_at <= now:
        raise ValueError('Corte histórico inválido')
    signals = [r for r in report['plans'] if (v := r.get('variants', {}).get('CONFIRMADA'))
               and cutoff - 86400 <= v['triggered_at'] <= cutoff]
    catalog = {r['symbol']: r for r in client.contracts()}
    data, errors, rows = {}, {}, []
    for symbol in sorted({r['symbol'] for r in signals}):
        try:
            data[symbol] = (parse_candles(client.candles(symbol, 'Min15', 480, now), 900, now, 480),
                            Contract.from_api(catalog[symbol]))
        except Exception as exc:
            errors[symbol] = type(exc).__name__
    for row in signals:
        r = {'plan_id': row['id'], 'symbol': row['symbol'], 'strategy': row['strategy'],
             'side': row['side'], 'signal': iso(row['variants']['CONFIRMADA']['triggered_at']),
             'target': row['variants']['CONFIRMADA']['target'], 'cases': {}, 'stop_notes': {}, 'quote_checks': {}}
        if row['symbol'] in errors:
            for stop in STOPS:
                r['stop_notes'][stop] = {'changed': False, 'reason': 'SEM_DADOS'}
                for fee in FEES:
                    r['cases'][stop + ':' + fee] = {'outcome': 'SEM_DADOS', 'window_complete': False}
            r['quote_checks'] = {fee: {'comparable': False} for fee in FEES}
        else:
            q, c = data[row['symbol']]
            for stop in STOPS:
                adjusted, note = stop_case(row, q, c, stop)
                r['stop_notes'][stop] = jsonable(note)
                for fee in FEES:
                    cfg = replace(config, taker_fee=fee)
                    r['cases'][stop + ':' + fee] = review(adjusted, q, c, cfg, observed_at, '2')
            for fee in FEES:
                r['quote_checks'][fee] = compare_quote(row, q, c, replace(config, taker_fee=fee))
        rows.append(r)
    limitations = [
        'Mesmos 85 sinais e mesma observação congelada do A/B anterior; apenas stops locais e taxas em cenários separados.',
        'SL local = extremo do candle de reação inicial ou de confirmação, mais 0,10 ATR, conhecido antes da entrada.',
        'Só troca SL se mais curto e válido para toda a faixa original. Caso contrário preserva o original e registra o motivo.',
        'Alvo, faixa de entrada, mínimo 2:1, risco até 10%, lote e teto 20x permanecem constantes.',
        'Taxas de 0,06%, 0,02% e zero POR EXECUÇÃO são hipóteses; taxa pessoal não foi consultada.',
        'Mesmo com taxa zero permanecem spread 0,02% e slippage configurado ou dois ticks por lado. Funding zero hipotético.',
        'Livro infinito, ausência de latência e regras atuais do contrato não reproduzem as condições reais passadas.',
        'Comparação da faixa com o preço pontual usa a mesma cotação arredondada ao tick nos dois casos, sem mudar SL/TP.',
        '4h por confirmação, stops primeiro na ambiguidade, abertas marcadas separadamente. Soma R não é carteira.',
        'Várias hipóteses na mesma amostra exploratória não validam uma estratégia nem demonstram vantagem prospectiva.'
    ]
    return jsonable({'kind': 'READ_ONLY_STOP_COST_DIAGNOSIS', 'report_cutoff': iso(cutoff),
                     'observed_at': iso(observed_at), 'collected_at': iso(now), 'errors': errors,
                     'summary_all': summarize(rows), 'summary_complete': summarize(rows, True),
                     'limitations': limitations, 'signals': rows})


def markdown(result):
    lines = ['## Diagnóstico de stops, taxas e faixa de entrada', '',
             'Fonte: ' + result['report_cutoff'] + '; observação congelada: ' + result['observed_at'] + '.', '',
             '| Stop | Taxa por lado | Mudanças de SL | Entradas | Alvos | Stops | Abertas | R encerradas |',
             '| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
    for key, v in result['summary_complete']['cases'].items():
        stop, fee = key.split(':')
        lines.append(f"| {stop} | {D(fee):.2%} | {v['stop_changes']} | {v['entries']} | {v['targets']} | {v['stops']} | {v['open']} | {D(v['closed_r']):.3f} |")
    lines += ['', '### Comparação da faixa com cotação pontual', '', '```json',
              json.dumps(result['summary_complete']['quote_comparison'], ensure_ascii=False, indent=2), '```', '',
              '### Hipóteses e limites', ''] + ['- ' + x for x in result['limitations']]
    lines += ['', '```json', json.dumps({k: result[k] for k in ('summary_all', 'summary_complete', 'errors')}, ensure_ascii=False, indent=2), '```']
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
