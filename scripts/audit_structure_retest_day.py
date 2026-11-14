"""Frozen single-day M5 structure/retest experiment. No orders or notifications."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime
import json
from pathlib import Path
from statistics import median

from mexc_scanner.config import load_config
from mexc_scanner.market import atr
from mexc_scanner.models import Candle, Contract, D, Plan, Variant, ceil_step, floor_step, jsonable, stable_id
from scripts.audit_pullback import paper_quote, close_outcome


def aggregate_five(minute):
    groups = defaultdict(list)
    for c in minute:
        groups[(c.ts//300)*300].append(c)
    result = []
    for ts, group in sorted(groups.items()):
        group = sorted(group, key=lambda c: c.ts)
        if len(group) != 5:
            continue
        if [c.ts for c in group] != list(range(ts, ts+300, 60)):
            raise ValueError('M1 gap in M5 aggregation')
        result.append(Candle(ts, 300, group[0].open, max(c.high for c in group),
                             min(c.low for c in group), group[-1].close,
                             sum((c.volume for c in group), D(0))))
    return result


def advance_retest(wait, c, tick):
    """An entry can only be prepared by a candle AFTER the breakout."""
    if c.ts < wait['break_at']:
        return 'WAIT', None
    if c.end > wait['break_at']+1800:
        return 'EXPIRED', None
    sign, level, a = wait['sign'], wait['level'], wait['atr']
    lower, upper = level-D('.20')*a, level+D('.20')*a
    if sign*(c.close-level) < -D('.20')*a:
        return 'CANCELLED', None
    # Target excludes the reaction candle; it is already known BEFORE reaction.
    target = wait['impulse_high'] if sign == 1 else wait['impulse_low']
    wait['wait_low'] = c.low if wait['wait_low'] is None else min(wait['wait_low'], c.low)
    wait['wait_high'] = c.high if wait['wait_high'] is None else max(wait['wait_high'], c.high)
    touch = c.low <= upper and c.high >= lower
    if touch and sign*(c.close-level) > 0:
        stop = (floor_step(wait['wait_low']-D('.10')*a, tick) if sign == 1 else
                ceil_step(wait['wait_high']+D('.10')*a, tick))
        target = floor_step(target, tick) if sign == 1 else ceil_step(target, tick)
        return 'REACTION', dict(signal=c.end, reference=c.close, stop=stop, target=target,
                                entry_low=ceil_step(c.close-D('.25')*a, tick),
                                entry_high=floor_step(c.close+D('.25')*a, tick))
    wait['impulse_high'] = max(wait['impulse_high'], c.high)
    wait['impulse_low'] = min(wait['impulse_low'], c.low)
    return 'WAIT', None


def generate(symbol, minute, tick, day_start, signal_cutoff):
    bars = aggregate_five(minute)
    values = atr(bars, 14)
    latest, active, used = {}, {}, set()
    setups, stats = [], Counter()
    for i, c in enumerate(bars):
        if c.end > signal_cutoff:
            break
        # At the start of c, pivot j already has two CLOSED right neighbours.
        j = i-3
        if j >= 2:
            neighbours = [bars[k] for k in (j-2, j-1, j+1, j+2)]
            pivot = bars[j]
            for side, value, confirmed in (
                    ('LONG', pivot.high, all(pivot.high > b.high for b in neighbours)),
                    ('SHORT', pivot.low, all(pivot.low < b.low for b in neighbours))):
                if confirmed:
                    latest[side] = dict(ts=pivot.ts, known_at=bars[j+2].end, value=value)
        for side in list(active):
            wait = active[side]
            stage, reaction = advance_retest(wait, c, tick)
            if stage != 'WAIT':
                del active[side]
                if c.end >= day_start:
                    stats['retest_'+stage] += 1
            if reaction and day_start <= reaction['signal'] <= signal_cutoff:
                pid = stable_id('STRUCTURE_RETEST_M5_V1', symbol, side,
                                wait['pivot_ts'], wait['break_at'], reaction['signal'])
                setups.append(dict(id=pid, symbol=symbol, side=side, atr=wait['atr'],
                                   level=wait['level'], break_at=wait['break_at'],
                                   pivot_ts=wait['pivot_ts'], pivot_known_at=wait['pivot_known_at'],
                                   **reaction))
        if i == 0 or values[i-1] is None:
            continue
        a = values[i-1]
        for side, sign in (('LONG', 1), ('SHORT', -1)):
            if side in active or side not in latest:
                continue
            pivot = latest[side]
            if c.ts-pivot['known_at'] > 7200:
                continue
            key = side, pivot['ts']
            threshold = pivot['value']+sign*D('.10')*a
            if key in used or not (sign*(bars[i-1].close-threshold) <= 0 < sign*(c.close-threshold)):
                continue
            used.add(key)
            active[side] = dict(sign=sign, level=pivot['value'], atr=a, break_at=c.end,
                                pivot_ts=pivot['ts'], pivot_known_at=pivot['known_at'],
                                wait_low=None, wait_high=None,
                                impulse_high=c.high, impulse_low=c.low)
            if c.end >= day_start:
                stats['breakouts'] += 1
    return setups, dict(stats)


def evaluate_setup(setup, minute, contract, config, delay, price_cutoff):
    signal = setup['signal']
    p = Plan(setup['id'], setup['symbol'], 'STRUCTURE_RETEST_M5_V1', setup['side'],
             setup['break_at'], signal, signal+120, setup['atr'], setup['level'],
             setup['level']-D('.20')*setup['atr'], setup['level']+D('.20')*setup['atr'],
             setup['stop'], setup['id'], status='ATIVO')
    v = Variant('CONFIRMADA', signal, setup['reference'], setup['entry_low'], setup['entry_high'],
                setup['stop'], setup['target'], 'KNOWN_PRE_REACTION_IMPULSE')
    p.variants[v.kind] = v
    r = dict(plan_id=p.id, symbol=p.symbol, side=p.side, confirmed_at=signal,
             delay=delay, entry_at=signal+delay, stop=v.stop, target=v.target,
             reference=v.reference, break_at=setup['break_at'], level=p.level)
    mm = {b.ts: b for b in minute}
    prior = [mm[t] for t in range(signal, signal+delay, 60) if t in mm]
    for b in prior:
        stop = b.low <= v.stop if p.side == 'LONG' else b.high >= v.stop
        target = b.high >= v.target if p.side == 'LONG' else b.low <= v.target
        if stop or target:
            return jsonable(dict(r, status='CANCELLED_BEFORE_ENTRY', outcome='SEM_ENTRADA'))
    entry_bar = mm.get(signal+delay)
    if entry_bar is None:
        return jsonable(dict(r, status='SEM_DADOS', outcome='SEM_ENTRADA'))
    f = paper_quote(p, v, contract, entry_bar.open, entry_bar.ts+1, config)
    r.update(entry_open=entry_bar.open, financial_status=f['status'])
    if f['status'] != 'VIAVEL_SIMULADO':
        return jsonable(dict(r, status='BLOQUEADA', outcome='SEM_ENTRADA', reasons=f['reasons']))
    horizon = min(price_cutoff, signal+14400)
    future = [b for b in minute if entry_bar.ts <= b.ts < horizon]
    outcome = close_outcome(future, p, v, contract, f, entry_bar.open, config, price_cutoff >= signal+14400)
    return jsonable(dict(r, **outcome, status='VIAVEL_SIMULADO', net_rr=f['net_rr'],
                         leverage=f['leverage'], financial_band=[f['entry_low'], f['entry_high']]))


def summarize(rows):
    entries = [r for r in rows if r['status'] == 'VIAVEL_SIMULADO']
    resolved = [r for r in entries if 'net_r' in r]
    targets = sum(r['outcome'] == 'ALVO' for r in entries)
    stops = sum(r['outcome'] in ('STOP', 'STOP_AMBIGUO') for r in entries)
    censored = sum(r['outcome'] == 'ABERTO' for r in entries)
    return dict(candidates=len(rows), entries=len(entries), targets=targets, stops=stops,
                open_or_censored=censored, ambiguous_stops=sum(r['outcome'] == 'STOP_AMBIGUO' for r in entries),
                win_rate_closed=str(D(targets)/(targets+stops)*100) if targets+stops else None,
                net_r_sum=str(sum((D(r['net_r']) for r in resolved), D(0))),
                mean_r_closed=str(sum((D(r['net_r']) for r in resolved), D(0))/len(resolved)) if resolved else None,
                blocked=dict(Counter(reason for r in rows for reason in r.get('reasons', []))),
                cancelled_before_entry=sum(r['status'] in ('CANCELLED_BEFORE_ENTRY', 'CANCELADO_TOQUE_ANTES') for r in rows))


def run(protocol_path, source_path, contracts_path, baseline_path, old_minute_path, config_path):
    protocol = json.loads(Path(protocol_path).read_text())
    baseline = json.loads(Path(baseline_path).read_text())
    config = load_config(config_path)
    catalog = {r['symbol']: Contract.from_api(r) for r in json.loads(Path(contracts_path).read_text())['contracts']}
    symbols = sorted({r['symbol'] for r in baseline['records']})
    records, setups_all, diagnostics, causal_checks = [], [], {}, 0
    overlap_checks = 0
    first = int(datetime.fromisoformat(protocol['day_start_brt']).timestamp())
    cutoff, signal_cutoff = protocol['price_cutoff'], protocol['signal_cutoff']
    for symbol in symbols:
        source = json.loads((Path(source_path)/(symbol+'.json')).read_text())
        assert source['price_cutoff'] == cutoff
        minute = [Candle.from_dict(b) for b in source['candles']]
        assert minute[0].ts == first-21600 and minute[-1].end == cutoff
        assert all(a.end == b.ts for a, b in zip(minute, minute[1:]))
        old = json.loads((Path(old_minute_path)/(symbol+'.json')).read_text())['candles']
        by_time = {b.ts:b for b in minute}
        for b in old:
            assert by_time[b['ts']] == Candle.from_dict(b), (symbol, b['ts'])
            overlap_checks += 1
        setups, diagnostics[symbol] = generate(symbol, minute, catalog[symbol].tick, first, signal_cutoff)
        for prefix_at in (first+7*3600, first+12*3600):
            prefix = [b for b in minute if b.end <= prefix_at]
            truncated, _ = generate(symbol, prefix, catalog[symbol].tick, first, prefix_at)
            expected = [s for s in setups if s['signal'] <= prefix_at]
            assert jsonable(truncated) == jsonable(expected), ('future information changed setup', symbol, prefix_at)
            causal_checks += 1
        setups_all.extend(jsonable(setups))
        for setup in setups:
            for delay in (0,60):
                records.append(evaluate_setup(setup, minute, catalog[symbol], config, delay, cutoff))
    mature_cutoff = cutoff-14400
    summary = {}
    for cohort, end in (('all_day', signal_cutoff), ('mature_4h', mature_cutoff)):
        summary[cohort] = {}
        for delay in (0,60):
            summary[cohort][str(delay)] = dict(
                baseline=summarize([r for r in baseline['records'] if r['delay']==delay and r['confirmed_at']<=end]),
                structure_retest=summarize([r for r in records if r['delay']==delay and r['confirmed_at']<=end]))
    by_id = {s['id']:s for s in setups_all}
    distances, rr_failures = [], Counter()
    for row in records:
        if row['delay'] != 0:
            continue
        s, c = by_id[row['plan_id']], catalog[row['symbol']]
        sign = 1 if row['side']=='LONG' else -1
        ref, target, stop = D(s['reference']), D(s['target']), D(s['stop'])
        distances.append(sign*(target-ref)/ref*100)
        if row.get('reasons') != ['RETORNO_RISCO_INSUFICIENTE']:
            continue
        best = ceil_step(D(s['entry_low']),c.tick) if sign==1 else floor_step(D(s['entry_high']),c.tick)
        fee, slip = D(config.taker_fee), D(config.slippage_rate)
        cost_stop = fee*(best+stop)+max(2*c.tick,slip*best)+max(2*c.tick,slip*stop)
        cost_target = fee*(best+target)+max(2*c.tick,slip*best)+max(2*c.tick,slip*target)
        gain = sign*(target-best)-cost_target
        reason = ('GEOMETRIA_SEM_ESPACO' if sign*(best-stop)<=0 or sign*(target-best)<=0 else
                  'TP_NAO_COBRE_CUSTOS' if gain<=0 else 'GANHO_LIQUIDO_MENOR_QUE_RISCO')
        rr_failures[reason] += 1
    finance_diagnostics = dict(rr_failures_immediate=dict(rr_failures),
                               median_target_distance_from_reaction_percent=str(median(distances)) if distances else None,
                               targets_not_beyond_reaction_close=sum(d<=0 for d in distances))
    return dict(experiment=protocol['name'], protocol=protocol, symbols=symbols,
                source_overlap_m1_checked=overlap_checks, causal_prefix_checks=causal_checks,
                mature_signal_cutoff=mature_cutoff, summary=summary,
                diagnostics_finance=finance_diagnostics,
                setups=setups_all, records=records, generation_diagnostics=diagnostics,
                limitations=['Exploratory single previously inspected day; parameters not optimized after results.',
                             'Market structure break need not be reversal of a previous trend; three-wave rules unspecified.',
                             'Zero delay is idealized; synthetic spread/depth and funding zero, no historical fills proven.',
                             'Use mature cohort for fair four-hour comparison; later open positions are censored.',
                             'Independent overlapping plans; sums of R are not a wallet simulation.',
                             'No RSI, 50% retracement, TOTAL3 or H1 EMA filter; no production changes.'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for key in ('protocol','source','contracts','baseline','old-minute','config','output'):
        parser.add_argument('--'+key, required=True)
    args = parser.parse_args()
    result = run(args.protocol,args.source,args.contracts,args.baseline,args.old_minute,args.config)
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('records','setups','generation_diagnostics')},
                     ensure_ascii=False, indent=2))
