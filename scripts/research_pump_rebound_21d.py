"""Causal PUMP M1 rebound scan on Gate USDT perpetuals. READ ONLY.
Fixed rule saved by user: reject lower 15 M1, reclaim, next 5 M1
close over rejection high without lower low, enter next open, SL at
rejection low, TP +2.67%, timeout 125 minutes.
"""
import csv,json,time,os
from collections import Counter
from datetime import datetime
from zoneinfo import ZoneInfo
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from urllib.parse import urlencode
from pathlib import Path
TZ=ZoneInfo('America/Sao_Paulo')
START=int(datetime(2026,10,31,14,tzinfo=TZ).timestamp())
END=int(datetime(2026,11,21,14,tzinfo=TZ).timestamp())
SYMBOLS=('PUMP TAO AVAX HYPE BTC ETH SOL SUI LINK INJ ENA DOT AERO TRX QNT '
         'ETHFI AAVE UNI PEPE ZEC STX HBAR GALA ADA DOGE BCH BNB OP ONDO XRP '
         'NEAR LTC PENGU FIL ETC APT ARB ALGO CRV RENDER DASH BERA INIT JTO MORPHO').split()
OUT=Path('reports/pump-causal-21d')
def br(t):return datetime.fromtimestamp(t,TZ).strftime('%d/%m/%Y %H:%M')
def request(symbol,a,b):
    url='https://api.bybit.com/v5/market/kline?'+urlencode(
        dict(category='linear',symbol=symbol+'USDT',interval='1',start=a*1000,end=b*1000,limit=1000))
    for attempt in range(4):
        try:
            with urlopen(Request(url,headers={'Accept':'application/json','User-Agent':'pump-m1-research/1'}),timeout=25) as response:
                d=json.loads(response.read().decode())
            if str(d.get('retCode'))!='0':raise ValueError('Bybit '+str(d.get('retCode'))+': '+str(d.get('retMsg'))[:150])
            batch=d.get('result',{}).get('list',[])
            if not isinstance(batch,list):raise ValueError('Non-list market response')
            return batch
        except HTTPError as e:
            if e.code in (400,404,422):raise ValueError('HTTP '+str(e.code)+' '+e.read().decode(errors='replace')[:400])
            err=str(e)
        except Exception as e:err=str(e)
        time.sleep(1.3*(attempt+1))
    raise RuntimeError(err)
