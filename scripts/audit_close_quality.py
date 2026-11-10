"""One fixed filter: confirmation close in favorable third; no extra wait."""
from collections import Counter
from copy import deepcopy
import gzip
import json
import os
from pathlib import Path

from mexc_scanner.config import Config
from mexc_scanner.market import parse_candles
from mexc_scanner.mexc import MexcClient
from mexc_scanner.models import D,jsonable
from scripts.audit_early_trigger import formations,trigger,evaluate_trigger,collect_minutes,check_ohlc,write_gzip
from scripts.audit_historical_trend import midnight
from scripts.audit_sustained_trigger import MODE,read_dataset,restore_plan,sustained,metrics,entry_key

FILTER='TERCO_FAVORAVEL'

def favorable(c,side):
    width=c.high-c.low
    if width<=0:
        return False
    distance=c.close-c.low if side=='LONG' else c.high-c.close
    return 3*distance>=2*width

def apply_filter(row,minutes):
    old=row[MODE]
    if 'signal' not in old:
        return deepcopy(old)
    c=minutes[int(row['M1']['signal'])]
    if not favorable(c,row['side']):
        return {'outcome':'FECHAMENTO_FORA_TERCO'}
    return deepcopy(old)

def summary(rows):
    out={'formations':len(rows)}
    for mode in (MODE,FILTER):
        unique={entry_key(r,mode):r[mode] for r in rows if 'entered_at' in r[mode]}
        out[mode]=metrics(list(unique.values()))
    original={entry_key(r,MODE):r for r in rows if 'entered_at' in r[MODE]}
    removed=[r for r in original.values() if 'entered_at' not in r[FILTER]]
    out['removed']=dict(Counter(r[MODE]['outcome'] for r in removed))
    return out

def finish(rows):
    return {'summary':summary(rows),'by_side':{s:summary([r for r in rows if r['side']==s]) for s in ('LONG','SHORT')},
            'trades':[r for r in rows if 'entered_at' in r[MODE]]}

def run():
    source=Path('reports/early-trigger-source')
    frozen=Path('reports/sustained-source')
    out=Path('reports/close-quality')
    out.mkdir(parents=True,exist_ok=True)
    prior=json.loads((source/'summary.json').read_text())
    cfg=Config(**prior['config']).validate()
    archive=json.loads(gzip.decompress((frozen/'all-formations.json.gz').read_bytes()))
    grouped={s:[r for r in archive if r['symbol']==s] for s in {r['symbol'] for r in archive}}
    old_rows,new_rows,errors,files=[],[],{},[]
    client=MexcClient(cfg.api_base)
    start,end=midnight('2026-10-11'),midnight('2026-10-25')
    observed=end+18000
    if client.server_time()<observed+10:
        raise ValueError('New period is not fully closed')
    for n,manifest in enumerate(prior['datasets'],1):
        symbol=manifest['symbol']
        d=read_dataset(source,manifest)
        mm={c.ts:c for c in d['minute']}
        for original in grouped.pop(symbol,[]):
            r=deepcopy(original)
            r[FILTER]=apply_filter(r,mm)
            old_rows.append(r)
        try:
            qn,hn=480+(observed-start)//900,240+(observed-start)//3600
            q=parse_candles(client.candles(symbol,'Min15',qn,observed+10),900,observed+10,qn)
            h=parse_candles(client.candles(symbol,'Min60',hn,observed+10),3600,observed+10,hn)
            m=collect_minutes(client,symbol,start,observed)
            m_by_ts={c.ts:c for c in m}
            check_ohlc(q,m_by_ts,start,observed)
            rows=[]
            for p in formations(symbol,q,d['contract'].tick,start,end):
                first=trigger(p,[m_by_ts[t] for t in range(p.formed_at,p.formed_at+1800,60)])
                a=evaluate_trigger(p,first,m_by_ts,h,d['contract'],cfg)
                b=sustained(p,a,m_by_ts,d['contract'],cfg)
                r={'id':p.id,'symbol':symbol,'side':p.side,'M1':a,MODE:b}
                r[FILTER]=apply_filter(r,m_by_ts)
                rows.append(r)
            digest=write_gzip(out/'raw-new'/f'{symbol}.json.gz',{'quarter':q,'hourly':h,'minute':m})
            files.append({'symbol':symbol,'sha256':digest,'formations':len(rows)})
            new_rows.extend(rows)
            print(json.dumps({'progress':f'{n}/{len(prior["datasets"])}','symbol':symbol,'new':summary(rows)}),flush=True)
        except Exception as exc:
            errors[symbol]={'type':type(exc).__name__,'reason':str(exc)[:160]}
            print(json.dumps({'symbol':symbol,'error':errors[symbol]}),flush=True)
    if grouped or len(old_rows)!=len(archive) or summary(old_rows)[MODE]['entries']!=57:
        raise ValueError('Frozen baseline cohort mismatch')
    result=jsonable({'kind':'CONFIRMATION_CLOSE_THIRD_FILTER','code_sha':os.environ.get('GITHUB_SHA'),
        'frozen_period':'25/10–07/11/2026','new_period':'11–24/10/2026',
        'frozen':finish(old_rows),'new_period_result':finish(new_rows),
        'selected_symbols':len(prior['datasets']),'new_analyzed_symbols':len(files),'new_errors':errors,
        'datasets':files,'limitations':[
            'Única mudança: fechamento do segundo candle M1 no terço superior para LONG ou inferior para SHORT; igualdade aceita, amplitude zero rejeitada.',
            'Sem candle adicional, sem alterar horário de entrada, TP, SL, faixa, custos ou critérios financeiros. O filtro apenas remove operações.',
            'Coleta congelada anterior validada por checksum. Período11–24/10 não foi usado neste experimento para definir ou ajustar o filtro.',
            'Mesmo universo e contratos da coleta anterior, com viés de seleção/sobrevivência. Referência1USDT e hipóteses de custos e preenchimentos anteriores.',
            'SomaR de ensaios possivelmente sobrepostos não representa carteira. Abertas após4h não entram no resultado encerrado.',
            'Comparação em novo período é histórica e limitada; não garante desempenho futuro. Nenhum limiar foi escolhido após observar os resultados.',
            'Se houver erros no período novo, os dois métodos usam somente os mesmos símbolos completos e as exclusões ficam explícitas.'
        ]})
    write_gzip(out/'all-frozen.json.gz',old_rows)
    write_gzip(out/'all-new.json.gz',new_rows)
    (out/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print('QUALITY_BEGIN')
    print(json.dumps(result,ensure_ascii=False,indent=2))
    print('QUALITY_END')

if __name__=='__main__':
    run()
