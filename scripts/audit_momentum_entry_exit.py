"""Entry/exit attribution and one predeclared six-hour exit test; research only."""
import argparse,gzip,json
from pathlib import Path
from statistics import median

from mexc_scanner.models import Candle,D,jsonable
from scripts.audit_relative_momentum_daily import HOUR,load_source,hour_funding,close_position
from scripts.audit_momentum_week10x import simulate_week
from scripts.audit_momentum_risk_ladder import explain


NUMERIC=('entry_mid','entry_fill','quantity','contracts','entry_fee','funding_cash','stop',
         'planned_risk','initial_notional','isolated_margin','liquidation_price','net_pnl')


def inspect_trade(raw,m):
    t={k:D(v) if k in NUMERIC and v is not None else v for k,v in raw.items()}
    sign=t['sign'];entry=t['entry_fill'];start=t['opened_at'];end=t['closed_at']
    stop_exit=t['reason'] not in ('TIME','STOP_GAP')
    all_bars=[m['hourly'][ts] for ts in range(start, end if end>start else start+HOUR,HOUR)]
    safe=[b for b in all_bars if b.end<=end and not(stop_exit and b.end==end)]
    # STOP_GAP at the hour open has no part of that hour in the held path.
    if t['reason']=='STOP_GAP':safe=[b for b in safe if b.end<=end]
    best_price=max([entry]+[b.high for b in safe]) if sign==1 else min([entry]+[b.low for b in safe])
    worst_price=min([entry,t['exit_mid'] and D(t['exit_mid']) or entry]+[b.low for b in safe]) if sign==1 else max([entry,t['exit_mid'] and D(t['exit_mid']) or entry]+[b.high for b in safe])
    upper_bars=[b for b in all_bars if b.ts<end]
    upper=max([entry]+[b.high for b in upper_bars]) if sign==1 else min([entry]+[b.low for b in upper_bars])
    best_net=D(0);best_at=None;funding=D(0);path=[]
    for b in safe:
        f,_=hour_funding(t,m['fair'][b.ts],m['funding'],False);funding+=f
        pos=dict(t,funding_cash=funding)
        hypothetical,_=close_position(pos,b.close,b.end,'H1_DIAGNOSTIC',m['contract'])
        net=hypothetical['net_pnl'];path.append(dict(ts=b.end,net_pnl=net))
        if net>best_net:best_net,best_at=net,b.end
    previous=m['hourly'][start-6*HOUR].open
    early=m['hourly'][start+5*HOUR].close
    return dict(symbol=t['symbol'],sign=sign,opened_at=start,closed_at=end,reason=t['reason'],
        net_pnl=t['net_pnl'],initial_notional=t['initial_notional'],margin=t['isolated_margin'],
        planned_risk=t['planned_risk'],mfe_safe_price_pct=sign*(best_price/entry-1)*100,
        mfe_exit_hour_upper_price_pct=sign*(upper/entry-1)*100,
        mae_price_pct=sign*(worst_price/entry-1)*100,
        best_completed_h1_net=best_net,best_completed_h1_at=best_at,
        best_completed_h1_R=best_net/t['planned_risk'],
        best_completed_h1_margin_roi_pct=best_net/t['isolated_margin']*100,
        giveback_from_best_completed_h1=max(D(0),best_net-t['net_pnl']),
        pre_entry6h_signed_return_pct=sign*(t['entry_mid']/previous-1)*100,
        post_entry6h_signed_return_pct=sign*(early/t['entry_mid']-1)*100,
        safe_completed_h1_count=len(safe),close_path=path)