def candles(symbol):
    a=START-18*60;data={};calls=0
    while a<END:
        b=min(a+899*60,END-60)
        batch=request(symbol,a,b);calls+=1
        for x in batch:
            ts=int(x[0])//1000;r=(ts,float(x[1]),float(x[2]),float(x[3]),float(x[4]))
            if ts in data and data[ts]!=r:raise ValueError('Inconsistent OHLC')
            data[ts]=r
        a=b+60;time.sleep(.16)
    bars=sorted(data.values())
    if len(bars)<100:raise ValueError('No full history')
    gaps=sum(max(0,(z[0]-y[0])//60-1) for y,z in zip(bars,bars[1:]))
    return bars,dict(calls=calls,bars=len(bars),missing_minutes=gaps,
                     first=br(bars[0][0]),last=br(bars[-1][0]))
def scan(symbol,bars):
    signals={};stats=Counter()
    index={r[0]:i for i,r in enumerate(bars)}
    for i in range(15,len(bars)-7):
        t,o,h,l,c=bars[i]
        if t<START or t>=END:continue
        if any(bars[j+1][0]!=bars[j][0]+60 for j in range(i-15,i)):continue
        old=min(x[3] for x in bars[i-15:i])
        if not(l<old and c>old):continue
        stats['pre_alert']+=1
        for j in range(i+1,i+6):
            tt,oo,hh,ll,cc=bars[j]
            if tt!=t+(j-i)*60:stats['missing_confirmation_data']+=1;break
            if ll<l:stats['invalidated']+=1;break
            if cc>h:
                if bars[j+1][0]!=tt+60:stats['missing_entry_bar']+=1;break
                et,ep=bars[j+1][0],bars[j+1][1]
                if et>=END:stats['outside_window']+=1;break
                if ep<=l:stats['invalid_entry']+=1;break
                item=dict(symbol=symbol+'_USDT',reject_ts=t,confirm_ts=tt+60,entry_ts=et,
                          reject_brt=br(t),confirm_brt=br(tt+60),entry_brt=br(et),
                          entry=ep,stop=l,tp=ep*1.0267,risk_pct=(ep-l)/ep*100,
                          confirm_after_minutes=j-i)
                # One notification per confirmed minute, earliest rejecting candle.
                signals.setdefault(et,item);stats['confirmed_raw']+=1
                break
        else:stats['expired']+=1
    for et,x in signals.items():
        k=index[et];status='SEM_DESFECHO';end=None;price=None
        for minutes in range(125):
            if k+minutes>=len(bars):break
            q=bars[k+minutes];t,o,h,l,c=q
            if t!=et+minutes*60 or t+60>END:break
            stop=l<=x['stop'];target=h>=x['tp']
            if stop and target:status='AMBIGUO_STOP_PRIMEIRO';end=t+60;price=x['stop'];break
            if stop:status='STOP';end=t+60;price=x['stop'];break
            if target:status='ALVO';end=t+60;price=x['tp'];break
            if minutes==124:status='TEMPO';end=t+60;price=c
        if price is None:x.update(outcome=status,exit_ts='',exit_brt='',gross_pct='',net_pct='',holding_min='')
        else:
            gross=(price/x['entry']-1)*100
            x.update(outcome=status,exit_ts=end,exit_brt=br(end),gross_pct=round(gross,5),
                     net_pct=round(gross-.20,5),holding_min=(end-et)//60)
    stats['confirmed_unique']=len(signals)
    return sorted(signals.values(),key=lambda x:x['entry_ts']),dict(stats)
def aggregate(rows):
    classes=Counter(x['outcome'] for x in rows)
    closed=[x for x in rows if x['net_pct']!='']
    return dict(confirmed=len(rows),target_hit=classes['ALVO'],stop=classes['STOP'],
                ambiguous=classes['AMBIGUO_STOP_PRIMEIRO'],timed=classes['TEMPO'],
                incomplete=classes['SEM_DESFECHO'],
                target_rate_closed_pct=round(100*classes['ALVO']/len(closed),2) if closed else None,
                sum_net_percentage_points=round(sum(x['net_pct'] for x in closed),4),
                outcomes=dict(classes))
def one_per_symbol(rows):
    selected=[];busy={}
    for x in sorted(rows,key=lambda r:(r['entry_ts'],r['symbol'])):
        if x['entry_ts']>=busy.get(x['symbol'],0):
            selected.append(x)
            busy[x['symbol']]=x['exit_ts'] or END
    return selected
def write(name,rows):
    if not rows:return
    with (OUT/name).open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def main():
    OUT.mkdir(parents=True,exist_ok=True)
    symbols=[x for x in os.environ.get('SYMBOLS','ALL').split(',') if x] if os.environ.get('SYMBOLS','ALL')!='ALL' else SYMBOLS
    result=[];coverage={}
    for number,s in enumerate(symbols,1):
        try:
            bars,diag=candles(s)
            hits,stats=scan(s,bars)
            result+=hits;coverage[s]=dict(**diag,**stats)
            print('COIN',number,'/',len(symbols),s,'confirmed',len(hits),json.dumps(coverage[s]),flush=True)
        except Exception as e:
            coverage[s]=dict(error=str(e)[:400])
            print('FAILED',number,s,str(e)[:250],flush=True)
    result.sort(key=lambda x:(x['entry_ts'],x['symbol']))
    distinct=one_per_symbol(result)
    portfolio=[];available=0
    for x in distinct:
        if x['entry_ts']>=available:
            portfolio.append(x);available=x['exit_ts'] or END
    write('all_confirmed.csv',result)
    write('targets_only.csv',[x for x in result if x['outcome']=='ALVO'])
    write('per_symbol_no_overlap.csv',distinct)
    write('global_one_position.csv',portfolio)
    expected=[x for x in result if x['symbol']=='PUMP_USDT' and x['entry_brt'].startswith('18/11/2026 22:')]
    report=dict(window_start=br(START),window_end=br(END),venue='Bybit USDT linear perpetual',interval='M1',
                symbols=symbols,coverage=coverage,
                confirmed=aggregate(result),per_symbol=aggregate(distinct),
                portfolio_one_position=aggregate(portfolio),pump_example_18nov=expected,
                warnings=['Historical causal reconstruction only; not alerts previously sent',
                          'Only confirmed signals before outcome, no filtering by later profitability',
                          'Target +2.67%, maximum 125m, fee assumption 0.20 percentage points per trade',
                          'Uses Bybit data, not MEXC execution prices',
                          'Stop first on same 1m candle ambiguity',
                          'Fixed universe may cause survivorship bias; coverage and missing data reported',
                          'One position per symbol/global portfolio are separate post-scan simulations'])
    (OUT/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print('FINAL',json.dumps({k:report[k] for k in ('confirmed','per_symbol','portfolio_one_position','pump_example_18nov')},ensure_ascii=False),flush=True)
if __name__=='__main__':main()
