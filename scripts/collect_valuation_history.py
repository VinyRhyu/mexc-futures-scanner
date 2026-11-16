"""Read public Fair M1/funding only; never reads/writes the live scanner state."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path

from mexc_scanner.mexc import MexcClient, SourceError
from mexc_scanner.models import Candle, D, jsonable, seconds


def timestamp(value):
    return int(datetime.fromisoformat(value.replace('Z', '+00:00')).timestamp())


def parse_fair(payload, start, end):
    names = ('time', 'open', 'high', 'low', 'close')
    if not all(k in payload for k in names) or len({len(payload[k]) for k in names}) != 1:
        raise ValueError('Fair arrays missing or unequal')
    result = {}
    for ts, op, hi, lo, close in zip(*(payload[k] for k in names)):
        ts = seconds(ts)
        if not start <= ts < end:
            continue
        c = Candle(ts, 60, D(op), D(hi), D(lo), D(close), D(0))
        c.validate()
        row = jsonable(c)
        if ts in result and result[ts] != row:
            raise ValueError('Conflicting Fair duplicates')
        result[ts] = row
    if set(result) != set(range(start, end, 60)):
        raise ValueError('Fair window incomplete: '+str(len(result))+'/'+str((end-start)//60))
    return [result[t] for t in sorted(result)]


def collect_symbol(client, symbol, start, end):
    # Funding starts earlier so the first decision has a known prior settlement.
    rates, seen = [], set()
    for page in range(1, 11):
        data = client._get('/api/v1/contract/funding_rate/history',
                           {'symbol': symbol, 'page_num': page, 'page_size': 1000})
        values = data['resultList']
        if not isinstance(values, list):
            raise ValueError('Funding resultList invalid')
        oldest = end
        for row in values:
            if row.get('symbol') != symbol:
                raise ValueError('Funding symbol mismatch')
            ts = seconds(row['settleTime'])
            oldest = min(oldest, ts)
            rate, cycle = D(row['fundingRate']), int(row['collectCycle'])
            if cycle <= 0:
                raise ValueError('Funding cycle invalid')
            if start-86400 <= ts <= end and ts not in seen:
                rates.append(dict(at=ts, rate=rate, cycle_hours=cycle)); seen.add(ts)
        if not values or oldest <= start-86400 or page >= int(data['totalPage']):
            break
    else:
        raise ValueError('Funding pagination did not reach requested period')
    fair = []
    for cursor in range(start, end, 1900*60):
        stop = min(end, cursor+1900*60)
        data = client._get('/api/v1/contract/kline/fair_price/'+client._symbol(symbol),
                           {'interval': 'Min1', 'start': cursor, 'end': stop-1})
        fair += parse_fair(data, cursor, stop)
    if not rates:
        raise ValueError('No funding events for period')
    return jsonable(dict(symbol=symbol, start=start, end=end, fair=fair,
                         funding=sorted(rates, key=lambda r: r['at'])))


def run(protocol, output):
    p=json.loads(Path(protocol).read_text());out=Path(output);out.mkdir(parents=True,exist_ok=True)
    start=timestamp(p['start_brt']);end=timestamp(p['end_exclusive_brt'])+14400
    client=MexcClient();specs=[];errors={}
    with ThreadPoolExecutor(max_workers=4) as pool:
        pending={pool.submit(collect_symbol,client,s,start,end):s for s in p['symbols']}
        for future in as_completed(pending):
            symbol=pending[future]
            try:
                data=future.result();raw=json.dumps(data,sort_keys=True,separators=(',',':')).encode()
                path=out/(symbol+'.json.gz');path.write_bytes(gzip.compress(raw,mtime=0))
                specs.append(dict(symbol=symbol,fair_bars=len(data['fair']),funding_events=len(data['funding']),
                                  sha256_uncompressed=hashlib.sha256(raw).hexdigest()))
                print(json.dumps(dict(symbol=symbol,status='OK',fair_bars=len(data['fair']))),flush=True)
            except (SourceError,ValueError,KeyError,TypeError,OSError) as exc:
                errors[symbol]=type(exc).__name__+': '+str(exc)
                print(json.dumps(dict(symbol=symbol,status='FAILED',error_type=type(exc).__name__)),flush=True)
    summary=dict(kind='PUBLIC_VALUATION_HISTORY_V1',collected_at_utc=datetime.now(timezone.utc).isoformat(),
        protocol_sha256=hashlib.sha256(Path(protocol).read_bytes()).hexdigest(),start=start,end=end,
        selected=len(p['symbols']),complete=len(specs),datasets=sorted(specs,key=lambda r:r['symbol']),errors=errors)
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    return summary


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--protocol',required=True);ap.add_argument('--output',required=True)
    a=ap.parse_args();s=run(a.protocol,a.output)
    print(json.dumps({k:v for k,v in s.items() if k!='datasets'},indent=2))
    raise SystemExit(0 if s['complete']==s['selected'] else 1)
