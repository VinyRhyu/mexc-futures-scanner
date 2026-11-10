"""Frozen-data comparison: first M1 trigger vs its immediately following close.

Uses the previous historical collection without contacting MEXC or changing the
live scanner. A failed second candle ends the attempt; no later replacements.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import datetime
import gzip
import hashlib
import json
import os
from pathlib import Path

from mexc_scanner.config import Config
from mexc_scanner.models import Candle, Contract, D, Plan, Variant, jsonable
from scripts.audit_early_trigger import check_ohlc, evaluate_trigger, write_gzip
from scripts.audit_pullback import close_outcome, iso, paper_quote


SOURCE_RUN = 'https://github.com/VinyRhyu/mexc-futures-scanner/actions/runs/42879077420'
MODE = 'M1_SUSTENTADA'


def restore_plan(row):
    first = row['M1']
    at = int(datetime.fromisoformat(row['formed_at']).timestamp())
    return Plan(row['id'],row['symbol'],'ROMPIMENTO',row['side'],at,at,at+1800,
                D(row['atr']),D(row['level']),D(row['lower']),D(row['upper']),D(first['stop']),row['id'])


def restore_variant(first):
    return Variant('ANTECIPADA',int(first['signal']),D(first['reference']),D(first['entry_low']),
                   D(first['entry_high']),D(first['stop']),D(first['target']),first['target_origin'])


def sustained(plan, first, minutes, contract, config):
    if 'signal' not in first:
        return {'outcome':'SEM_GATILHO'}
    signal = int(first['signal'])
    v = restore_variant(first)  # All levels frozen at the first closed minute.
    c = minutes.get(signal)
    if c is None or c.tf!=60 or c.end!=signal+60:
        return {'outcome':'SEM_DADOS'}
    sign = 1 if plan.side=='LONG' else -1
    base = {'original_signal':signal,'confirmation_end':c.end,'stop':v.stop,'target':v.target,
            'target_origin':v.target_origin,'entry_low':v.entry_low,'entry_high':v.entry_high}
    stop_hit = c.low<=v.stop if sign==1 else c.high>=v.stop
    target_hit = c.high>=v.target if sign==1 else c.low<=v.target
    if stop_hit or target_hit:
        reason = ('STOP_E_ALVO_ANTES_DA_ENTRADA' if stop_hit and target_hit else
                  'STOP_ANTES_DA_ENTRADA' if stop_hit else 'ALVO_ANTES_DA_ENTRADA')
        return jsonable(dict(base,outcome=reason))
    threshold = plan.level+sign*D('.10')*plan.atr
    if sign*(c.close-threshold)<=0:
        return jsonable(dict(base,outcome='NAO_SUSTENTOU_SEGUNDO_FECHAMENTO'))
    bars = [minutes[t] for t in range(c.end,c.end+14400,60) if t in minutes]
    if len(bars)!=240:
        return jsonable(dict(base,outcome='SEM_DADOS'))
    p = deepcopy(plan)
    p.status,p.entry_started_at,p.expires_at = 'ATIVO',signal,signal+1800
    price = bars[0].open
    base.update(signal=c.end,reference=v.reference,confirmation_close=c.close,entry_mid=price)
    f = paper_quote(p,v,contract,price,c.end+1,config)
    if f['status']!='VIAVEL_SIMULADO':
        return jsonable(dict(base,outcome='BLOQUEADA',reasons=f['reasons']))
    outcome = close_outcome(bars,p,v,contract,f,price,config,True)
    return jsonable(dict(base,**outcome,entered_at=iso(c.end),net_rr=f['net_rr'],planned_loss=f['loss_usdt']))


def entry_key(row,mode):
    v = row[mode]
    return row['symbol'],row['side'],v['signal'],v['stop'],v['target']


def metrics(values):
    closed = [v for v in values if 'net_r' in v]
    positive = sum((D(v['net_r']) for v in closed if D(v['net_r'])>0),D(0))
    negative = -sum((D(v['net_r']) for v in closed if D(v['net_r'])<0),D(0))
    targets = sum(v['outcome']=='ALVO' for v in closed)
    return {'entries':len(values),'targets':targets,
        'stops':sum(v['outcome'] in {'STOP','STOP_AMBIGUO'} for v in closed),
        'ambiguous':sum(v['outcome']=='STOP_AMBIGUO' for v in closed),
        'open':sum(v['outcome']=='ABERTO' for v in values),
        'win_rate_closed':str(D(targets)/len(closed)) if closed else None,
        'positive_r':str(positive),'negative_r':str(negative),
        'net_r':str(sum((D(v['net_r']) for v in closed),D(0)))}


def summary(rows):
    result = {'formations':len(rows)}
    for mode in ('M1',MODE):
        all_values = [r[mode] for r in rows]
        entries = [v for v in all_values if 'entered_at' in v]
        unique = {entry_key(r,mode):r[mode] for r in rows if 'entered_at' in r[mode]}
        result[mode] = {'all_entries':metrics(entries),'unique':metrics(list(unique.values())),
            'outcomes':dict(Counter(v['outcome'] for v in all_values)),
            'blocked':dict(Counter(x for v in all_values for x in v.get('reasons',[])))}
    # Same deterministic deduplication as the previous baseline's unique entries.
    paired = {entry_key(r,'M1'):r for r in rows if 'entered_at' in r['M1']}
    sample = list(paired.values())
    is_stop = lambda v:v['outcome'] in {'STOP','STOP_AMBIGUO'}
    result['paired_baseline_unique'] = {
        'cases':len(sample),
        'baseline_stops_not_entered':sum(is_stop(r['M1']) and 'entered_at' not in r[MODE] for r in sample),
        'baseline_targets_not_entered':sum(r['M1']['outcome']=='ALVO' and 'entered_at' not in r[MODE] for r in sample),
        'baseline_stops_turned_targets':sum(is_stop(r['M1']) and r[MODE]['outcome']=='ALVO' for r in sample),
        'baseline_targets_turned_stops':sum(r['M1']['outcome']=='ALVO' and is_stop(r[MODE]) for r in sample),
        'baseline_stops_still_stops':sum(is_stop(r['M1']) and is_stop(r[MODE]) for r in sample)}
    result['new_entries_from_baseline_blocked'] = sum('entered_at' in r[MODE] and r['M1']['outcome']=='BLOQUEADA' for r in rows)
    return result


def read_dataset(directory,manifest):
    raw = gzip.decompress((directory/'raw'/f"{manifest['symbol']}.json.gz").read_bytes())
    if hashlib.sha256(raw).hexdigest()!=manifest['sha256_uncompressed']:
        raise ValueError('Source checksum differs: '+manifest['symbol'])
    data = json.loads(raw)
    result = {}
    for key,tf in [('quarter',900),('hourly',3600),('minute',60)]:
        bars = [Candle.from_dict(c) for c in data[key]]
        for c in bars:
            c.validate()
            if c.tf!=tf:
                raise ValueError('Wrong candle timeframe')
        if len(bars)!=manifest[key+'_bars'] or any(a.end!=b.ts for a,b in zip(bars,bars[1:])):
            raise ValueError('Source candle history is incomplete')
        result[key] = bars
    result['contract'] = Contract.from_api(data['contract'])
    return result


def run(source,directory):
    prior = json.loads((source/'summary.json').read_text())
    if prior['kind']!='EARLY_TRIGGER_MATCHED_HISTORY' or prior['errors'] or prior['analyzed_symbols']!=prior['selected_symbols']:
        raise ValueError('Original collection is not the complete expected experiment')
    cfg = Config(**prior['config']).validate()
    if cfg.mode!='paper' or cfg.fingerprint!=prior['config_fingerprint']:
        raise ValueError('Original paper configuration differs')
    original = json.loads(gzip.decompress((source/'all-formations.json.gz').read_bytes()))
    if len(original)!=prior['summary']['formations'] or len({r['id'] for r in original})!=len(original):
        raise ValueError('Original formation cohort is incomplete or duplicated')
    by_symbol = defaultdict(list)
    for row in original:
        by_symbol[row['symbol']].append(row)
    records,checked = [],0
    for num,manifest in enumerate(prior['datasets'],1):
        symbol = manifest['symbol']
        data = read_dataset(source,manifest)
        m = {c.ts:c for c in data['minute']}
        check_ohlc(data['quarter'],m,data['minute'][0].ts,data['minute'][-1].end)
        rows = by_symbol.pop(symbol,[])
        if len(rows)!=manifest['formations']:
            raise ValueError('Formation count differs for '+symbol)
        processed = []
        for old in rows:
            row = deepcopy(old)
            if 'signal' not in old['M1']:
                row[MODE] = {'outcome':'SEM_GATILHO'}
            else:
                plan = restore_plan(old)
                bar = m[int(old['M1']['signal'])-60]
                rebuilt = evaluate_trigger(plan,bar,m,data['hourly'],data['contract'],cfg)
                if rebuilt!=old['M1']:
                    raise ValueError('Baseline differs from frozen collection: '+old['id'])
                checked += 1
                row[MODE] = sustained(plan,old['M1'],m,data['contract'],cfg)
            records.append(row)
            processed.append(row)
        print(json.dumps({'progress':f'{num}/{len(prior["datasets"])}','symbol':symbol,'summary':summary(processed)}),flush=True)
    if by_symbol or len(records)!=len(original):
        raise ValueError('Original universe not fully reconstructed')
    s = summary(records)
    for key,new_key in [('entries','entries'),('targets','targets'),('stops','stops'),('open','open')]:
        if s['M1']['unique'][new_key]!=prior['summary']['M1']['unique_'+key]:
            raise ValueError('Baseline unique summary mismatch')
    if D(s['M1']['unique']['net_r'])!=D(prior['summary']['M1']['unique_closed_r_independent']):
        raise ValueError('Baseline net R mismatch')
    report = jsonable({'kind':'SUSTAINED_TRIGGER_FROZEN_HISTORY','source_run':SOURCE_RUN,
        'source_code_sha':prior['code_sha'],'code_sha':os.environ.get('GITHUB_SHA'),
        'start_brt':prior['start_brt'],'end_exclusive_brt':prior['end_exclusive_brt'],
        'analyzed_symbols':len(prior['datasets']),'formations':len(records),'baseline_checked_triggers':checked,
        'config_fingerprint':cfg.fingerprint,'summary':s,
        'weekly':{w:summary([r for r in records if r['week']==w]) for w in prior['weekly']},
        'by_side':{side:summary([r for r in records if r['side']==side]) for side in ('LONG','SHORT')},
        'source_datasets':prior['datasets'],
        'limitations':[
            'Mesmo universo, candles, contratos e configuração da coleta anterior. Checksums e OHLC validados; todos os gatilhos M1 reconstruídos idênticos antes do teste.',
            'Exige apenas o candle1m imediatamente seguinte ao primeiro gatilho: fechamento também além da borda por0,10ATR. Não exige novo topo/fundo e não procura substituto se falhar.',
            'TP, SL e faixa originais congelados no primeiro gatilho. Não recalcula pivôs com a confirmação. SL/TP tocado durante a espera cancela a nova entrada.',
            'Entrada na abertura seguinte à confirmação; mesmo validador financeiro e custos. Janela4h desde cada entrada; abertas separadas e stop primeiro na ambiguidade.',
            'Primeiro gatilho é elegível dentro dos30min da formação; confirmação pode ocorrer um minuto depois desse prazo, dentro da validade do primeiro gatilho.',
            'Inclui todas as formações, inclusive sem gatilho M15 ou bloqueadas no primeiro M1. Não aplica a supressão de planos ativos da produção.',
            'Deduplicação remove somente execuções exatamente iguais. Formações e posições podem se sobrepor; somaR não é evolução de carteira nem saldo reproduzível.',
            'O teste anterior usou referência de1USDT, risco até10%, teto20x, taxa0,06% por lado, spread0,02%, slippage configurado ou2ticks; funding zero e livro infinito hipotéticos.',
            'Regra definida após observar os resultados anteriores das mesmas duas semanas; análise exploratória, sem validação fora da amostra. Não escolher ajustes retroativamente.',
            'Dados/contratos congelados refletem universo elegível da coleta, não a composição histórica. Exige monitoramento por minuto; cron atual de15min não entrega esses fills.',
            'Diferenças pareadas indicam stops evitados e acertos perdidos; não permitem identificar antecipadamente quais trades vencerão.'
        ],
        'trades':[r for r in records if 'entered_at' in r['M1'] or 'entered_at' in r[MODE]]})
    write_gzip(directory/'all-formations.json.gz',records)
    (directory/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    (directory/'report.md').write_text(markdown(report))
    return report


def markdown(r):
    lines=['## Segundo fechamento M1: teste em coleta congelada','',
        f"Históricos: {r['analyzed_symbols']} criptos. Formações: {r['formations']}. Gatilhos anteriores reconstruídos idênticos: {r['baseline_checked_triggers']}.",'',
        '| Período | Regra | Entradas únicas | Alvos | Stops | Abertas | R encerradas |',
        '| --- | --- | ---: | ---: | ---: | ---: | ---: |']
    for period,s in [('Total',r['summary']),*r['weekly'].items()]:
        for name in ('M1',MODE):
            v=s[name]['unique']
            lines.append(f"| {period} | {name} | {v['entries']} | {v['targets']} | {v['stops']} | {v['open']} | {D(v['net_r']):.3f} |")
    lines+=['','### Comparação das entradas originais','', '```json',
            json.dumps(r['summary']['paired_baseline_unique'],ensure_ascii=False,indent=2),'```','',
            '### Limites','']+['- '+x for x in r['limitations']]
    return '\n'.join(lines)+'\n'


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--source',default='reports/early-trigger-source')
    parser.add_argument('--output',default='reports/sustained-trigger-history')
    args=parser.parse_args()
    result=run(Path(args.source),Path(args.output))
    print('SUSTAINED_RESULT_BEGIN',flush=True)
    print(json.dumps(result,ensure_ascii=False,indent=2),flush=True)
    print('SUSTAINED_RESULT_END',flush=True)
    if path:=os.environ.get('GITHUB_STEP_SUMMARY'):
        Path(path).write_text(markdown(result))
