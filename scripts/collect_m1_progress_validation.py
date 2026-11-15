"""Public historical data only; no trading, state or Telegram dependencies."""
import json
from pathlib import Path
from datetime import datetime,timezone
from concurrent.futures import ThreadPoolExecutor,as_completed
from mexc_scanner.config import load_config
from mexc_scanner.mexc import MexcClient
from mexc_scanner.market import parse_candles
from mexc_scanner.models import Contract,jsonable
from scripts.audit_early_trigger import collect_minutes,check_ohlc,write_gzip


def run():
    p=json.loads(Path('config/audit-m1-short-progress-new-week-2026-11-15.json').read_text())
    start=int(datetime.fromisoformat(p['start_brt']).timestamp())
    end=int(datetime.fromisoformat(p['end_exclusive_brt']).timestamp());observed=end+18000
    client=MexcClient();now=client.server_time();assert now>=observed+10
    cfg=load_config(p['config_file']);catalog={c['symbol']:c for c in client.contracts()}
    out=Path('reports/m1-progress-new-week');out.mkdir(parents=True,exist_ok=True)
    qn=480+(observed-start)//900;hn=240+(observed-start)//3600
    result=dict(kind='M1_PROGRESS_NEW_WEEK_SOURCE',start_brt=p['start_brt'],
        end_exclusive_brt=p['end_exclusive_brt'],collected_at=datetime.fromtimestamp(now,timezone.utc).isoformat(),
        config=jsonable(cfg),selected_symbols=len(p['symbols']),analyzed_symbols=0,datasets=[],errors={})
    def one(symbol):
        raw=catalog[symbol];contract=Contract.from_api(raw)
        q=parse_candles(client.candles(symbol,'Min15',qn,observed+10),900,observed+10,qn)
        h=parse_candles(client.candles(symbol,'Min60',hn,observed+10),3600,observed+10,hn)
        m=collect_minutes(client,symbol,start-1200,observed)
        check_ohlc(q,{c.ts:c for c in m},start,observed)
        digest=write_gzip(out/'raw'/f'{symbol}.json.gz',
            dict(symbol=symbol,contract=raw,quarter=q,hourly=h,minute=m))
        return dict(symbol=symbol,quarter_bars=len(q),hourly_bars=len(h),minute_bars=len(m),
                    sha256_uncompressed=digest,ohlc_matches=True)
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures={pool.submit(one,s):s for s in p['symbols']}
        for f in as_completed(futures):
            symbol=futures[f]
            try:
                d=f.result();result['datasets'].append(d);print(json.dumps(d),flush=True)
            except Exception as e:
                result['errors'][symbol]=type(e).__name__+': '+str(e)[:180]
                print(json.dumps(dict(symbol=symbol,error=result['errors'][symbol])),flush=True)
    result['datasets'].sort(key=lambda d:d['symbol']);result['analyzed_symbols']=len(result['datasets'])
    (out/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
    assert not result['errors'] and result['analyzed_symbols']==31,result['errors']


if __name__=='__main__':run()
