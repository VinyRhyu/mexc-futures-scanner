"""Read-only equivalence against frozen formation/confirmation records."""
from datetime import datetime
import gzip,json
from pathlib import Path
from mexc_scanner.config import Config
from mexc_scanner.models import D
from mexc_scanner.minute_breakout import process_minutes,STRATEGY
from scripts.audit_sustained_trigger import MODE,read_dataset

def run():
    source=Path('reports/early-trigger-source')
    prior=json.loads((source/'summary.json').read_text())
    cfg=Config(**prior['config']).validate()
    cohort=json.loads(gzip.decompress(Path('reports/sustained-source/all-formations.json.gz').read_bytes()))
    start=int(datetime.fromisoformat(prior['start_brt']).timestamp())
    end=int(datetime.fromisoformat(prior['end_exclusive_brt']).timestamp())
    count=0;qualified=0
    for manifest in prior['datasets']:
        symbol=manifest['symbol'];d=read_dataset(source,manifest)
        mm={c.ts:c for c in d['minute']}
        expected={}
        for row in cohort:
            if row['symbol']!=symbol or 'signal' not in row[MODE]:continue
            first=int(row['M1']['signal'])
            if mm[first-60].volume<=0 or 2*mm[first].volume<mm[first-60].volume:continue
            key=row['side'],int(datetime.fromisoformat(row['formed_at']).timestamp())
            expected[key]=row
        plans,_,_=process_minutes(symbol,d['quarter'],d['hourly'],d['minute'],[],0,
            d['minute'][-1].end+10,d['contract'].tick,cfg,start)
        actual={(p.side,p.formed_at):p for p in plans if p.formed_at<end and 'CONFIRMADA' in p.variants}
        if set(expected)!=set(actual):
            raise ValueError(f'Confirmation cohort mismatch {symbol}: missing={len(set(expected)-set(actual))}, extra={len(set(actual)-set(expected))}')
        for key,row in expected.items():
            v=actual[key].variants['CONFIRMADA'];old=row[MODE]
            if v.triggered_at!=old['signal'] or any(getattr(v,k)!=D(old[k]) for k in ('reference','entry_low','entry_high','stop','target')):
                raise ValueError('Frozen levels differ: '+symbol)
            count+=1
            qualified+='entered_at' in old
        print(json.dumps({'symbol':symbol,'matching_confirmations':len(actual)}),flush=True)
    if qualified!=28:raise ValueError('The28financially qualified entries were not reproduced')
    print(json.dumps({'verification':'PASS','matching_confirmations':count,'matching_qualified_entries':qualified}),flush=True)

if __name__=='__main__':run()
