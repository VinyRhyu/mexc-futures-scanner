"""Fixed H1/H4 family, one isolated wallet, public archived data only.

Signals, risk and rank depend only on closed bars; execution is delayed one H1.
This module never sends orders, alerts, or writes production state.
"""
import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path

from mexc_scanner.models import Candle, Contract, D, ceil_step, floor_step, jsonable

HOUR = 3600
DAY = 86400


def stamp(value):
    return int(datetime.fromisoformat(value).timestamp())


def iso(at):
    return datetime.fromtimestamp(at, timezone.utc).isoformat()


def aggregate(hourly, hours):
    groups = defaultdict(list)
    for bar in hourly:
        groups[bar.ts // (hours * HOUR) * hours * HOUR].append(bar)
    result = []
    for at, bars in sorted(groups.items()):
        if len(bars) != hours:
            continue
        assert [b.ts for b in bars] == list(range(at, at + hours * HOUR, HOUR))
        result.append(Candle(at, hours * HOUR, bars[0].open,
            max(b.high for b in bars), min(b.low for b in bars), bars[-1].close,
            sum((b.volume for b in bars), D(0))))
    return result


def ema(values, period):
    alpha = 2 / (period + 1)
    result = []
    for value in values:
        result.append(value if not result else alpha * value + (1-alpha) * result[-1])
    return result


def events(symbol, market, variant, start, end, delay=HOUR):
    if variant['kind'] == 'MOMENTUM':
        return momentum_events(symbol, market, variant, start, end, delay)
    bars = aggregate(list(market['hourly'].values()), variant['tf_hours'])
    closes = [float(b.close) for b in bars]
    trend = ema(closes, variant['ema'])
    e20, e50 = ema(closes, 20), ema(closes, 50)
    ranges = [float(b.high-b.low) if i == 0 else max(float(b.high-b.low),
        abs(float(b.high-bars[i-1].close)), abs(float(b.low-bars[i-1].close)))
        for i, b in enumerate(bars)]
    entries, updates = defaultdict(list), {}
    for i, bar in enumerate(bars):
        decision = bar.end + delay
        if i < max(variant['ema'], variant['channel'], 15) or not start <= decision < end:
            continue
        a = sum(ranges[i-13:i+1]) / 14
        if a <= 0:
            continue
        previous = bars[i-variant['channel']:i]
        upper, lower = max(float(b.high) for b in previous), min(float(b.low) for b in previous)
        exit_bars = bars[i-variant['exit_channel']:i]
        exit_low, exit_high = min(b.low for b in exit_bars), max(b.high for b in exit_bars)
        updates[decision] = dict(signal_at=bar.end, close=bar.close, atr=D(str(a)),
            exit_long=bar.close < exit_low, exit_short=bar.close > exit_high)
        sign = 0
        if variant['kind'] == 'CHANNEL':
            if closes[i] > upper and closes[i] > trend[i]:
                sign = 1
            elif closes[i] < lower and closes[i] < trend[i]:
                sign = -1
            score = abs(closes[i] - (upper if sign == 1 else lower)) / a
        else:
            if e20[i] > e50[i] > trend[i] and closes[i-1] <= e20[i-1] and closes[i] > e20[i]:
                sign = 1
            elif e20[i] < e50[i] < trend[i] and closes[i-1] >= e20[i-1] and closes[i] < e20[i]:
                sign = -1
            score = abs(closes[i]-e20[i]) / a
        if not sign:
            continue
        known = [market['hourly'].get(t) for t in range(bar.end-DAY, bar.end, HOUR)]
        if any(b is None for b in known):
            continue
        turnover = sum((b.volume * market['contract'].size * b.close for b in known), D(0))
        tick = market['contract'].tick
        raw_stop = bar.close-sign*D(variant['stop_atr'])*D(str(a))
        stop = floor_step(raw_stop, tick) if sign == 1 else ceil_step(raw_stop, tick)
        entries[decision].append(dict(symbol=symbol, sign=sign, score=D(str(score)),
            signal_at=bar.end, stop=stop, turnover=turnover, atr=D(str(a))))
    return dict(entries), updates


def momentum_events(symbol, market, variant, start, end, delay=HOUR):
    bars = aggregate(list(market['hourly'].values()), 24)
    entries, updates = defaultdict(list), {}
    for i, bar in enumerate(bars):
        decision = bar.end+delay
        if i < 14 or not start <= decision < end:
            continue
        known = bars[i-13:i+1]
        trs = [max(b.high-b.low, abs(b.high-bars[i-13+j-1].close),
            abs(b.low-bars[i-13+j-1].close)) for j,b in enumerate(known)]
        a = sum(trs, D(0))/14
        ret = bar.close/bars[i-variant['lookback_days']].close-1
        updates[decision] = dict(signal_at=bar.end,close=bar.close,atr=a,
            exit_long=ret <= 0,exit_short=ret >= 0)
        if not ret or a <= 0:
            continue
        sign = 1 if ret > 0 else -1
        distance = min(D(variant['stop_atr'])*a,bar.close*D(variant['stop_cap']))
        stop = bar.close-sign*distance
        tick = market['contract'].tick
        stop = floor_step(stop,tick) if sign == 1 else ceil_step(stop,tick)
        turnover = sum((market['hourly'][t].volume*market['contract'].size*
            market['hourly'][t].close for t in range(bar.end-DAY,bar.end,HOUR)),D(0))
        entries[decision].append(dict(symbol=symbol,sign=sign,score=abs(ret)/(a/bar.close),
            signal_at=bar.end,stop=stop,turnover=turnover,atr=a))
    return dict(entries), updates


def execution(mid, direction, tick, costs):
    spread, slip = D(costs['spread']), D(costs['slippage'])
    raw = mid + direction*(mid*spread/2+max(2*tick, mid*slip))
    return ceil_step(raw, tick) if direction == 1 else floor_step(raw, tick)


def liquidation(position):
    q, entry = position['quantity'], position['entry']
    margin = position['margin']-position['funding_paid']
    rate = position['mmr']+position['liquidation_fee']
    if position['sign'] == 1:
        return (q*entry-margin)/(q*(1-rate))
    return (q*entry+margin)/(q*(1+rate))


def risk_budget(signal, market, at, cash, protocol, variant, costs):
    c = market['contract']; sign = signal['sign']; fee = D(costs['fee'])
    if signal['turnover'] < D(protocol['minimum_turnover']):
        return None, 'LIQUIDEZ'
    # Every latency bar is already closed when the order decision is made.
    for t in range(signal['signal_at'], at, HOUR):
        bar = market['fair'][t] if c.stop_only_fair else market['hourly'][t]
        if (bar.low <= signal['stop'] if sign == 1 else bar.high >= signal['stop']):
            return None, 'STOP_DURANTE_LATENCIA'
    entry = execution(market['hourly'][at].open, sign, c.tick, costs)
    stop = signal['stop']
    if stop <= 0 or sign*(entry-stop) <= 0:
        return None, 'STOP_INVALIDO'
    exit_at_stop = execution(stop, -sign, c.tick, costs)
    prior = [r for r in market['funding'] if r['ts'] < at]
    if not prior:
        return None, 'SEM_FUNDING_CONHECIDO'
    last = prior[-1]
    fund_rate = max(D(last['rate'])*sign, D(0))
    fund_reserve = entry*fund_rate*D(variant['max_hold_hours'])/D(last['cycle'])
    loss_unit = sign*(entry-exit_at_stop)+fee*(entry+exit_at_stop)+fund_reserve
    reserve = fee*(entry+max(entry, stop))+fund_reserve
    maximum = min(cash*D(protocol['risk_fraction'])/loss_unit,
        cash/(entry/D(protocol['leverage'])+reserve))
    contracts = floor_step(maximum/c.size, c.volume_step)
    if contracts < c.min_volume or contracts > c.max_volume:
        return None, 'LOTE'
    mmr, tier = c.margin_tier(contracts)
    if tier < protocol['leverage']:
        return None, 'ALAVANCAGEM'
    quantity = contracts*c.size
    position = dict(symbol=signal['symbol'], sign=sign, entry=entry, stop=stop,
        original_stop=stop, opened_at=at, signal_at=signal['signal_at'],
        deadline=at+variant['max_hold_hours']*HOUR, quantity=quantity, contracts=contracts,
        tick=c.tick, margin=quantity*entry/D(protocol['leverage']), mmr=mmr,
        liquidation_fee=c.liquidation_fee if c.liquidation_fee is not None else fee,
        funding_paid=D(0), entry_fee=quantity*entry*fee, equity_before=cash,
        planned_risk=quantity*loss_unit, score=signal['score'])
    if sign*(entry-liquidation(position)) < D(protocol['min_liquidation_buffer'])*sign*(entry-stop):
        return None, 'STOP_PROXIMO_DA_LIQUIDACAO'
    assert position['planned_risk'] <= cash*D(protocol['risk_fraction'])+D('1E-18')
    assert position['margin']+quantity*reserve <= cash+D('1E-18')
    return position, None


def exit_event(position, last, fair, stop_only_fair):
    sign = position['sign']
    liq = liquidation(position)
    source = fair if stop_only_fair else last
    bad = source.low <= position['stop'] if sign == 1 else source.high >= position['stop']
    liq_hit = fair.low <= liq if sign == 1 else fair.high >= liq
    if liq_hit:
        return 'LIQUIDACAO', None, bad
    if bad:
        if stop_only_fair:
            mid = last.open if sign*(source.open-position['stop']) <= 0 else (last.low if sign == 1 else last.high)
        else:
            mid = min(position['stop'], last.open) if sign == 1 else max(position['stop'], last.open)
        return 'STOP', mid, False
    return None


def settlement_amount(position, event, last, fair, stop_only_fair):
    amount = position['sign']*D(event['rate'])*position['quantity']*fair.open
    source = fair if stop_only_fair else last
    stop_gap = position['sign']*(source.open-position['stop']) <= 0
    liquidation_gap = position['sign']*(fair.open-liquidation(position)) <= 0
    # Opening settlement and a gap exit can share the timestamp; do not assign
    # an unproved credit. Adverse debits remain a conservative cash assumption.
    return D(0) if amount < 0 and (stop_gap or liquidation_gap) else amount


def close(position, mid, at, reason, costs, ambiguous=False):
    if reason == 'LIQUIDACAO':
        price = None; fee = D(0)
        delta = -(position['margin']-position['funding_paid'])
    else:
        price = execution(mid, -position['sign'], position['tick'], costs)
        fee = position['quantity']*price*D(costs['fee'])
        delta = position['sign']*position['quantity']*(price-position['entry'])-fee
    return dict(position, exit=price, exit_at=at, exit_fee=fee, outcome=reason,
        ambiguous=ambiguous, net=delta-position['entry_fee']-position['funding_paid']), delta


def summarize(initial, final, trades, equity, skips):
    peak = initial; dd = D(0)
    for row in equity:
        peak = max(peak, row['equity']); dd = max(dd, (peak-row['equity'])/peak)
    positive = sum((t['net'] for t in trades if t['net'] > 0), D(0))
    negative = -sum((t['net'] for t in trades if t['net'] < 0), D(0))
    return dict(initial=initial, final=final, return_pct=(final/initial-1)*100,
        max_drawdown_pct=dd*100, positions=len(trades), positive=sum(t['net'] > 0 for t in trades),
        profit_factor=positive/negative if negative else None,
        outcomes=dict(Counter(t['outcome'] for t in trades)), skipped=dict(skips),
        trading_fees=sum((t['entry_fee']+t['exit_fee'] for t in trades), D(0)),
        funding_paid=sum((t['funding_paid'] for t in trades), D(0)))


def market_gate_allows(markets, signal, gate):
    btc = markets['BTC_USDT']['hourly']
    at = signal['signal_at']
    close = btc[at-HOUR].close
    week_return = close/btc[at-7*DAY-HOUR].close-1
    if week_return*signal['sign'] <= 0:
        return False
    if gate == 'BTC7_AND_1_SIGN':
        day_return = close/btc[at-DAY-HOUR].close-1
        return day_return*signal['sign'] > 0
    if gate != 'BTC7_SIGN':
        raise ValueError('Unknown pre-registered market gate')
    return True


def simulate(markets, variant, block, protocol, costs):
    start, end = stamp(block['start']), stamp(block['end'])
    entry_events = defaultdict(list); updates = {}
    for symbol, market in markets.items():
        e, u = events(symbol, market, variant, start, end, protocol['signal_delay_seconds'])
        for t, rows in e.items():
            entry_events[t].extend(rows)
        updates[symbol] = u
    cash = initial = D(protocol['initial_equity']); position = None
    skips = Counter(); trades = []; curve = [dict(at=start, equity=cash)]
    cashflows = []; delay = protocol['signal_delay_seconds']
    for at in range(start, end, HOUR):
        # These exits/stop updates are known at the opening, before any new fill.
        if position:
            market = markets[position['symbol']]
            update = updates[position['symbol']].get(at)
            channel = False
            if update and update['signal_at'] >= position['opened_at']:
                channel = update['exit_long'] if position['sign'] == 1 else update['exit_short']
                proposed = update['close']-position['sign']*D(variant['trail_atr'])*update['atr']
                rounded = floor_step(proposed, position['tick']) if position['sign'] == 1 else ceil_step(proposed, position['tick'])
                position['stop'] = max(position['stop'], rounded) if position['sign'] == 1 else min(position['stop'], rounded)
            if channel or at >= position['deadline']:
                trade, delta = close(position, market['hourly'][at].open, at,
                    'CANAL' if channel else 'TEMPO', costs)
                cash += delta; trades.append(trade); cashflows.append(delta)
                position = None
        candidates = entry_events.get(at, [])
        if position:
            skips['CARTEIRA_OCUPADA'] += len(candidates)
        else:
            ranked = []
            for signal in candidates:
                if variant.get('market_gate'):
                    if not market_gate_allows(markets, signal, variant['market_gate']):
                        skips['DIRECAO_CONTRA_BTC_7D'] += 1
                        continue
                candidate, reason = risk_budget(signal, markets[signal['symbol']], at,
                    cash, protocol, variant, costs)
                if candidate is None:
                    skips[reason] += 1
                    continue
                rank = (-signal['score'], candidate['entry_fee']/candidate['planned_risk'], signal['symbol'])
                ranked.append((rank, candidate))
            if ranked:
                ranked.sort(key=lambda row: row[0]); position = ranked[0][1]
                skips['OUTRO_PLANO_PRIORIZADO'] += len(ranked)-1
                cash -= position['entry_fee']; cashflows.append(-position['entry_fee'])
        if position:
            market = markets[position['symbol']]
            last, fair = market['hourly'][at], market['fair'][at]
            if at > position['opened_at']:
                for event in market['funding_by_time'].get(at, []):
                    amount = settlement_amount(position,event,last,fair,market['contract'].stop_only_fair)
                    position['funding_paid'] += amount; cash -= amount; cashflows.append(-amount)
            result = exit_event(position, last, fair, market['contract'].stop_only_fair)
            if result or at+HOUR == end:
                reason, mid, ambiguous = result if result else ('FIM_DO_BLOCO', last.close, False)
                trade, delta = close(position, mid, at+HOUR, reason, costs, ambiguous)
                cash += delta; trades.append(trade); cashflows.append(delta); position = None
        marked = cash
        if position:
            mid = markets[position['symbol']]['fair'][at].close
            price = execution(mid, -position['sign'], position['tick'], costs)
            marked += position['sign']*position['quantity']*(price-position['entry'])-position['quantity']*price*D(costs['fee'])
        assert cash >= 0 and marked > 0, 'Wallet exhausted or negative'
        curve.append(dict(at=at+HOUR, equity=marked))
    assert position is None
    assert abs(initial+sum(cashflows, D(0))-cash) < D('1E-16')
    assert abs(initial+sum((t['net'] for t in trades), D(0))-cash) < D('1E-16')
    assert all(a['exit_at'] <= b['opened_at'] for a, b in zip(trades, trades[1:]))
    split = stamp(block['validation_start'])
    split_equity = next(row['equity'] for row in curve if row['at'] == split)
    months = {}
    month_start = initial
    for row in curve[1:]:
        d = datetime.fromtimestamp(row['at'], timezone.utc)
        if (d.day == 1 and d.hour == 0) or row['at'] == end:
            key = datetime.fromtimestamp(row['at']-1, timezone.utc).strftime('%Y-%m')
            months[key] = dict(start=month_start, end=row['equity'], return_pct=(row['equity']/month_start-1)*100)
            month_start = row['equity']
    return dict(summary=summarize(initial, cash, trades, curve, skips),
        temporal_blocks=dict(development_return_pct=(split_equity/initial-1)*100,
            verification_return_pct=(cash/split_equity-1)*100),
        months=months, trades=trades, equity_curve=curve)


def load_markets(block, protocol, data_root=None):
    original = Path(block['source'])
    path = Path(data_root)/original.parent.name/original.name if data_root else original
    manifest = path/'manifest.json'
    assert hashlib.sha256(manifest.read_bytes()).hexdigest() == protocol['source_manifests'][str(original/'manifest.json')]
    markets = {}; hashes = {}; start, end = stamp(block['start']), stamp(block['end'])
    for symbol in protocol['symbols']:
        source = path/(symbol+'.json.gz'); raw = gzip.decompress(source.read_bytes())
        hashes[symbol] = hashlib.sha256(raw).hexdigest(); row = json.loads(raw)
        assert hashes[symbol] == protocol['data_sha256'][block['name']][symbol]
        assert row['symbol'] == symbol
        hourly = [Candle.from_dict(b) for b in row['hourly']]
        for bar in hourly:
            bar.validate()
            assert bar.tf == HOUR
        assert all(a.end == b.ts for a, b in zip(hourly, hourly[1:]))
        assert hourly[0].ts <= start-240*HOUR and hourly[-1].end >= end
        fair = [Candle.from_dict(b) for b in row.get('fair', row['hourly'])]
        for bar in fair:
            bar.validate()
            assert bar.tf == HOUR
        hmap, fmap = {b.ts:b for b in hourly}, {b.ts:b for b in fair}
        assert set(hmap) == set(fmap)
        funding = sorted([dict(ts=int(e['ts']), rate=D(e['rate']), cycle=e.get('cycle'))
            for e in row['funding']], key=lambda e:e['ts'])
        for i, event in enumerate(funding):
            # Older archives omitted the cycle. Infer it only from the preceding
            # observed settlement interval, never a future settlement.
            event['cycle'] = int(event['cycle']) if event['cycle'] else (
                (event['ts']-funding[i-1]['ts'])//HOUR if i else 8)
            assert 0 < event['cycle'] <= 8
        # Known prior event and full historical coverage, no future-rate input.
        assert funding[0]['ts'] < start and funding[-1]['ts'] >= end
        relevant = [e for e in funding if start-8*HOUR <= e['ts'] <= end+8*HOUR]
        assert all(0 < b['ts']-a['ts'] <= 8*HOUR for a,b in zip(relevant,relevant[1:]))
        by_time = defaultdict(list)
        for event in funding:
            assert event['ts'] % HOUR == 0
            by_time[event['ts']].append(event)
        markets[symbol] = dict(contract=Contract.from_api(row['contract']),
            hourly=hmap, fair=fmap, funding=funding, funding_by_time=by_time)
    return markets, hashes


def run(protocol_path, data_root=None):
    raw = Path(protocol_path).read_bytes(); protocol = json.loads(raw)
    result = dict(protocol=protocol, protocol_sha256=hashlib.sha256(raw).hexdigest(),
        experiments={}, data_sha256={}, production_changed=False, approved_for_production=False,
        independent_validation=False)
    for block in protocol['blocks']:
        markets, hashes = load_markets(block, protocol, data_root)
        result['data_sha256'][block['name']] = hashes
        result['experiments'][block['name']] = {}
        for variant in protocol['variants']:
            arms = {}
            for costs in protocol['costs']:
                wallet = simulate(markets, variant, block, protocol, costs)
                arms[costs['name']] = wallet
                print(json.dumps(jsonable(dict(block=block['name'], variant=variant['name'],
                    costs=costs['name'], **wallet['summary'], temporal_blocks=wallet['temporal_blocks']))), flush=True)
            result['experiments'][block['name']][variant['name']] = arms
    result['research_screen'] = {}
    for variant in protocol['variants']:
        name = variant['name']; recent = result['experiments']['recent_fair'][name]
        past = result['experiments']['historical_last_proxy'][name]['base']
        minimum_recent = 5 if variant['kind'] == 'MOMENTUM' else 30
        result['research_screen'][name] = (recent['base']['summary']['final'] > D(protocol['initial_equity'])
            and recent['stress']['summary']['final'] > D(protocol['initial_equity'])
            and recent['base']['summary']['max_drawdown_pct'] <= 10
            and recent['base']['summary']['positions'] >= minimum_recent
            and (variant['kind'] != 'MOMENTUM' or
                 recent['base']['summary']['positions']+past['summary']['positions'] >= 30)
            and all(v > 0 for v in past['temporal_blocks'].values()))
    return jsonable(result)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--protocol', required=True); parser.add_argument('--output', required=True)
    parser.add_argument('--data-root', help='Portable root containing momentum/source and momentum-week10x/source')
    args = parser.parse_args()
    result = run(args.protocol, args.data_root)
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result['research_screen'], indent=2))
