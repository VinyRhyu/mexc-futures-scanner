"""Matched historical consolidation formations: first 1m vs first 15m close.

Read-only public data. No production edits, alerts or orders. All formations are
registered from already closed bars, including those never triggered on 15m.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
from dataclasses import replace
from datetime import datetime
import gzip
import hashlib
import json
import os
from pathlib import Path
from statistics import median

from mexc_scanner.config import load_config
from mexc_scanner.market import atr, parse_candles, select_universe
from mexc_scanner.mexc import MexcClient
from mexc_scanner.models import Contract, D, Plan, ceil_step, floor_step, jsonable, stable_id
from mexc_scanner.strategies import make_variant
from scripts.audit_historical_trend import BRT, midnight
from scripts.audit_pullback import close_outcome, iso, paper_quote


def formations(symbol, quarter, tick, start, end):
    """Same consolidation geometry; formation is known BEFORE its trigger bar."""
    result = []
    for i in range(480, len(quarter)):
        at = quarter[i].ts  # No OHLC of this or later bars is read here.
        if not start <= at < end:
            continue
        known = quarter[i-479:i]
        if any(c.end > at for c in known):
            raise ValueError('Formation received an unclosed bar')
        a = atr(known, 14)[-1]
        box = known[-8:]
        lo, hi = min(c.low for c in box), max(c.high for c in box)
        if not a or not a <= hi-lo <= 4*a:
            continue
        if sum(c.high >= hi-D('.25')*a for c in box)<2 or sum(c.low <= lo+D('.25')*a for c in box)<2:
            continue
        for side, sign in [('LONG',1),('SHORT',-1)]:
            level = hi if sign==1 else lo
            stop = level-sign*D('.50')*a
            stop = floor_step(stop,tick) if sign==1 else ceil_step(stop,tick)
            pid = stable_id('EARLY_MATCHED',symbol,side,at,lo,hi)
            result.append(Plan(pid,symbol,'ROMPIMENTO',side,at,at,at+1800,a,level,lo,hi,stop,pid))
    return result


def trigger(plan, bars):
    sign = 1 if plan.side=='LONG' else -1
    threshold = plan.level+sign*D('.10')*plan.atr
    return next((c for c in bars if plan.formed_at<=c.ts and c.end<=plan.formed_at+1800
                 and sign*(c.close-threshold)>0),None)


def evaluate_trigger(plan, bar, minute_by_ts, hourly, contract, config):
    if bar is None:
        return {'outcome':'SEM_GATILHO'}
    p = deepcopy(plan)
    p.status, p.entry_started_at, p.expires_at = 'ATIVO',bar.end,bar.end+1800
    known_h = [c for c in hourly if c.end<=bar.end][-240:]
    if len(known_h)!=240:
        raise ValueError('Insufficient closed hourly history')
    v = make_variant(p,'ANTECIPADA',bar,known_h,contract.tick)
    bars = [minute_by_ts[t] for t in range(bar.end,bar.end+14400,60) if t in minute_by_ts]
    if len(bars)!=240:
        return {'outcome':'SEM_DADOS','signal':bar.end}
    price = bars[0].open
    base = {'signal':bar.end,'reference':v.reference,'entry_mid':price,'stop':v.stop,
            'target':v.target,'target_origin':v.target_origin,'entry_low':v.entry_low,'entry_high':v.entry_high}
    sign = 1 if p.side=='LONG' else -1
    fill = price*(1+sign*D('.0001'))
    # Price-path diagnostic includes blocked setups. It is never a released trade.
    if sign*(v.target-fill)>0 and sign*(fill-v.stop)>0:
        base['trajectory'] = close_outcome(bars,p,v,contract,{'base_quantity':'1'},price,config,True)
    else:
        base['trajectory'] = {'outcome':'SEM_GEOMETRIA'}
    f = paper_quote(p,v,contract,price,bar.end+1,config)
    if f['status']!='VIAVEL_SIMULADO':
        return jsonable(dict(base,outcome='BLOQUEADA',reasons=f['reasons']))
    outcome = close_outcome(bars,p,v,contract,f,price,config,True)
    return jsonable(dict(base,**outcome,entered_at=iso(bar.end),net_rr=f['net_rr'],planned_loss=f['loss_usdt']))


def evaluate_formation(plan, quarter_by_ts, minute_by_ts, hourly, contract, config):
    at = plan.formed_at
    minute = [minute_by_ts[t] for t in range(at,at+1800,60)]
    quarter = [quarter_by_ts[t] for t in range(at,at+1800,900)]
    early, normal = trigger(plan,minute),trigger(plan,quarter)
    a = evaluate_trigger(plan,normal,minute_by_ts,hourly,contract,config)
    b = evaluate_trigger(plan,early,minute_by_ts,hourly,contract,config)
    row = {'id':plan.id,'symbol':plan.symbol,'side':plan.side,'formed_at':iso(at),
           'week':'25–31/10' if at<midnight('2026-11-01') else '01–07/11',
           'level':plan.level,'lower':plan.lower,'upper':plan.upper,'atr':plan.atr,
           'M15':a,'M1':b}
    if early:
        sign = 1 if plan.side=='LONG' else -1
        enclosing = quarter_by_ts[((early.end-1)//900)*900]
        row['m1_not_sustained_at_15m_close'] = sign*(enclosing.close-plan.level-sign*D('.10')*plan.atr)<=0
        row['returned_inside_before_15m_close'] = any(sign*(c.close-plan.level)<=0 for c in minute
                                                    if early.end<=c.ts and c.end<=enclosing.end)
        if normal:
            row['lead_seconds'] = normal.end-early.end
            if row['lead_seconds']<0:
                raise ValueError('Minute trigger later than quarter trigger: source mismatch')
            row['target_changed_by_reference'] = a.get('target')!=b.get('target')
    return jsonable(row)


def summarize(rows):
    out = {'formations':len(rows)}
    for name in ('M15','M1'):
        values = [r[name] for r in rows]
        entries = [v for v in values if 'entered_at' in v]
        unique = {(r['symbol'],r['side'],r[name]['signal'],r[name]['stop'],r[name]['target']):r[name]
                  for r in rows if 'entered_at' in r[name]}
        unique_closed = [v for v in unique.values() if 'net_r' in v]
        closed = [v for v in entries if 'net_r' in v]
        paths = [v['trajectory'] for v in values if 'trajectory' in v]
        out[name] = {'triggers':sum('signal' in v for v in values),'entries':len(entries),
            'unique_entries':len(unique),
            'unique_targets':sum(v['outcome']=='ALVO' for v in unique_closed),
            'unique_stops':sum(v['outcome'] in {'STOP','STOP_AMBIGUO'} for v in unique_closed),
            'unique_open':sum(v['outcome']=='ABERTO' for v in unique.values()),
            'unique_closed_r_independent':str(sum((D(v['net_r']) for v in unique_closed),D(0))),
            'targets':sum(v['outcome']=='ALVO' for v in closed),
            'stops':sum(v['outcome'] in {'STOP','STOP_AMBIGUO'} for v in closed),
            'ambiguous':sum(v['outcome']=='STOP_AMBIGUO' for v in closed),
            'open':sum(v['outcome']=='ABERTO' for v in entries),
            'closed_r_independent':str(sum((D(v['net_r']) for v in closed),D(0))),
            'outcomes':dict(Counter(v['outcome'] for v in values)),
            'blocked':dict(Counter(x for v in values for x in v.get('reasons',[]))),
            'trajectory_all_triggers':dict(Counter(v['outcome'] for v in paths)),
            'trajectory_blocked':dict(Counter(v['trajectory']['outcome'] for v in values if v['outcome']=='BLOQUEADA'))}
    both = [r for r in rows if 'lead_seconds' in r]
    leads = [r['lead_seconds'] for r in both]
    entered_early = [r for r in rows if 'entered_at' in r['M1']]
    out['paired'] = {'m1_only_triggers':sum('signal' in r['M1'] and 'signal' not in r['M15'] for r in rows),
        'm1_only_entries':sum('entered_at' in r['M1'] and 'entered_at' not in r['M15'] for r in rows),
        'm15_only_entries':sum('entered_at' in r['M15'] and 'entered_at' not in r['M1'] for r in rows),
        'both_triggered':len(both),'strictly_earlier':sum(x>0 for x in leads),
        'median_lead_seconds':median(leads) if leads else None,
        'target_changed_by_reference':sum(r['target_changed_by_reference'] for r in both),
        'm1_not_sustained_at_15m_close':sum(r.get('m1_not_sustained_at_15m_close',False) for r in rows),
        'm1_entries_not_sustained_at_15m_close':sum(r.get('m1_not_sustained_at_15m_close',False) for r in entered_early),
        'returned_inside_before_15m_close':sum(r.get('returned_inside_before_15m_close',False) for r in rows)}
    return out


def collect_minutes(client,symbol,start,end):
    result, right = [],end
    while right>start:
        count = min(1800,(right-start)//60)
        part = parse_candles(client.candles(symbol,'Min1',count,right+10),60,right+10,count)
        result = part+result
        right -= count*60
    if (not result or result[0].ts!=start or result[-1].end!=end
            or any(a.end!=b.ts for a,b in zip(result,result[1:]))):
        raise ValueError('Minute history incomplete across request boundaries')
    return result


def check_ohlc(quarter,minute_by_ts,start,end):
    for c in quarter:
        if not start<=c.ts or c.end>end:
            continue
        group = [minute_by_ts[t] for t in range(c.ts,c.end,60)]
        if (group[0].open,max(x.high for x in group),min(x.low for x in group),group[-1].close)!=(c.open,c.high,c.low,c.close):
            raise ValueError('Minute OHLC does not match 15m source at '+iso(c.ts))


def write_gzip(path,value):
    raw = json.dumps(jsonable(value),sort_keys=True,separators=(',',':')).encode()
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_bytes(gzip.compress(raw,mtime=0))
    return hashlib.sha256(raw).hexdigest()


def run(start,end,directory,client=None,limit=50):
    cfg = replace(load_config('config/default.toml'),mode='paper',fees_verified=False,account_rules_verified=False)
    observed = end+18000  # Final formation: 30m preparation plus 4h observation.
    qn,hn = 480+(observed-start)//900,240+(observed-start)//3600
    if start>=end or start%3600 or end%3600 or max(qn,hn)>1900:
        raise ValueError('Use an aligned period of at most 14 days')
    client = client or MexcClient(cfg.api_base)
    now = client.server_time()
    if observed+10>now:
        raise ValueError('Observation period has not closed')
    catalog,tickers = client.contracts(),client.tickers()
    assets = set(json.loads(Path('config/crypto-assets.json').read_text())['assets'])
    selected,_ = select_universe(catalog,tickers,assets,D(cfg.minimum_turnover),limit)
    records,errors,datasets = [],{},[]
    for num,raw in enumerate(selected,1):
        symbol = raw['symbol']
        try:
            contract = Contract.from_api(raw)
            q = parse_candles(client.candles(symbol,'Min15',qn,observed+10),900,observed+10,qn)
            h = parse_candles(client.candles(symbol,'Min60',hn,observed+10),3600,observed+10,hn)
            plans = formations(symbol,q,contract.tick,start,end)
            m = collect_minutes(client,symbol,start,observed)
            qm,mm = {c.ts:c for c in q},{c.ts:c for c in m}
            check_ohlc(q,mm,start,observed)
            rows = [evaluate_formation(p,qm,mm,h,contract,cfg) for p in plans]
            digest = write_gzip(directory/'raw'/f'{symbol}.json.gz',
                                {'symbol':symbol,'contract':raw,'quarter':q,'hourly':h,'minute':m})
            records.extend(rows)
            datasets.append({'symbol':symbol,'quarter_bars':len(q),'hourly_bars':len(h),'minute_bars':len(m),
                             'formations':len(plans),'sha256_uncompressed':digest,'ohlc_matches':True})
            print(json.dumps({'progress':f'{num}/{len(selected)}','symbol':symbol,'summary':summarize(rows)}),flush=True)
        except Exception as exc:
            errors[symbol]={'type':type(exc).__name__,'reason':str(exc)[:200]}
            print(json.dumps({'progress':f'{num}/{len(selected)}','symbol':symbol,'error':errors[symbol]}),flush=True)
    limits = [
        'Gatilho fixo: primeiro fechamento além da borda da consolidação por 0,10 ATR; M1 versus M15, entrada na abertura do minuto seguinte.',
        'Mesmas formações causais de oito candles anteriores, largura1–4ATR, dois toques por borda; ATR14 e SL da produção. LONG/SHORT espelhados.',
        'Inclui todas as formações a cada15m, mesmo sem gatilho posterior. Não aplica supressão de planos ativos do daemon: comparação controlada de gatilhos, não replay exato da carteira/produção.',
        'Formações podem se sobrepor ou gerar execuções iguais; unique_entries identifica duplicatas exatas. SomaR é de ensaios independentes, não retorno de uma carteira.',
        'Cada formação tem30min para disparar, inclusive após a data final; primeira tentativa somente. Bloqueio não permite escolher outra entrada depois.',
        'Usa make_variant e evaluate atuais: mesma seleção/projeção de TP e mesmo SL, RR líquido>=2, saldo1USDT, risco até10%, teto20x e lote.',
        'O valor do TP pode diferir porque a mesma regra seleciona pivôs à frente da referência de cada gatilho. Não foi alterada a lógica dos pivôs.',
        'Pivôs apenas de candles1h/2h já fechados naquele minuto. Os níveis são congelados antes de consultar desfechos futuros.',
        'Janela4h por entrada; SL primeiro na ambiguidade e gaps adversos. Candle de gatilho não conta como lucro após entrada.',
        'trajectory_blocked descreve SL/TP no preço mesmo quando não há liberação financeira; não representa operação executável nem taxa de acerto do bot.',
        'Funding zero e livro infinito hipotéticos; taxa0,06% por lado, spread0,02%, slippage configurado ou dois ticks. Taxas pessoais não verificadas.',
        'Universo/liquidez e regras atuais de contratos, não sua composição histórica. Mesmos dados para os dois métodos, OHLC1m/15m verificado.',
        '25–31/10 é período ainda não analisado por este experimento; 01–07/11 já foi explorado em outras hipóteses. Não é validação prospectiva.',
        'Execução M1 exige monitoramento por minuto; o agendamento atual de15m não entrega esse preenchimento. Latência real não foi medida.'
    ]
    report = jsonable({'kind':'EARLY_TRIGGER_MATCHED_HISTORY','start_brt':datetime.fromtimestamp(start,BRT).isoformat(),
        'end_exclusive_brt':datetime.fromtimestamp(end,BRT).isoformat(),'collected_at':iso(now),
        'code_sha':os.environ.get('GITHUB_SHA'),'config_fingerprint':cfg.fingerprint,
        'config':cfg,
        'selected_symbols':len(selected),'analyzed_symbols':len(datasets),'summary':summarize(records),
        'weekly':{w:summarize([r for r in records if r['week']==w]) for w in ('25–31/10','01–07/11')},
        'by_side':{s:summarize([r for r in records if r['side']==s]) for s in ('LONG','SHORT')},
        'datasets':datasets,'errors':errors,'limitations':limits,
        'trades':[r for r in records if 'entered_at' in r['M1'] or 'entered_at' in r['M15']]})
    write_gzip(directory/'all-formations.json.gz',records)
    (directory/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    (directory/'report.md').write_text(markdown(report))
    return report


def markdown(r):
    lines=['## Antecipação do gatilho: M1 × M15','',
        f"Formações de {r['start_brt']} até {r['end_exclusive_brt']} (exclusivo). Históricos íntegros: {r['analyzed_symbols']}/{r['selected_symbols']}.",'',
        '| Período | Gatilho | Formações | Gatilhos | Entradas | Únicas | Alvos | Stops | Abertas | R encerradas |',
        '| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
    for period,s in [('Total',r['summary']),*r['weekly'].items()]:
        for name in ('M15','M1'):
            v=s[name]
            lines.append(f"| {period} | {name} | {s['formations']} | {v['triggers']} | {v['entries']} | {v['unique_entries']} | {v['targets']} | {v['stops']} | {v['open']} | {D(v['closed_r_independent']):.3f} |")
    lines+=['','### Comportamento pareado','', '```json',json.dumps(r['summary']['paired'],ensure_ascii=False,indent=2),'```',
            '','### Limites','']+['- '+x for x in r['limitations']]
    lines+=['','### Erros','', '```json',json.dumps(r['errors'],ensure_ascii=False,indent=2),'```']
    return '\n'.join(lines)+'\n'


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--start',default='2026-10-25')
    parser.add_argument('--end',default='2026-11-08')
    parser.add_argument('--output',default='reports/early-trigger-history')
    args=parser.parse_args()
    result=run(midnight(args.start),midnight(args.end),Path(args.output))
    print('EARLY_RESULT_BEGIN',flush=True)
    print(json.dumps(result,ensure_ascii=False,indent=2),flush=True)
    print('EARLY_RESULT_END',flush=True)
    if path:=os.environ.get('GITHUB_STEP_SUMMARY'):
        Path(path).write_text(markdown(result))
    if not result['analyzed_symbols']:
        raise SystemExit('Nenhum histórico completo disponível')
