"""GET-only historical Last/Fair/funding collector, no state or notifications."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path

from mexc_scanner.mexc import MexcClient
from mexc_scanner.models import Candle, Contract, D, jsonable, seconds
from scripts.audit_multihour import HOUR, stamp


def parse_window(payload, start, end, *, fair=False):
    names = ['time','open','high','low','close'] + ([] if fair else ['vol'])
    if any(name not in payload for name in names) or len({len(payload[n]) for n in names}) != 1:
        raise ValueError('Incomplete or unequal public candle arrays')
    found = {}
    for i, value in enumerate(payload['time']):
        at = seconds(value)
        if not start <= at < end:
            continue
        bar = Candle(at,HOUR,D(payload['open'][i]),D(payload['high'][i]),
            D(payload['low'][i]),D(payload['close'][i]),D(0) if fair else D(payload['vol'][i]))
        bar.validate()
        if at in found and found[at] != bar:
            raise ValueError('Conflicting public candle duplicate')
        found[at] = bar
    if set(found) != set(range(start,end,HOUR)):
        raise ValueError('Public hourly history incomplete')
    return [found[t] for t in sorted(found)]


def collect_symbol(client,symbol,contract,start,end):
    Contract.from_api(contract)
    result = dict(symbol=symbol,contract=contract,hourly=[],fair=[],funding=[])
    for cursor in range(start,end,1900*HOUR):
        stop = min(end,cursor+1900*HOUR)
        params = dict(interval='Min60',start=cursor,end=stop-1)
        for name,prefix in [('hourly','/api/v1/contract/kline/'),('fair','/api/v1/contract/kline/fair_price/')]:
            payload = client._get(prefix+client._symbol(symbol),params)
            result[name].extend(parse_window(payload,cursor,stop,fair=name=='fair'))
    records = {}; reached = False
    for page in range(1,21):
        data = client._get('/api/v1/contract/funding_rate/history',
            dict(symbol=symbol,page_num=page,page_size=1000))
        rows = data['resultList']
        if not isinstance(rows,list):
            raise ValueError('Invalid public funding records')
        for row in rows:
            if row['symbol'] != symbol:
                raise ValueError('Funding symbol mismatch')
            at = seconds(row['settleTime']); cycle = int(row['collectCycle'])
            if not 0 < cycle <= 8:
                raise ValueError('Unsupported funding cycle')
            record = dict(ts=at,rate=D(row['fundingRate']),cycle=cycle)
            if at in records and record != records[at]:
                raise ValueError('Conflicting funding duplicate')
            records[at] = record
        if rows and min(seconds(r['settleTime']) for r in rows) <= start-8*HOUR:
            reached = True; break
        if not rows or page >= int(data['totalPage']):
            break
    if not reached:
        raise ValueError('Funding pagination did not cover the requested start')
    rates = [r for at,r in sorted(records.items()) if start-8*HOUR <= at <= end+8*HOUR]
    if not rates or rates[0]['ts'] > start or rates[-1]['ts'] < end:
        raise ValueError('Funding endpoints incomplete')
    if any(not 0 < b['ts']-a['ts'] <= 8*HOUR for a,b in zip(rates,rates[1:])):
        raise ValueError('Funding history contains a gap')
    result['funding'] = rates
    return jsonable(result)


def run(protocol,output,client=None):
    path = Path(protocol); p = json.loads(path.read_text())
    start,end = stamp(p['collect_start_utc']),stamp(p['collect_end_utc'])
    client = client or MexcClient()
    out = Path(output); out.mkdir(parents=True,exist_ok=True)
    try:
        server = client.server_time()
        catalog = {c['symbol']:c for c in client.contracts()}
    except Exception as exc:
        (out/'collection_error.json').write_text(json.dumps(dict(
            status='FAILED_BEFORE_COLLECTION',error_type=type(exc).__name__,
            reason=str(exc)[:180],protocol_sha256=hashlib.sha256(path.read_bytes()).hexdigest()),indent=2)+'\n')
        raise
    if server < end+10:
        raise ValueError('Collection end includes an unclosed hourly candle')
    manifest = dict(captured_at=server,start=start,end=end,selected=p['symbols'],ok={},errors={},
        protocol_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        contract_rules='Current public snapshot, not historical point-in-time rules')
    def one(symbol):
        row = collect_symbol(client,symbol,catalog[symbol],start,end)
        raw = json.dumps(row,sort_keys=True,separators=(',',':')).encode()
        (out/(symbol+'.json.gz')).write_bytes(gzip.compress(raw,mtime=0))
        return dict(symbol=symbol,hours=len(row['hourly']),fair_hours=len(row['fair']),
            funding=len(row['funding']),sha256_uncompressed=hashlib.sha256(raw).hexdigest())
    with ThreadPoolExecutor(max_workers=4) as pool:
        pending = {pool.submit(one,s):s for s in p['symbols']}
        for future in as_completed(pending):
            symbol = pending[future]
            try:
                spec = future.result(); manifest['ok'][symbol] = spec
                print(json.dumps(spec),flush=True)
            except Exception as exc:
                manifest['errors'][symbol] = type(exc).__name__+': '+str(exc)[:180]
                print(json.dumps(dict(symbol=symbol,error=manifest['errors'][symbol])),flush=True)
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    if manifest['errors']:
        raise ValueError('Incomplete collection; do not evaluate only the successful survivors')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--protocol',required=True)
    parser.add_argument('--output',required=True); args = parser.parse_args()
    run(args.protocol,args.output)
