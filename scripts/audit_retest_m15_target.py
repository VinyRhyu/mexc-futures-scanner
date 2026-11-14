"""Change only the target of a frozen structure/retest cohort. Read-only audit."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from pathlib import Path
import json

from mexc_scanner.config import load_config
from mexc_scanner.models import Candle, Contract, D, ceil_step, floor_step, jsonable
from scripts.audit_structure_retest_day import evaluate_setup, generate, summarize


def quarters(minute):
    groups = defaultdict(list)
    for c in minute:
        groups[c.ts//900*900].append(c)
    bars = []
    for ts, group in sorted(groups.items()):
        group = sorted(group, key=lambda c:c.ts)
        if len(group) != 15:
            continue
        assert [c.ts for c in group] == list(range(ts,ts+900,60))
        bars.append(Candle(ts,900,group[0].open,max(c.high for c in group),
                           min(c.low for c in group),group[-1].close,
                           sum((c.volume for c in group),D(0))))
    return bars


def choose_target(bars, side, reference, signal, tick):
    """Nearest still-active M15 pivot, frozen at the original reaction time."""
    known = [b for b in bars if b.end+10 <= signal]
    sign = 1 if side=='LONG' else -1
    candidates = []
    for j in range(2,len(known)-2):
        p = known[j]
        if signal-p.ts > 21600:
            continue
        neighbours = [known[k] for k in (j-2,j-1,j+1,j+2)]
        level = p.high if sign==1 else p.low
        pivot = all(level > c.high for c in neighbours) if sign==1 else all(level < c.low for c in neighbours)
        if not pivot or sign*(level-reference) <= tick:
            continue
        if any(sign*(c.close-level)>0 for c in known[j+3:]):
            continue
        target = floor_step(level-tick,tick) if sign==1 else ceil_step(level+tick,tick)
        if sign*(target-reference) <= 0:
            continue
        candidates.append(dict(target=target,level=level,pivot_at=p.ts,
                               known_at=known[j+2].end+10))
    if not candidates:
        return None
    return min(candidates,key=lambda c:(sign*(c['level']-reference),-c['pivot_at']))


def mark_open(row, minute, contract, config, cutoff):
    """Report a hypothetical marked exit separately; never label it TP or SL."""
    if row['status'] != 'VIAVEL_SIMULADO' or row['outcome'] != 'ABERTO':
        return row
    horizon = min(cutoff,row['confirmed_at']+14400)
    bars = [b for b in minute if row['entry_at']<=b.ts and b.end<=horizon]
    if not bars:
        return row
    sign = 1 if row['side']=='LONG' else -1
    entry = D(row['entry_open'])*(1+sign*D('.0001'))
    stop,price = D(row['stop']),bars[-1].close
    fee,slip,tick = D(config.taker_fee),D(config.slippage_rate),contract.tick
    entry_cost = max(2*tick,slip*entry)
    risk = sign*(entry-stop)+entry_cost+max(2*tick,slip*stop)+fee*(entry+stop)
    net = sign*(price-entry)-entry_cost-max(2*tick,slip*price)-fee*(entry+price)
    return dict(row,marked_r=str(net/risk),marked_price=str(price),marked_at=bars[-1].end)


def summary(rows):
    result = summarize(rows)
    accepted = [r for r in rows if r['status']=='VIAVEL_SIMULADO']
    result['without_target'] = sum(r['status']=='SEM_ALVO_M15' for r in rows)
    result['net_r_with_hypothetical_marks'] = str(sum((D(r.get('net_r',r.get('marked_r','0')))
                                                     for r in accepted),D(0)))
    return result


def run(original_path,source_path,contracts_path,config_path):
    original = json.loads(Path(original_path).read_text())
    assert len(original['setups']) == 264
    cfg = load_config(config_path)
    catalog = {r['symbol']:Contract.from_api(r) for r in json.loads(Path(contracts_path).read_text())['contracts']}
    protocol = original['protocol'];cutoff=protocol['price_cutoff']
    from datetime import datetime
    first = int(datetime.fromisoformat(protocol['day_start_brt']).timestamp())
    market,changed,records,checks = {},[],[],0
    for symbol in original['symbols']:
        data=json.loads((Path(source_path)/(symbol+'.json')).read_text())
        assert data['price_cutoff']==cutoff
        minute=[Candle.from_dict(c) for c in data['candles']]
        q=quarters(minute);contract=catalog[symbol];market[symbol]=minute
        rebuilt,_=generate(symbol,minute,contract.tick,first,protocol['signal_cutoff'])
        frozen=[s for s in original['setups'] if s['symbol']==symbol]
        assert jsonable(rebuilt)==frozen,('original candidate changed',symbol)
        for row in frozen:
            setup=dict(row)
            for k in ('atr','level','reference','stop','target','entry_low','entry_high'):
                setup[k]=D(setup[k])
            selected=choose_target(q,setup['side'],setup['reference'],setup['signal'],contract.tick)
            # Repeating with a historical prefix must yield exactly the same target.
            prefix=[b for b in q if b.end+10<=setup['signal']]
            assert selected==choose_target(prefix,setup['side'],setup['reference'],setup['signal'],contract.tick)
            checks+=1
            old_target=setup['target']
            if selected:
                setup['target']=selected['target']
            changed.append(jsonable(dict(setup,original_target=old_target,m15_target=selected)))
            for delay in (0,60):
                if selected is None:
                    r=dict(plan_id=setup['id'],symbol=symbol,side=setup['side'],confirmed_at=setup['signal'],
                           delay=delay,entry_at=setup['signal']+delay,status='SEM_ALVO_M15',outcome='SEM_ENTRADA')
                else:
                    r=evaluate_setup(setup,minute,contract,cfg,delay,cutoff)
                    r=mark_open(r,minute,contract,cfg,cutoff)
                    r.update(target_origin='M15_CONFIRMED_ACTIVE_PIVOT',m15_target=jsonable(selected),
                             original_target=str(old_target))
                records.append(r)
    comparisons={}
    for name,end in (('all_day',protocol['signal_cutoff']),('mature_4h',cutoff-14400)):
        comparisons[name]={}
        for delay in (0,60):
            before=[r for r in original['records'] if r['delay']==delay and r['confirmed_at']<=end]
            after=[r for r in records if r['delay']==delay and r['confirmed_at']<=end]
            assert len(before)==len(after)
            comparisons[name][str(delay)]=dict(original_local_target=summary(before),m15_target=summary(after))
    original_by_key={(r['plan_id'],r['delay']):r for r in original['records']}
    paired={}
    for delay in (0,60):
        transitions=Counter()
        for row in records:
            if row['delay']!=delay:continue
            old=original_by_key[row['plan_id'],delay]
            transitions[(old['status'],row['status'])]+=1
        paired[str(delay)]={' -> '.join(k):n for k,n in sorted(transitions.items())}
    distances=[(1 if s['side']=='LONG' else -1)*(D(s['target'])-D(s['reference']))/D(s['reference'])*100
               for s in changed if s['m15_target']]
    from statistics import median
    return dict(experiment='M5_RETEST_WITH_NEAREST_ACTIVE_M15_TARGET_V1',
                only_changed_variable='target selection; candidate timestamps, entry prices and stops fixed',
                price_cutoff=cutoff,signal_cutoff=protocol['signal_cutoff'],symbols=original['symbols'],
                target_causality_checks=checks,candidate_count=len(changed),
                available_targets=sum(s['m15_target'] is not None for s in changed),
                median_target_distance_percent=str(median(distances)) if distances else None,
                comparisons=comparisons,eligibility_transitions=paired,setups=changed,records=records,
                limitations=['Single already-inspected day, exploratory and not out-of-sample.',
                             'Funding zero, synthetic spread/depth, same contract parameters and cost model.',
                             'Zero-delay entry is idealized; overlapping independent plans are not a wallet.',
                             'Mature cohort has four-hour observation potential; unresolved plans remain open.',
                             'Marked R assumes an exit at the observation cutoff and is not a realized trade.',
                             'Nearest active M15 pivot only; no searching farther to satisfy RR. Production unchanged.'])


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    for key in ('original','source','contracts','config','output'):
        parser.add_argument('--'+key,required=True)
    args=parser.parse_args()
    result=run(args.original,args.source,args.contracts,args.config)
    Path(args.output).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('setups','records')},ensure_ascii=False,indent=2))
