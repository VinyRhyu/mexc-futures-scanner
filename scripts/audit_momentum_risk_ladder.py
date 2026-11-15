"""Frozen exploratory stop correction followed by portfolio risk increases. Research only."""
import argparse
import gzip
import json
from pathlib import Path

from mexc_scanner.models import Candle,D,jsonable
from scripts.audit_relative_momentum_daily import load_source
from scripts.audit_momentum_week10x import simulate_week


def explain(scenario):
    trades=scenario['trades']
    wins=[D(t['net_pnl']) for t in trades if D(t['net_pnl'])>0]
    losses=[D(t['net_pnl']) for t in trades if D(t['net_pnl'])<0]
    return jsonable(dict(total_positive_pnl=sum(wins,D(0)),total_negative_pnl=sum(losses,D(0)),
        mean_positive_pnl=sum(wins,D(0))/len(wins) if wins else None,
        mean_negative_pnl=sum(losses,D(0))/len(losses) if losses else None,
        best_trade=max((D(t['net_pnl']) for t in trades),default=D(0)),
        worst_trade=min((D(t['net_pnl']) for t in trades),default=D(0)),
        profitable_cycles=sum(D(d['net_pnl'])>0 for d in scenario['days']),
        adjusted_stops=sum(t.get('stop_adjusted',False) for t in trades),
        mean_actual_planned_risk_pct=sum((D(d['planned_stop_risk'])/D(d['start_equity'])*100
             for d in scenario['days']),D(0))/len(scenario['days']),
        maximum_cycle_loss=min(D(d['net_pnl']) for d in scenario['days'])))


def run(source,protocol,baseline):
    p=json.loads(Path(protocol).read_text())
    market,excluded=load_source(source,p)
    for symbol,m in market.items():
        raw=json.load(gzip.open(Path(source)/(symbol+'.json.gz'),'rt'))
        m['fair']={b['ts']:Candle.from_dict(b) for b in raw['fair']}
        assert set(m['fair'])==set(m['hourly'])
    results={}
    for setting in p['scenarios']:
        config=dict(p,portfolio_risk_fraction=setting['risk_fraction'],
                    liquidation_stop_buffer=setting['stop_buffer'])
        result=simulate_week(market,config,10)
        result=jsonable(result)
        result['explanation']=explain(result)
        results[setting['name']]=result
    old=json.loads(Path(baseline).read_text())['primary10x']
    replay=results['original_risk2']
    for key in ('summary','days','trades','hourly_equity','skips','causal_checks'):
        assert replay[key]==old[key],f'Baseline replay changed: {key}'
    for name,s in results.items():
        if name!='original_risk2':
            assert s['summary']['positions_without_1_5_liquidation_buffer']==0
            assert s['summary']['positions_with_stop_beyond_liquidation']==0
    return dict(protocol=p,complete_symbols=sorted(market),excluded=excluded,
                baseline_replay_identical=True,scenarios=results,production_changed=False)


if __name__=='__main__':
    ap=argparse.ArgumentParser()
    for key in ('source','protocol','baseline','output'):ap.add_argument('--'+key,required=True)
    args=ap.parse_args()
    results=run(args.source,args.protocol,args.baseline)
    Path(args.output).write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({n:dict(summary=s['summary'],explanation=s['explanation'],skips=s['skips'])
                      for n,s in results['scenarios'].items()},indent=2))
