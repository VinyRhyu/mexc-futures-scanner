"""Read-only frozen MEXC vs OKX OI/taker participation study.
All features use completed hourly metrics available before MEXC trigger.
Different venues: cross-exchange proxy only, no orders.
"""
from __future__ import annotations
import gzip, json, time
from collections import Counter
from datetime import datetime,timezone
from decimal import Decimal as D
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.parse import urlencode

H = 3600_000
MODES = ('M1','M1_SUSTENTADA')
WEEK2 = 1793502000
BASE = 'https://www.okx.com/api/v5/rubik/stat/'

def cohort(path):
    with gzip.open(path, 'rt') as f: source=json.load(f)
    all_modes={}
    for mode in MODES:
        uniq={}
        for row in source:
            v=row[mode]
            if 'entered_at' not in v:continue
            key=(row['symbol'],row['side'],int(v['signal']),v['stop'],v['target'])
            uniq[key]=dict(symbol=row['symbol'],side=row['side'],signal=int(v['signal']),
                           outcome=v['outcome'],net_r=v.get('net_r'),
                           week='25-31/10' if int(v['signal'])<WEEK2 else '01-07/11')
        all_modes[mode]=list(uniq.values())
    return all_modes

def get(endpoint,inst,cursor):
    params=dict(instId=inst,period='1H',limit=100,end=cursor)
    url=BASE+endpoint+'?'+urlencode(params)
    last=None
    for attempt in range(3):
        try:
            req=Request(url,headers={'Accept':'application/json','User-Agent':'research-participation/1'})
            with urlopen(req,timeout=20) as response:
                body=json.loads(response.read().decode())
            if str(body.get('code'))!='0':raise ValueError('OKX '+str(body.get('code'))+': '+str(body.get('msg'))[:150])
            rows=body.get('data')
            if not isinstance(rows,list):raise ValueError('non-list data')
            return rows
        except Exception as e:
            last=type(e).__name__+': '+str(e)[:170]
            time.sleep(attempt+1)
    raise RuntimeError(last)

def history(endpoint,inst,start,end):
    cursor=end
    rows={}
    reached=False
    for page in range(14):
        batch=get(endpoint,inst,cursor)
        if not batch: break
        for row in batch:
            if isinstance(row,list) and row: rows[int(row[0])]=row
        oldest=min(int(row[0]) for row in batch)
        if oldest<=start:
            reached=True
            break
        if oldest>=cursor:raise RuntimeError('Pagination did not advance')
        cursor=oldest
        time.sleep(.22)
    else:raise RuntimeError('Exhausted pagination budget')
    if not reached:raise RuntimeError(f'Incomplete OI/taker series: oldest={min(rows) if rows else None} start={start}')
    return rows

def nearest(rows,cutoff):
    timestamps=[ts for ts in rows if ts<=cutoff]
    return rows[max(timestamps)] if timestamps else None

def features(signal,oi,taker):
    cutoff=signal*1000-H
    a=nearest(oi,cutoff);b=nearest(taker,cutoff)
    if a is None or b is None:return None,'NOT_FOUND'
    oi_ts=int(a[0]);flow_ts=int(b[0])
    if cutoff-oi_ts>2*H or cutoff-flow_ts>2*H:return None,'STALE'
    prev=nearest(oi,oi_ts-3*H)
    if prev is None or oi_ts-3*H-int(prev[0])>2*H:return None,'MISSING_OI_LOOKBACK'
    base=D(str(prev[3]));now=D(str(a[3])) # OKX [ts,oi,oiCcy,oiUsd]
    recent=[taker.get(flow_ts-i*H) for i in range(3)]
    if None in recent:return None,'MISSING_TAKER_HOURS'
    # OKX contract taker returns [ts,sellVol,buyVol], sell FIRST.
    buys=sum((D(str(x[2])) for x in recent),D(0))
    sells=sum((D(str(x[1])) for x in recent),D(0))
    if min(base,now,buys,sells)<=0:return None,'NONPOSITIVE_VOLUME'
    return dict(oi_pct_3h=float((now/base-1)*100),buy_sell_ratio_3h=float(buys/sells),
                oi_known_ts=oi_ts,flow_known_ts=flow_ts),None