def summarize_inspections(rows):
    losses=[r for r in rows if r['net_pnl']<0]
    wins=[r for r in rows if r['net_pnl']>0]
    return dict(trades=len(rows),wins=len(wins),losses=len(losses),
        losses_with_positive_h1_close=sum(r['best_completed_h1_net']>0 for r in losses),
        losses_without_positive_h1_close=sum(r['best_completed_h1_net']==0 for r in losses),
        losses_pre_entry6h_favorable=sum(r['pre_entry6h_signed_return_pct']>0 for r in losses),
        losses_post_entry6h_adverse=sum(r['post_entry6h_signed_return_pct']<0 for r in losses),
        losses_reached_margin_roi={str(threshold):sum(r['best_completed_h1_margin_roi_pct']>=threshold for r in losses)
                                  for threshold in (10,20,30)},
        losses_reached_R={str(threshold):sum(r['best_completed_h1_R']>=D(threshold) for r in losses)
                          for threshold in ('.25','.5','1')},
        losses_previously_positive_net=sum((r['net_pnl'] for r in losses if r['best_completed_h1_net']>0),D(0)),
        sum_best_completed_h1_net=sum((r['best_completed_h1_net'] for r in rows),D(0)),
        sum_giveback_from_best_completed_h1=sum((r['giveback_from_best_completed_h1'] for r in rows),D(0)),
        median_mfe_safe_price_pct=median(r['mfe_safe_price_pct'] for r in rows),
        median_mae_price_pct=median(r['mae_price_pct'] for r in rows),
        median_pre_entry6h_signed_return_pct=median(r['pre_entry6h_signed_return_pct'] for r in rows),
        median_post_entry6h_signed_return_pct=median(r['post_entry6h_signed_return_pct'] for r in rows),
        median_best_h1_hours=median(D(r['best_completed_h1_at']-r['opened_at'])/HOUR for r in rows if r['best_completed_h1_at']),
        best_completed_h1_within6h=sum(r['best_completed_h1_at'] is not None and r['best_completed_h1_at']-r['opened_at']<=6*HOUR for r in rows),
        wins_with_major_giveback=sum(r['best_completed_h1_net']>0 and r['net_pnl']<=r['best_completed_h1_net']/2 for r in wins))


def run(source,protocol,baseline):
    p=json.loads(Path(protocol).read_text());market,excluded=load_source(source,p)
    for symbol,m in market.items():
        raw=json.load(gzip.open(Path(source)/(symbol+'.json.gz'),'rt'))
        m['fair']={b['ts']:Candle.from_dict(b) for b in raw['fair']}
        assert set(m['fair'])==set(m['hourly'])
    control=jsonable(simulate_week(market,dict(p,holding_hours=p['holding_hours_control']),10))
    old=json.loads(Path(baseline).read_text())['scenarios']['capped_risk2']
    for key in ('summary','days','trades','hourly_equity','skips','causal_checks'):
        assert control[key]==old[key],f'24h baseline changed: {key}'
    variant=jsonable(simulate_week(market,dict(p,holding_hours=p['holding_hours_test']),10))
    rows=[inspect_trade(t,market[t['symbol']]) for t in control['trades']]
    a={(t['opened_at'],t['symbol']):t for t in control['trades']}
    b={(t['opened_at'],t['symbol']):t for t in variant['trades']}
    common=sorted(set(a)&set(b))
    paired=[dict(symbol=k[1],opened_at=k[0],quantity24=a[k]['quantity'],quantity6=b[k]['quantity'],
                 net24=a[k]['net_pnl'],net6=b[k]['net_pnl']) for k in common]
    return jsonable(dict(protocol=p,complete_symbols=sorted(market),excluded=excluded,
        control24h=control,variant6h=variant,
        control_explanation=explain(control),variant_explanation=explain(variant),
        control_replay_identical=True,diagnostic_summary=summarize_inspections(rows),
        diagnostic_trades=rows,pairing=dict(common_entries=len(common),
        only24h=len(set(a)-set(b)),only6h=len(set(b)-set(a)),
        equal_quantity_entries=sum(a[k]['quantity']==b[k]['quantity'] for k in common),rows=paired),
        production_changed=False))


if __name__=='__main__':
    ap=argparse.ArgumentParser()
    for k in ('source','protocol','baseline','output'):ap.add_argument('--'+k,required=True)
    a=ap.parse_args();r=run(a.source,a.protocol,a.baseline)
    Path(a.output).write_text(json.dumps(r,indent=2)+'\n')
    print(json.dumps({k:r[k] for k in ('diagnostic_summary','control_explanation','variant_explanation')},indent=2))
    print(json.dumps({k:r[k]['summary'] for k in ('control24h','variant6h')},indent=2))
    print(json.dumps({k:v for k,v in r['pairing'].items() if k!='rows'}))
