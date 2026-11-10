"""Teste paralelo do filtro de estrutura 1h, sem ordens ou mensagens.

Reutiliza a captura do scanner. Estado exclusivo em trend-experiment; nunca salva
scanner-state. Um período reservado é separado da coleta prospectiva de 14 dias.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
import math
import os
from pathlib import Path
import time

from mexc_scanner.config import Config, load_config
from mexc_scanner.market import parse_candles, structure
from mexc_scanner.mexc import MexcClient
from mexc_scanner.models import Candle, Contract, D, jsonable, stable_id
from mexc_scanner.state import atomic_json
from scripts import state_branch
from scripts.audit_pullback import iso
from scripts.audit_rr import review


BRANCH = 'trend-experiment'
RESERVED_SINCE = 1794308334  # 10/11/2026 10:58:54 UTC: fim da amostra já explorada
DURATION = 14 * 86400
FINAL = {'ALVO', 'STOP', 'STOP_AMBIGUO', 'BLOQUEADA'}


def calculation_hash():
    names = ['mexc_scanner/finance.py', 'mexc_scanner/market.py', 'mexc_scanner/strategies.py',
             'scripts/audit_rr.py', 'scripts/audit_pullback.py', 'scripts/trend_experiment.py']
    return hashlib.sha256(b''.join(Path(n).read_bytes() for n in names)).hexdigest()


def initialize(now, config, code_hash):
    start = (now // 900 + 1) * 900
    return {'schema_version': 1, 'protocol': {'id': 'ROMPIMENTO_ESTRUTURA_1H_V1',
            'created_at': now, 'prospective_since': start, 'end_at': start + DURATION,
            'reserved_since': RESERVED_SINCE, 'config_fingerprint': config.fingerprint,
            'calculation_hash': code_hash, 'minimum_rr': config.minimum_rr,
            'risk_fraction_planned': '0.10', 'rule': 'LONG_ALTA_SHORT_BAIXA; demais estruturas excluídas',
            'execution_model': 'ABERTURA_SEGUINTE_HIPOTETICA; sem latência real ou livro histórico'},
            'cases': {}, 'last_update': 0, 'diagnostics': []}


def eligible_variants(report, end_at):
    for p in report['plans']:
        if p['strategy'] != 'ROMPIMENTO':
            continue
        for kind, v in p.get('variants', {}).items():
            if kind in {'ANTECIPADA', 'CONFIRMADA'} and RESERVED_SINCE < v['triggered_at'] < end_at:
                yield p, kind, v


def direction_at(hourly, signal):
    known = [c for c in hourly if c.end <= signal][-240:]
    if len(known) < 240:
        raise ValueError('Histórico de 1h insuficiente na formação do sinal')
    return structure(known, signal)


def update(state, report, snapshot, config, now, code_hash):
    state = deepcopy(state)
    protocol = state['protocol']
    if protocol['config_fingerprint'] != config.fingerprint or protocol['calculation_hash'] != code_hash:
        raise ValueError('Regras/calculador mudaram; experimento pausado, sem misturar versões')
    if report.get('source_status') != 'OK' or snapshot.get('source_status') != 'OK':
        raise ValueError('Fonte não validada para o experimento')
    if not 0 <= now - int(report['analyzed_at']) <= 1800:
        raise ValueError('Relatório desatualizado para o experimento')
    catalog = {r['symbol']: r for r in snapshot.get('contracts', [])}
    market = snapshot.get('market', {})
    diagnostics = []
    for p, kind, v in eligible_variants(report, protocol['end_at']):
        key = stable_id(p['id'], kind)
        if key in state['cases']:
            continue
        try:
            h = [Candle.from_dict(c) for c in market[p['symbol']]['hourly']]
            direction = direction_at(h, v['triggered_at'])
            contract = catalog[p['symbol']]
        except (KeyError, ValueError) as exc:
            diagnostics.append({'symbol': p['symbol'], 'kind': kind, 'reason': type(exc).__name__})
            continue
        frozen = deepcopy(p)
        # O replay compartilhado espera esta chave, mas preserva os níveis do tipo original.
        frozen['variants'] = {'CONFIRMADA': deepcopy(v)}
        prospective = v['triggered_at'] >= protocol['prospective_since']
        state['cases'][key] = {'plan_id': p['id'], 'symbol': p['symbol'], 'kind': kind, 'side': p['side'],
            'signal': v['triggered_at'], 'first_seen_at': now,
            'cohort': 'PROSPECTIVA' if prospective else 'RESERVADA_PRELIMINAR',
            'timely_capture': 0 <= now - v['triggered_at'] <= config.quote_max_age,
            'structure_1h': direction,
            'aligned': direction == ('ALTA' if p['side'] == 'LONG' else 'BAIXA'),
            'plan': frozen, 'contract': deepcopy(contract), 'baseline': {'outcome': 'AGUARDANDO_CANDLE', 'window_complete': False}}
    for case in state['cases'].values():
        previous = case['baseline']
        # Um desfecho já observado não é reescolhido usando preços posteriores.
        if previous['outcome'] in FINAL:
            previous['window_complete'] = now >= case['signal'] + 14400
            continue
        if previous.get('window_complete'):
            continue
        try:
            q = [Candle.from_dict(c) for c in market[case['symbol']]['quarter']]
            contract = Contract.from_api(case['contract'])
            if not q or q[-1].end <= case['signal']:
                continue
            case['baseline'] = review(case['plan'], q, contract, config, now, '2')
        except (KeyError, ValueError) as exc:
            diagnostics.append({'symbol': case['symbol'], 'reason': type(exc).__name__})
    state['last_update'], state['diagnostics'] = now, diagnostics
    return jsonable(state)


def summarize(state, cohort, kind, complete_only=False, timely_only=False):
    sample = [c for c in state['cases'].values() if c['cohort'] == cohort and c['kind'] == kind
              and (not complete_only or c['baseline'].get('window_complete'))
              and (not timely_only or c['timely_capture'])]
    result = {'candidates': len(sample), 'structure_counts': dict(Counter(c['structure_1h'] for c in sample)),
              'capture_late': sum(not c['timely_capture'] for c in sample), 'models': {}}
    for name, values in [('ATUAL', sample), ('FILTRO_1H', [c for c in sample if c['aligned']])]:
        entries = [c['baseline'] for c in values if 'entered_at' in c['baseline']]
        closed = [v for v in entries if 'net_r' in v]
        result['models'][name] = {'candidates': len(values), 'entries': len(entries),
            'targets': sum(v['outcome'] == 'ALVO' for v in closed),
            'stops': sum(v['outcome'] in {'STOP', 'STOP_AMBIGUO'} for v in closed),
            'open': sum(v['outcome'] == 'ABERTO' for v in entries),
            'closed_r_independent': str(sum((D(v['net_r']) for v in closed), D(0))),
            'marked_r_independent': str(sum((D(v.get('net_r', v.get('mark_to_market_r', 0))) for v in entries), D(0))),
            'outcomes': dict(Counter(c['baseline']['outcome'] for c in values))}
    excluded = [c['baseline'] for c in sample if not c['aligned']]
    result['removed_winners'] = sum(v['outcome'] == 'ALVO' for v in excluded)
    result['avoided_stops'] = sum(v['outcome'] in {'STOP', 'STOP_AMBIGUO'} for v in excluded)
    return result


def result(state):
    summaries = {}
    for cohort in ('RESERVADA_PRELIMINAR', 'PROSPECTIVA'):
        summaries[cohort] = {kind: {
            'all': summarize(state, cohort, kind),
            'complete': summarize(state, cohort, kind, complete_only=True),
            'timely_complete': summarize(state, cohort, kind, complete_only=True, timely_only=True)
        } for kind in ('ANTECIPADA', 'CONFIRMADA')}
    return {'kind': 'TREND_1H_SHADOW', 'updated_at': iso(state['last_update']),
            'protocol': state['protocol'], 'summaries': summaries, 'diagnostics': state['diagnostics']}


def markdown(report):
    p = report['protocol']
    lines = ['## Experimento paralelo: rompimento a favor da estrutura de 1h', '',
        'Atualização: ' + report['updated_at'] + '.',
        'Coleta prospectiva: ' + iso(p['prospective_since']) + ' até ' + iso(p['end_at']) + '.', '',
        'LONG somente em ALTA; SHORT somente em BAIXA. INDEFINIDA/DESCONHECIDA são excluídas.',
        'ANTECIPADA e CONFIRMADA são simulações independentes, não carteiras somáveis.', '',
        '| Amostra com 4h completas | Tipo | Candidatos | Regra | Entradas | Alvos | Stops | Abertas | R encerradas |',
        '| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: |']
    for cohort, kinds in report['summaries'].items():
        for kind, data in kinds.items():
            s = data['timely_complete'] if cohort == 'PROSPECTIVA' else data['complete']
            for rule, v in s['models'].items():
                lines.append(f"| {cohort} | {kind} | {s['candidates']} | {rule} | {v['entries']} | {v['targets']} | {v['stops']} | {v['open']} | {D(v['closed_r_independent']):.3f} |")
    lines += ['', '### Como interpretar', '',
        '- O filtro só remove sinais. Contamos stops evitados e alvos bons descartados.',
        '- Amostra reservada começa após 10/11/2026 10:58:54 UTC; não foi usada nos ajustes anteriores.',
        '- Prospectiva começa após registrar este protocolo. Capturas tardias ficam separadas da comparação principal.',
        '- Novas posições precisam de até 4h para a janela completa; abertas não são vitórias.',
        '- Entrada na abertura seguinte, taxa 0,06% por lado, spread 0,02%, slippage configurado ou dois ticks, funding zero e livro infinito hipotéticos.',
        '- Usa regras do contrato congeladas na primeira captura; sem latência real e sem execução de ordens.',
        '- Soma R compara sinais independentes e sobrepostos, não o saldo de uma carteira de 1 USDT.',
        '- Nenhum alerta do bot é filtrado por este experimento. Mudanças no calculador/configuração pausam a coleta para evitar misturar regras.',
        '- 14 dias não garantem amostra suficiente; resultados permanecem exploratórios.', '', '```json',
        json.dumps(report['summaries'], ensure_ascii=False, indent=2), '```']
    return '\n'.join(lines) + '\n'


def enrich(report, snapshot, state, config):
    """Busca pública só quando a captura compartilhada não cobre o experimento."""
    now = int(time.time())
    needs = {}
    end = state['protocol']['end_at'] if state else now + DURATION
    for p, kind, v in eligible_variants(report, end):
        if state and stable_id(p['id'], kind) in state['cases']:
            continue
        needs[p['symbol']] = min(needs.get(p['symbol'], v['triggered_at']), v['triggered_at'])
    for case in (state or {}).get('cases', {}).values():
        if case['baseline']['outcome'] not in FINAL and not case['baseline'].get('window_complete'):
            needs[case['symbol']] = min(needs.get(case['symbol'], case['signal']), case['signal'])
    client = None
    market = snapshot.setdefault('market', {})
    catalog = {r['symbol']: r for r in snapshot.get('contracts', [])}
    for symbol, earliest in needs.items():
        data = market.setdefault(symbol, {})
        q = data.get('quarter', [])
        h = data.get('hourly', [])
        enough_h = sum(int(c['ts']) + 3600 <= earliest for c in h) >= 240
        try:
            if not q or not enough_h or symbol not in catalog:
                client = client or MexcClient(config.api_base)
            if not q:
                data['quarter'] = jsonable(parse_candles(client.candles(symbol, 'Min15', 480, now), 900, now, 480))
            if not enough_h:
                count = 240 + math.ceil((now - earliest) / 3600) + 4
                data['hourly'] = jsonable(parse_candles(client.candles(symbol, 'Min60', count, now), 3600, now, count))
            if symbol not in catalog:
                # Só a primeira falta de catálogo exige a lista pública completa.
                catalog.update({r['symbol']: r for r in client.contracts()})
        except Exception as exc:
            print(json.dumps({'experiment_data_warning': symbol, 'reason': type(exc).__name__}))
    snapshot['contracts'] = list(catalog.values())
    return snapshot


def run(args):
    config = load_config('config/default.toml')
    if config.mode != 'paper':
        raise ValueError('Experimento isolado disponível apenas em paper')
    # Este processo separado nunca usa a branch de estado do scanner para escrita.
    state_branch.BRANCH, state_branch.BASE_FILE = BRANCH, Path('.trend-experiment-base')
    directory = Path('.trend-experiment')
    state_branch.restore(directory)
    path = directory / 'state.json'
    state = json.loads(path.read_text()) if path.exists() else None
    if state and state.get('finished_at'):
        print(json.dumps({'trend_experiment': 'CONCLUIDO', 'finished_at': state['finished_at']}))
        return
    if args.bootstrap_report:
        report = json.loads(Path(args.bootstrap_report).read_text())
        snapshot = {'source_status': report['source_status'], 'market': {}, 'contracts': []}
    else:
        report = json.loads(Path(args.report).read_text())
        snapshot = json.loads(Path(args.snapshot).read_text())
    snapshot = enrich(report, snapshot, state, config)
    now = int(time.time())
    code_hash = calculation_hash()
    state = state or initialize(now, config, code_hash)
    state = update(state, report, snapshot, config, now, code_hash)
    if now >= state['protocol']['end_at'] + 14400:
        state['finished_at'] = now
    output = result(state)
    atomic_json(path, state)
    atomic_json(directory / 'latest/report.json', output)
    text = markdown(output)
    (directory / 'latest/report.md').parent.mkdir(parents=True, exist_ok=True)
    (directory / 'latest/report.md').write_text(text)
    state_branch.save(directory)
    if summary_path := os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(summary_path, 'a') as out:
            out.write('\n' + text)
    print(json.dumps(output, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--report', default='.scanner-state/latest/report.json')
    parser.add_argument('--snapshot', default='.scanner-state/latest/snapshot.json')
    parser.add_argument('--bootstrap-report')
    run(parser.parse_args())