def metrics(rows):
    closed=[r for r in rows if r['net_r'] is not None]
    total=sum((D(str(r['net_r'])) for r in closed),D(0))
    wins=sum(r['outcome']=='ALVO' for r in closed)
    return dict(entries=len(rows),closed=len(closed),wins=wins,stops=sum(r['outcome'] in ('STOP','STOP_AMBIGUO') for r in closed),
                open=len(rows)-len(closed),win_rate=round(100*wins/len(closed),2) if closed else None,
                sum_net_r=round(float(total),5),mean_net_r=round(float(total)/len(closed),5) if closed else None)

def main():
    results=Path('reports/flow-research');results.mkdir(parents=True,exist_ok=True)
    modes=cohort('reports/sustained-source/all-formations.json.gz')
    symbols=sorted({r['symbol'] for ts in modes.values() for r in ts})
    begin=min(r['signal'] for group in modes.values() for r in group)*1000-10*H
    end=max(r['signal'] for group in modes.values() for r in group)*1000+H
    raw={};diagnostics={}
    for n,symbol in enumerate(symbols,1):
        inst=symbol.replace('_','-')+'-SWAP'
        try:
            oi=history('contracts/open-interest-history',inst,begin,end)
            tk=history('taker-volume-contract',inst,begin,end)
            raw[symbol]=(oi,tk)
            diagnostics[symbol]=dict(oi=len(oi),taker=len(tk),oldest_oi=min(oi),oldest_taker=min(tk))
        except Exception as e: diagnostics[symbol]=dict(error=f'{type(e).__name__}: {str(e)[:170]}')
        print('DATA',n,len(symbols),symbol,json.dumps(diagnostics[symbol]),flush=True)
        time.sleep(.25)
    with gzip.open(results/'okx_raw_series.json.gz','wt',encoding='utf-8') as stream:
        json.dump({s:{'oi':list(pair[0].values()),'taker':list(pair[1].values())} for s,pair in raw.items()},stream)
    result={};records=[]
    for mode,trades in modes.items():
        joined=[];missing=Counter()
        for trade in trades:
            if trade['symbol'] not in raw:
                missing['SOURCE_NOT_AVAILABLE']+=1; continue
            feat,err=features(trade['signal'],*raw[trade['symbol']])
            if err:
                missing[err]+=1;continue
            agree=(feat['buy_sell_ratio_3h']>1 if trade['side']=='LONG' else feat['buy_sell_ratio_3h']<1)
            x=dict(trade,**feat,flow_aligned=agree,oi_up=feat['oi_pct_3h']>0)
            joined.append(x);records.append(dict(x,mode=mode))
        groups={'baseline_pareado':joined,
                'agressao_alinhada':[r for r in joined if r['flow_aligned']],
                'oi_crescente':[r for r in joined if r['oi_up']],
                'ambos':[r for r in joined if r['flow_aligned'] and r['oi_up']],
                'nao_ambos':[r for r in joined if not(r['flow_aligned'] and r['oi_up'])]}
        result[mode]=dict(total_original=metrics(trades),matched=len(joined),missing=dict(missing),
                          groups={name:metrics(v) for name,v in groups.items()},
                          weekly={w:{name:metrics([r for r in v if r['week']==w]) for name,v in groups.items()}
                                  for w in ('25-31/10','01-07/11')})
    payload=dict(kind='FROZEN_MEXC_VS_OKX_OI_TAKER_HOURLY',created_at=datetime.now(timezone.utc).isoformat(),
                 source='OKX public Rubik; one-hour lag; OI USD and contract taker volume',
                 data_source_coverage=diagnostics,results=result,
                 limitations=['Cross-venue proxy, not MEXC native OI or taker flows',
                              'Previously explored MEXC historical cohort, NOT out-of-sample',
                              'Only data with OKX timestamp <= signal minus 1h used',
                              '4h-unclosed trades excluded from PnL; no realized portfolio ROI',
                              'Changes only signal selection, not frozen SL/TP/fills/costs',
                              'No trading orders or scanner modifications'])
    (results/'result.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2))
    (results/'matched.json').write_text(json.dumps(records,ensure_ascii=False,indent=2))
    print('RESULT',json.dumps(result,ensure_ascii=False),flush=True)
    if not records:print('INCONCLUSIVE_NO_MATCHED_OI_TAKER',flush=True)
if __name__=='__main__':main()
