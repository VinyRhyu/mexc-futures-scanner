"""Read-only OI/taker research. Uses frozen MEXC labels, never sends orders."""
import gzip, json, time
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal as D
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urlencode
H=3600000
MODES=('M1','M1_SUSTENTADA')
START_WEEK2=1793502000

def cohorts(path):
    with gzip.open(path,'rt') as f: rows=json.load(f)
    out={}
    for mode in MODES:
        distinct={}
        for r in rows:
            v=r[mode]
            if 'entered_at' not in v: continue
            key=(r['symbol'],r['side'],v['signal'],v['stop'],v['target'])
            distinct[key]={'symbol':r['symbol'],'side':r['side'],'signal':int(v['signal']),
                           'week':'25-31/10' if int(v['signal'])<START_WEEK2 else '01-07/11',
                           'outcome':v['outcome'],'net_r':v.get('net_r')}
        out[mode]=list(distinct.values())
    return out

def download(symbol,kind,start,end):
    url='https://fapi.binance.com/futures/data/'+kind+'?'+urlencode(dict(symbol=symbol.replace('_',''),period='1h',startTime=start,endTime=end,limit=500))
    last=None
    for attempt in range(3):
        try:
            with urlopen(Request(url,headers={'User-Agent':'mexc-flow-research/1'}),timeout=20) as response:
                data=json.loads(response.read().decode())
            if not isinstance(data,list): raise ValueError(str(data)[:200])
            return sorted(data,key=lambda x:int(x['timestamp']))
        except Exception as e:
            last=type(e).__name__+': '+str(e)[:200]
            time.sleep(attempt+1)
    raise RuntimeError(last)

def past(rows,cutoff):
    selected=[r for r in rows if int(r['timestamp'])<=cutoff]
    return selected[-1] if selected else None

def features(t,oi,flow):
    # One full extra hour of delay prevents observing an unfinished hourly bucket.
    cutoff=t*1000-H
    x=past(oi,cutoff);y=past(flow,cutoff)
    if not x or not y:return None,'NO_PRIOR_DATA'
    ox=int(x['timestamp']);fy=int(y['timestamp'])
    if cutoff-ox>2*H or cutoff-fy>2*H:return None,'STALE'
    z=past(oi,ox-3*H)
    if not z or ox-3*H-int(z['timestamp'])>2*H:return None,'NO_PRIOR_OI'
    a=D(str(z.get('sumOpenInterestValue',0)));b=D(str(x.get('sumOpenInterestValue',0)))
    window=[r for r in flow if fy-2*H<=int(r['timestamp'])<=fy]
    if [int(r['timestamp']) for r in window]!=[fy-2*H,fy-H,fy]:return None,'INCOMPLETE_FLOW'
    buy=sum((D(str(r.get('buyVol',0))) for r in window),D(0))
    sell=sum((D(str(r.get('sellVol',0))) for r in window),D(0))
    if min(a,b,buy,sell)<=0:return None,'INVALID_VALUES'
    return {'oi_3h_pct':float((b/a-1)*100),'buy_sell_ratio_3h':float(buy/sell),
            'oi_timestamp':ox,'flow_timestamp':fy},None

def summary(rows):
    closed=[r for r in rows if r['net_r'] is not None]
    pnl=sum((D(str(x['net_r'])) for x in closed),D(0))
    wins=sum(x['outcome']=='ALVO' for x in closed)
    return dict(n=len(rows),closed=len(closed),wins=wins,stops=sum(x['outcome'] in ('STOP','STOP_AMBIGUO') for x in closed),
                open=len(rows)-len(closed),win_pct=round(100*wins/len(closed),2) if closed else None,
                net_r=round(float(pnl),4),mean_r=round(float(pnl)/len(closed),4) if closed else None)

def run():
    base=Path('reports/sustained-source/all-formations.json.gz')
    out=Path('reports/flow-research');out.mkdir(parents=True,exist_ok=True)
    data=cohorts(base)
    symbols=sorted({t['symbol'] for trades in data.values() for t in trades})
    first=min(t['signal'] for a in data.values() for t in a)*1000-9*H
    last=max(t['signal'] for a in data.values() for t in a)*1000
    market={};sources={}
    for i,s in enumerate(symbols):
        try:
            o=download(s,'openInterestHist',first,last)
            f=download(s,'takerlongshortRatio',first,last)
            market[s]=(o,f); sources[s]=dict(oi=len(o),taker=len(f))
        except Exception as e:sources[s]=dict(error=str(e))
        print('SOURCE',i+1,len(symbols),s,json.dumps(sources[s]),flush=True)
        if i==1 and all('error' in sources[s] for s in symbols[:2]):break
    result={};joined=[]
    for mode,trades in data.items():
        selected=[];missing=Counter()
        for t in trades:
            if t['symbol'] not in market:missing['SOURCE_UNAVAILABLE']+=1;continue
            obs,error=features(t['signal'],*market[t['symbol']])
            if error:missing[error]+=1;continue
            row=dict(t,**obs,flow_aligned=obs['buy_sell_ratio_3h']>1 if t['side']=='LONG' else obs['buy_sell_ratio_3h']<1,oi_up=obs['oi_3h_pct']>0)
            selected.append(row);joined.append(dict(row,mode=mode))
        groups=dict(baseline=selected,flow_aligned=[x for x in selected if x['flow_aligned']],
                    oi_up=[x for x in selected if x['oi_up']],both=[x for x in selected if x['flow_aligned'] and x['oi_up']],
                    not_both=[x for x in selected if not(x['flow_aligned'] and x['oi_up'])])
        result[mode]=dict(total_original=summary(trades),source_matched=len(selected),missing=dict(missing),
                          all={k:summary(v) for k,v in groups.items()},
                          weekly={w:{k:summary([r for r in v if r['week']==w]) for k,v in groups.items()} for w in ('25-31/10','01-07/11')})
    doc=dict(kind='MEXC_FROZEN_VS_BINANCE_FUTURES_FLOW',created=datetime.now(timezone.utc).isoformat(),
             data_sources=sources,results=result,
             limitations=['Historical previously studied; in-sample exploration only','Binance is a different venue than MEXC',
                          'Only 1h-lagged hourly metrics are available to each signal','Coverage-matched baseline required',
                          'OI delta is not directional by itself','R-sum is not chronological compounded ROI',
                          'Simulated exchange costs, no real trades or scanner changes'])
    (out/'result.json').write_text(json.dumps(doc,indent=2))
    (out/'matched.json').write_text(json.dumps(joined,indent=2))
    print('RESULT',json.dumps(result),flush=True)
    if not joined: print('INCONCLUSIVE_NO_MATCHED_SERIES',flush=True)
if __name__=='__main__':run()
