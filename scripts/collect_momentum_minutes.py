"""Resolve every frozen ambiguous hourly liquidation with public M1 data."""
import argparse,gzip,hashlib,json
from pathlib import Path

from mexc_scanner.mexc import MexcClient
from mexc_scanner.models import Candle,D,jsonable,seconds


def minute_window(payload,start,end,fair=False):
    names=['time','open','high','low','close']+([] if fair else ['vol'])
    if any(k not in payload for k in names) or len({len(payload[k]) for k in names})!=1:
        raise ValueError('Unequal M1 arrays')
    bars={}
    for i,t in enumerate(payload['time']):
        at=seconds(t)
        if not start<=at<end:continue
        c=Candle(at,60,D(payload['open'][i]),D(payload['high'][i]),D(payload['low'][i]),
            D(payload['close'][i]),D(0) if fair else D(payload['vol'][i]))
        c.validate()
        if at in bars and bars[at]!=c:raise ValueError('Conflicting M1 duplicate')
        bars[at]=c
    if set(bars)!=set(range(start,end,60)):raise ValueError('Incomplete M1 hour')
    return [bars[t] for t in sorted(bars)]


def verify_hour(minutes,expected):
    actual=(minutes[0].open,max(c.high for c in minutes),min(c.low for c in minutes),minutes[-1].close)
    target=tuple(D(expected[k]) for k in ('open','high','low','close'))
    if actual!=target:raise ValueError('M1 OHLC does not reproduce the frozen H1 source')


def run(protocol,output,client=None):
    p=json.loads(Path(protocol).read_text());client=client or MexcClient()
    out=Path(output);out.mkdir(parents=True,exist_ok=True)
    summary=dict(protocol_sha256=hashlib.sha256(Path(protocol).read_bytes()).hexdigest(),
        selected=len(p['cases']),complete=0,datasets=[],errors={})
    for case in p['cases']:
        symbol,start,end=case['symbol'],case['start'],case['end'];key=f'{symbol}-{start}'
        try:
            params=dict(interval='Min1',start=start,end=end-1)
            last=minute_window(client._get('/api/v1/contract/kline/'+client._symbol(symbol),params),start,end)
            fair=minute_window(client._get('/api/v1/contract/kline/fair_price/'+client._symbol(symbol),params),start,end,True)
            verify_hour(last,case['last_hour']);verify_hour(fair,case['fair_hour'])
            raw=json.dumps(jsonable(dict(symbol=symbol,start=start,end=end,last=last,fair=fair)),sort_keys=True,separators=(',',':')).encode()
            (out/(key+'.json.gz')).write_bytes(gzip.compress(raw,mtime=0))
            summary['datasets'].append(dict(key=key,symbol=symbol,start=start,end=end,
                sha256_uncompressed=hashlib.sha256(raw).hexdigest(),ohlc_matches=True))
            summary['complete']+=1;print(json.dumps(dict(case=key,status='OK')),flush=True)
        except Exception as exc:
            summary['errors'][key]=type(exc).__name__+': '+str(exc)[:180]
            print(json.dumps(dict(case=key,error=summary['errors'][key])),flush=True)
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    if summary['errors']:raise ValueError('Incomplete minute resolution; preserve coarse uncertainty')
    return summary


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--protocol',required=True);ap.add_argument('--output',required=True)
    a=ap.parse_args();run(a.protocol,a.output)
