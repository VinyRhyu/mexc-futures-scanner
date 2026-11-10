"""A/B histórico de confirmações registradas. Exclusivamente leitura, sem alertas/ordens.

A: cotação hipotética na abertura imediatamente após a confirmação, faixa original.
B: aguardar a checagem de 15m seguinte e recuo à faixa entre o nível técnico e o
fechamento da confirmação. Validade experimental: 30m após a confirmação.
SL/TP nunca mudam. Livro, spread e funding históricos não foram observados.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone
import json
import os
from pathlib import Path

from mexc_scanner.config import Config, load_config
from mexc_scanner.finance import evaluate
from mexc_scanner.market import parse_candles, structure
from mexc_scanner.mexc import MexcClient
from mexc_scanner.models import Contract, D, Plan, Variant, ceil_step, floor_step, jsonable


def iso(stamp):
    return datetime.fromtimestamp(stamp, timezone.utc).isoformat()


def paper_quote(plan, variant, contract, price, now, config, quoted=False):
    """Cotação/livro sintéticos na abertura, com o mesmo validador financeiro."""
    spread = price * D('0.0002')
    bid, ask = price - spread / 2, price + spread / 2
    if quoted:
        bid, ask = ((price - spread, price) if plan.side == 'LONG' else (price, price + spread))
    ticker = {'bid1': bid, 'ask1': ask, 'timestamp': now * 1000}
    book = {'bids': [[bid, D('1E15')]], 'asks': [[ask, D('1E15')]], 'timestamp': now * 1000}
    funding = {'fundingRate': '0', 'collectCycle': 8, 'nextSettleTime': (now + 8 * 3600) * 1000}
    return evaluate(plan, variant, contract, D(config.initial_balance), ticker, book, funding, now, config)


def pullback_variant(plan: Plan, variant: Variant, tick):
    """Faixa fixada na confirmação, sem consultar candles posteriores."""
    v = deepcopy(variant)
    threshold = plan.level + (1 if plan.side == 'LONG' else -1) * plan.atr * (
        D('0.25') if plan.strategy == 'CONTINUACAO' else D('0.10'))
    if plan.side == 'LONG':
        v.entry_low = ceil_step(threshold + tick, tick)
        v.entry_high = floor_step(v.reference - tick, tick)
    else:
        v.entry_low = ceil_step(v.reference + tick, tick)
        v.entry_high = floor_step(threshold - tick, tick)
    return v


def close_outcome(bars, plan, variant, contract, financial, entry_mid, config, complete):
    """Stop tem precedência na ambiguidade; gaps adversos atravessam o stop."""
    sign = 1 if plan.side == 'LONG' else -1
    entry = entry_mid * (1 + sign * D('0.0001'))  # bid/ask assumidos
    quantity = D(financial['base_quantity'])
    tick, slip, fee = contract.tick, D(config.slippage_rate), D(config.taker_fee)
    entry_cost = max(2 * tick, entry * slip)
    label, stamp, level, ambiguous = 'ABERTO', None, None, False
    for c in bars:
        bad = c.low <= variant.stop if sign == 1 else c.high >= variant.stop
        good = c.high >= variant.target if sign == 1 else c.low <= variant.target
        if bad or good:
            ambiguous = bad and good
            label = 'STOP_AMBIGUO' if ambiguous else 'STOP' if bad else 'ALVO'
            level = (min(variant.stop, c.open) if sign == 1 else max(variant.stop, c.open)) if bad else variant.target
            stamp = c.end
            break
    result = {'outcome': label, 'window_complete': complete, 'ambiguous': ambiguous}
    if level is not None:
        exit_cost = max(2 * tick, level * slip)
        net = quantity * (sign * (level - entry) - entry_cost - exit_cost - fee * (entry + level))
        # Mesmo preço e custos para normalizar em R, sem somar carteiras sobrepostas.
        risk = quantity * (sign * (entry - variant.stop) + entry_cost +
                           max(2 * tick, variant.stop * slip) + fee * (entry + variant.stop))
        result.update(net_usdt=net, net_r=net / risk, exited_at=iso(stamp))
    return result


def review_signal(row, quarter, hourly, contract, config, now, horizon=14400):
    plan = Plan.from_dict(row)
    variant = deepcopy(plan.variants['CONFIRMADA'])
    # Status final do relatório não pode ser usado para escolher entradas passadas.
    plan.status, plan.reason = 'ATIVO', ''
    variant.status, variant.reason = 'VALIDA', ''
    variant.financial = {}
    signal = variant.triggered_at
    cutoff = signal + horizon
    complete = now >= cutoff and bool(quarter) and quarter[-1].end >= cutoff
    bars = [c for c in quarter if signal <= c.ts < cutoff]
    result = {'plan_id': plan.id, 'symbol': plan.symbol, 'strategy': plan.strategy,
              'side': plan.side, 'signal': iso(signal), 'stop': variant.stop,
              'target': variant.target, 'target_origin': variant.target_origin,
              'window_complete': complete}
    if not bars or bars[0].ts != signal or any(a.end != b.ts for a, b in zip(bars, bars[1:])):
        result.update(A={'outcome': 'SEM_DADOS'}, B={'outcome': 'SEM_DADOS'})
        return jsonable(result)
    baseline = deepcopy(plan)
    f = paper_quote(baseline, variant, contract, bars[0].open, signal + 1, config)
    if f['status'] == 'VIAVEL_SIMULADO':
        result['A'] = dict(close_outcome(bars, baseline, variant, contract, f, bars[0].open, config, complete),
                           entered_at=iso(signal), entry_mid=bars[0].open, net_rr=f['net_rr'])
    else:
        result['A'] = {'outcome': 'BLOQUEADA', 'reasons': f['reasons']}
    trial = deepcopy(plan)
    trial.expires_at = signal + 1800  # política experimental definida antes dos resultados
    v = pullback_variant(trial, variant, contract.tick)
    result['pullback_band'] = [v.entry_low, v.entry_high]
    if v.entry_low > v.entry_high:
        result['B'] = {'outcome': 'SEM_FAIXA_DE_RECUO'}
        return jsonable(result)
    # Diagnóstico no melhor preço: mostra se existe faixa financeiramente possível.
    best_quote = v.entry_low if plan.side == 'LONG' else v.entry_high
    probe = paper_quote(trial, v, contract, best_quote, signal + 1, config, quoted=True)
    if probe['status'] != 'VIAVEL_SIMULADO':
        result['B'] = {'outcome': 'BLOQUEADA', 'reasons': probe['reasons']}
        return jsonable(result)
    result['admissible_band'] = [probe['entry_low'], probe['entry_high']]
    result['B'] = {'outcome': 'SEM_RECUO_NA_CHECAGEM'}
    sign = 1 if plan.side == 'LONG' else -1
    for i, prior in enumerate(bars):
        # Enquanto aguarda, SL/TP tocado invalida a nova entrada. Nada é preenchido
        # retroativamente com a mínima/máxima de um candle já encerrado.
        if (prior.low <= v.stop if sign == 1 else prior.high >= v.stop):
            result['B'] = {'outcome': 'CANCELADA_STOP_ANTES_DA_ENTRADA'}
            break
        if (prior.high >= v.target if sign == 1 else prior.low <= v.target):
            result['B'] = {'outcome': 'CANCELADA_ALVO_ANTES_DA_ENTRADA'}
            break
        if (prior.close <= plan.level if sign == 1 else prior.close >= plan.level):
            result['B'] = {'outcome': 'CANCELADA_PERDA_DO_NIVEL'}
            break
        if plan.strategy == 'CONTINUACAO' and structure(hourly, prior.end) != ('ALTA' if sign == 1 else 'BAIXA'):
            result['B'] = {'outcome': 'CANCELADA_ESTRUTURA'}
            break
        if i + 1 >= len(bars):
            if prior.end < trial.expires_at:
                result['B'] = {'outcome': 'OBSERVACAO_INCOMPLETA'}
            break
        c = bars[i + 1]
        if c.ts + 1 >= trial.expires_at:
            break
        f = paper_quote(trial, v, contract, c.open, c.ts + 1, config)
        if f['status'] == 'VIAVEL_SIMULADO':
            result['B'] = dict(close_outcome(bars[i + 1:], trial, v, contract, f, c.open, config, complete),
                               entered_at=iso(c.ts), entry_mid=c.open, net_rr=f['net_rr'])
            break
    return jsonable(result)


def summarize(rows, complete_only=False):
    sample = [r for r in rows if not complete_only or r.get('window_complete')]
    result = {'signals': len(sample)}
    for key in ('A', 'B'):
        values = [r[key] for r in sample]
        entries = [x for x in values if 'entered_at' in x]
        resolved = [x for x in entries if 'net_r' in x]
        result[key] = {'outcomes': dict(Counter(x['outcome'] for x in values)),
                       'blocked_reasons': dict(Counter(t for x in values for t in x.get('reasons', []))),
                       'entries': len(entries), 'closed': len(resolved),
                       'sum_r_independent': str(sum((D(x['net_r']) for x in resolved), D(0)))}
    result['B_only_entries'] = sum('entered_at' in r['B'] and 'entered_at' not in r['A'] for r in sample)
    return result


def run(report, config=None, client=None):
    config = replace(config or Config(), mode='paper', fees_verified=False, account_rules_verified=False)
    client = client or MexcClient(config.api_base)
    now = client.server_time()
    cutoff = int(report['analyzed_at'])
    if not 0 <= now - cutoff <= 1800 or report.get('source_status') != 'OK':
        raise ValueError('Relatório da fonte inválido ou desatualizado para o teste')
    signals = [r for r in report['plans'] if (v := r.get('variants', {}).get('CONFIRMADA'))
               and cutoff - 86400 <= v['triggered_at'] <= cutoff]
    catalog = {r['symbol']: r for r in client.contracts()}
    datasets, errors, rows = {}, {}, []
    for symbol in sorted({r['symbol'] for r in signals}):
        try:
            contract = Contract.from_api(catalog[symbol])
            q = parse_candles(client.candles(symbol, 'Min15', 480, now), 900, now, 480)
            h = parse_candles(client.candles(symbol, 'Min60', 240, now), 3600, now, 240)
            datasets[symbol] = (q, h, contract)
        except Exception as exc:
            errors[symbol] = type(exc).__name__
    for row in signals:
        if row['symbol'] in errors:
            rows.append({'symbol': row['symbol'], 'plan_id': row['id'], 'window_complete': False,
                         'A': {'outcome': 'SEM_DADOS'}, 'B': {'outcome': 'SEM_DADOS'}})
        else:
            q, h, c = datasets[row['symbol']]
            rows.append(review_signal(row, q, h, c, config, now))
    limitations = [
        'Sinais registrados em produção; amostra dos planos retidos no relatório das últimas 24h, não todos os trades possíveis.',
        'A usa a abertura seguinte; B aguarda uma checagem de 15m, com validade de 30m APÓS a confirmação (mudança experimental de prazo).',
        'B conserva stop/alvo e exige recuo desde o fechamento ao nível técnico; não conta toques intrabar como preenchimentos.',
        'Taxa de 0,06% por execução, spread de 0,02%, deslizamento configurado ou dois ticks por lado; funding zero hipotético.',
        'Profundidade histórica não observada; livro infinito é hipótese. Regras atuais do contrato e saldo independente de 1 USDT.',
        'Sem latência real de 1 minuto do bot; abertura seguinte é uma aproximação, não execução demonstrada.',
        'Horizon de 4h desde a confirmação. Janelas incompletas identificadas e separadas; posições abertas não são vitórias.',
        'Stop tem precedência em candle ambíguo; gaps adversos contabilizados. Planos sobrepostos são testes independentes.',
        'Soma em R não é retorno de uma carteira nem prova prospectiva; não extrapolar taxa de acerto desta amostra.',
    ]
    return jsonable({'kind': 'READ_ONLY_PULLBACK_AB', 'report_cutoff': iso(cutoff), 'observed_at': iso(now),
                     'config_fingerprint': config.fingerprint, 'summary_all': summarize(rows),
                     'summary_complete': summarize(rows, True), 'errors': errors,
                     'limitations': limitations, 'signals': rows})


def markdown(result):
    lines = ['## Confirmação imediata × recuo observado a cada 15m', '',
             'Fonte congelada em ' + result['report_cutoff'] + '; observação até ' + result['observed_at'] + '.', '',
             '| Amostra | Regra | Sinais | Entradas | Alvos | Stops (incl. ambíguos) | Abertas | Soma R independente |',
             '| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    for label, summary in [('Todas', result['summary_all']), ('Janela completa de 4h', result['summary_complete'])]:
        for key, name in [('A', 'Atual'), ('B', 'Recuo em 15m')]:
            s, o = summary[key], summary[key]['outcomes']
            lines.append(f"| {label} | {name} | {summary['signals']} | {s['entries']} | {o.get('ALVO', 0)} | "
                         f"{o.get('STOP', 0) + o.get('STOP_AMBIGUO', 0)} | {o.get('ABERTO', 0)} | {s['sum_r_independent']} |")
    lines += ['', '```json', json.dumps({k: result[k] for k in ('summary_all', 'summary_complete', 'errors')}, ensure_ascii=False, indent=2), '```', '',
              '### Hipóteses e limites', ''] + ['- ' + x for x in result['limitations']]
    lines += ['', '| Ativo | Confirmação UTC | Atual | Recuo | R do recuo |', '| --- | --- | --- | --- | ---: |']
    for row in result['signals']:
        lines.append(' | '.join(['| ' + row['symbol'], row.get('signal', '—'), row['A']['outcome'],
                                  row['B']['outcome'], row['B'].get('net_r', '—')]) + ' |')
    return '\n'.join(lines) + '\n'


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--report', required=True)
    args = parser.parse_args()
    result = run(json.loads(Path(args.report).read_text()), load_config('config/default.toml'))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if path := os.environ.get('GITHUB_STEP_SUMMARY'):
        Path(path).write_text(markdown(result))
