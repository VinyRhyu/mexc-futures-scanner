"""Prospectively freeze signals; keep modeled paper P&L separate from quotes.

Only public GET endpoints. Persistence is isolated by forward_state_branch.py.
No account, order, main, scanner-state, or Telegram operations.
"""
import argparse
from collections import defaultdict
from copy import deepcopy
from datetime import datetime,timezone
import gzip,hashlib,json
from pathlib import Path

from mexc_scanner.mexc import MexcClient,quote_is_fresh
from mexc_scanner.models import Candle,Contract,D,jsonable,seconds,stable_id
from scripts.audit_multihour import DAY,HOUR,events,market_gate_allows,simulate,stamp,iso
from scripts.collect_multihour_source import parse_window

PINNED_CODE=('scripts/audit_multihour.py','scripts/forward_momentum.py',
    'scripts/collect_multihour_source.py','mexc_scanner/models.py','mexc_scanner/mexc.py')


def canonical(value):
    return json.dumps(jsonable(value),sort_keys=True,separators=(',',':')).encode()


def digest(value):return hashlib.sha256(canonical(value)).hexdigest()


def read_json(path):return json.loads(Path(path).read_text())


def write_json(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(jsonable(value),sort_keys=True,indent=2)+'\n')


def append_event(root,state,kind,at,payload):
    row=dict(sequence=state['sequence']+1,previous=state['journal_head'],kind=kind,at=at,payload=payload)
    row['hash']=digest(row)
    with (root/'journal.jsonl').open('a') as f:f.write(json.dumps(jsonable(row),sort_keys=True)+'\n')
    state['sequence']=row['sequence'];state['journal_head']=row['hash']


def verify_journal(root,state):
    previous='0'*64;sequence=0
    path=root/'journal.jsonl'
    if path.exists():
        for line in path.read_text().splitlines():
            row=json.loads(line);got=row.pop('hash')
            assert row['previous']==previous and row['sequence']==sequence+1 and digest(row)==got,'Journal chain changed'
            previous=got;sequence+=1
    assert previous==state['journal_head'] and sequence==state['sequence'],'Journal/state mismatch'


def pins():return {p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in PINNED_CODE}


def initialize(root,protocol_path,now,catalog):
    p=read_json(protocol_path);root.mkdir(parents=True,exist_ok=True)
    assert stamp(p['frozen_at_utc'])<stamp(p['decision_start_utc']),'Protocol was not frozen before its evaluation window'
    technical=[{k:v for k,v in arm.items() if k not in ('name','allocation')} for arm in p['variants']]
    assert technical and all(v==technical[0] for v in technical),'Risk comparison requires identical technical rules'
    state=dict(version=1,protocol_sha256=hashlib.sha256(Path(protocol_path).read_bytes()).hexdigest(),
        code_sha256=pins(),started_at=now,sequence=0,journal_head='0'*64,data_end=stamp(p['history_start_utc']),
        contracts={s:jsonable(catalog[s]) for s in p['symbols']},files={},source_revisions={},last_success_hour=None)
    for row in state['contracts'].values():Contract.from_api(row)
    append_event(root,state,'INITIALIZED',now,dict(protocol_sha256=state['protocol_sha256'],code_sha256=state['code_sha256']))
    return state


def verify_state(root,state,protocol_path):
    assert state['protocol_sha256']==hashlib.sha256(Path(protocol_path).read_bytes()).hexdigest(),'Frozen protocol changed'
    assert state['code_sha256']==pins(),'Frozen execution code changed'
    verify_journal(root,state)
    for name,expected in state['files'].items():
        path=root/name
        assert path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest()==expected,'Frozen source file changed: '+name


def load_days(root):
    return {p.stem.split('.')[0]:json.loads(gzip.decompress(p.read_bytes())) for p in sorted((root/'prices').glob('*.json.gz'))}


def merge_observation(days,state,symbol,kind,row,observed_at):
    at=int(row['ts']);day=datetime.fromtimestamp(at,timezone.utc).strftime('%Y-%m-%d')
    section=days.setdefault(day,{}).setdefault(symbol,{}).setdefault(kind,{})
    key=str(at);value=jsonable(row)
    if key in section:
        previous={k:v for k,v in section[key].items() if k!='observed_at'}
        same=(Candle.from_dict(previous)==Candle.from_dict(value)) if kind in ('hourly','fair') else (
            int(previous['ts'])==int(value['ts']) and D(previous['rate'])==D(value['rate']) and int(previous['cycle'])==int(value['cycle']))
        if not same:
            change=stable_id(symbol,kind,at,previous,value)
            state['source_revisions'].setdefault(change,dict(symbol=symbol,kind=kind,at=at,detected_at=observed_at))
        return
    section[key]=dict(value,observed_at=observed_at)


def funding_since(client,symbol,start,end):
    found={};reached=False
    for page in range(1,21):
        data=client._get('/api/v1/contract/funding_rate/history',dict(symbol=symbol,page_num=page,page_size=100))
        rows=data['resultList']
        for r in rows:
            assert r['symbol']==symbol
            at=seconds(r['settleTime']);cycle=int(r['collectCycle'])
            assert 0<cycle<=8
            if start-8*HOUR<=at<=end:
                value=dict(ts=at,rate=D(r['fundingRate']),cycle=cycle)
                assert at not in found or found[at]==value
                found[at]=value
        if rows and min(seconds(r['settleTime']) for r in rows)<=start-8*HOUR:reached=True;break
        if not rows or page>=int(data['totalPage']):break
    assert reached,'Funding does not cover requested start'
    rates=[found[t] for t in sorted(found)]
    assert rates and rates[0]['ts']<=start and all(0<b['ts']-a['ts']<=8*HOUR for a,b in zip(rates,rates[1:]))
    return rates


def collect_increment(client,p,state,end):
    begin=state['data_end'];pending=[]
    for symbol in p['symbols']:
        row=dict(symbol=symbol,hourly=[],fair=[])
        for cursor in range(begin,end,1900*HOUR):
            stop=min(end,cursor+1900*HOUR);params=dict(interval='Min60',start=cursor,end=stop-1)
            for key,prefix in [('hourly','/api/v1/contract/kline/'),('fair','/api/v1/contract/kline/fair_price/')]:
                row[key].extend(parse_window(client._get(prefix+client._symbol(symbol),params),cursor,stop,fair=key=='fair'))
        row['funding']=funding_since(client,symbol,max(stamp(p['history_start_utc']),begin-8*HOUR),end)
        pending.append(row)
    return pending


def markets_from_days(days,state,p,end):
    result={s:dict(contract=Contract.from_api(state['contracts'][s]),hourly={},fair={},funding=[],funding_by_time=defaultdict(list)) for s in p['symbols']}
    for day in sorted(days):
        for symbol,sections in days[day].items():
            m=result[symbol]
            for kind,rows in sections.items():
                for _,row in sorted(rows.items(),key=lambda item:int(item[0])):
                    if kind in ('hourly','fair'):
                        c=Candle.from_dict(row);c.validate();assert c.tf==HOUR and c.end<=end
                        m[kind][c.ts]=c
                    else:
                        e=dict(ts=row['ts'],rate=D(row['rate']),cycle=int(row['cycle']))
                        m['funding'].append(e);m['funding_by_time'][e['ts']].append(e)
    expected=set(range(stamp(p['history_start_utc']),end,HOUR))
    for m in result.values():
        assert set(m['hourly'])==set(m['fair'])==expected,'Incomplete fixed cohort/hourly timeline'
        m['hourly']=dict(sorted(m['hourly'].items()));m['fair']=dict(sorted(m['fair'].items()))
        m['funding'].sort(key=lambda e:e['ts'])
        assert m['funding'] and m['funding'][0]['ts']<stamp(p['decision_start_utc'])
    return result


def freeze_day(root,state,p,markets,catalog,now):
    day=now//DAY*DAY;first,last=stamp(p['decision_start_utc']),stamp(p['decision_end_exclusive_utc'])
    if not first<=day<last:return
    target=day+HOUR;path=root/'decisions'/f'{day}.json'
    if path.exists():return
    if not day<=now<target:return
    if any(not m['hourly'] or max(c.end for c in m['hourly'].values())<day for m in markets.values()):return
    entries=[];updates={};variant=p['variants'][0]
    for symbol,m in markets.items():
        candidates,changes=events(symbol,m,variant,target,target+HOUR,HOUR)
        updates[symbol]=changes.get(target)
        compatible=jsonable(m['contract'])==jsonable(Contract.from_api(catalog[symbol]))
        for signal in candidates.get(target,[]):
            assert signal['signal_at']==day
            signal['frozen_market_gate']=market_gate_allows(markets,signal,variant['market_gate'])
            signal['source_gate_reasons']=[] if compatible else ['CONTRACT_RULES_CHANGED']
            entries.append(signal)
    record=dict(status='FROZEN_BEFORE_ENTRY',signal_at=day,entry_at=target,frozen_at=now,
        protocol_sha256=state['protocol_sha256'],entries=entries,updates=updates)
    write_json(path,record);append_event(root,state,'SIGNAL_FROZEN',now,dict(signal_at=day,sha256=digest(record),candidates=len(entries)))


def record_missing_days(root,state,p,now):
    for day in range(stamp(p['decision_start_utc']),stamp(p['decision_end_exclusive_utc']),DAY):
        path=root/'decisions'/f'{day}.json'
        if day+HOUR<=now and not path.exists():
            record=dict(status='MISSED_FREEZE_WINDOW',signal_at=day,entry_at=day+HOUR,recorded_at=now,entries=[],updates={})
            write_json(path,record);append_event(root,state,'MISSED_FREEZE_WINDOW',now,dict(signal_at=day))


def quote_capture(root,state,p,client,now):
    day=now//DAY*DAY;target=day+HOUR
    if not stamp(p['decision_start_utc'])<=day<stamp(p['decision_end_exclusive_utc']):return
    path=root/'quotes'/f'{day}.json'
    if path.exists() or now<target:return
    if now>target+p['quote_max_delay_seconds']:
        write_json(path,dict(status='MISSED_QUOTE_WINDOW',entry_at=target,recorded_at=now,quotes={}))
        append_event(root,state,'MISSED_QUOTE_WINDOW',now,dict(entry_at=target));return
    tickers={r.get('symbol'):r for r in client.tickers()}
    quotes={}
    for symbol in p['symbols']:
        row=tickers.get(symbol,{})
        quotes[symbol]=dict(valid=quote_is_fresh(row,now,p['quote_max_age_seconds']),
            bid=row.get('bid1'),ask=row.get('ask1'),last=row.get('lastPrice'),timestamp=row.get('timestamp'))
    decision=root/'decisions'/f'{day}.json';books={}
    if decision.exists():
        signals=[s for s in read_json(decision)['entries'] if s.get('frozen_market_gate') and not s.get('source_gate_reasons')]
        selected=sorted(signals,key=lambda s:(-D(s['score']),s['symbol']))[:3]
        for s in selected:
            try:books[s['symbol']]=client.depth(s['symbol'])
            except Exception as exc:books[s['symbol']]=dict(error=type(exc).__name__)
    completed=client.server_time()
    for symbol in quotes:quotes[symbol]['valid']=quote_is_fresh(tickers.get(symbol,{}),completed,p['quote_max_age_seconds'])
    status='OBSERVED_QUOTES' if completed<=target+p['quote_max_delay_seconds'] else 'LATE_QUOTES'
    record=dict(status=status,entry_at=target,observed_at=completed,delay_seconds=completed-target,
        quotes=quotes,top3_depth=books,interpretation='Observed public quotes, not an order or execution fill')
    write_json(path,record);append_event(root,state,status,completed,dict(entry_at=target,sha256=digest(record)))


def frozen_timeline(root,p,protocol_sha256=None):
    timeline=dict(entries={},updates={s:{} for s in p['symbols']});days=[]
    for path in sorted((root/'decisions').glob('*.json')):
        row=read_json(path);days.append(row)
        if row['status']!='FROZEN_BEFORE_ENTRY':continue
        if protocol_sha256:assert row['protocol_sha256']==protocol_sha256
        assert stamp(p['decision_start_utc'])<=row['signal_at']<stamp(p['decision_end_exclusive_utc'])
        assert row['frozen_at']<row['entry_at'] and row['signal_at']+HOUR==row['entry_at']
        entries=[]
        for s in row['entries']:
            for k in ('score','stop','turnover','atr'):s[k]=D(s[k])
            entries.append(s)
        timeline['entries'][row['entry_at']]=entries
        for symbol,value in row['updates'].items():
            if value is not None:
                value['close']=D(value['close']);value['atr']=D(value['atr'])
                timeline['updates'][symbol][row['entry_at']]=value
    return timeline,days


def replay(root,state,p,markets,asof):
    first=stamp(p['decision_start_utc']);end=min(asof,stamp(p['evaluation_end_utc']))
    timeline,days=frozen_timeline(root,p,state['protocol_sha256']);wallets={};previous=read_json(root/'wallets.json') if (root/'wallets.json').exists() else {}
    for variant in p['variants']:
        for costs in p['costs']:
            key=variant['name']+'__'+costs['name']
            begin=min(first,end)
            block=dict(start=iso(begin),end=iso(end),validation_start=iso(begin))
            wallet=simulate(markets,variant,block,p,costs,frozen_events=timeline,force_flat=False)
            old=previous.get(key,{}).get('trades',[])
            assert jsonable(wallet['trades'][:len(old)])==old,'A closed paper trade changed'
            for trade in wallet['trades'][len(old):]:
                append_event(root,state,'PAPER_TRADE_CLOSED',asof,dict(wallet=key,trade=trade,
                    interpretation='Frozen signal; modeled H1 fill, not live execution'))
            wallets[key]=wallet
    write_json(root/'wallets.json',wallets)
    quotes=[read_json(f) for f in (root/'quotes').glob('*.json')]
    frozen=sum(d['status']=='FROZEN_BEFORE_ENTRY' for d in days)
    observed=sum(q['status']=='OBSERVED_QUOTES' for q in quotes)
    complete=end>=stamp(p['evaluation_end_utc'])
    limits=p['checkpoint'];coverage=observed/30
    conditions=dict(checkpoint_reached=complete,frozen_days_sufficient=frozen>=limits['minimum_frozen_days'],
        quote_coverage_sufficient=coverage>=float(limits['minimum_quote_coverage']),
        no_source_revisions=not state['source_revisions'])
    models={}
    for variant in p['variants']:
        name=variant['name'];arms={c['name']:wallets[name+'__'+c['name']] for c in p['costs']}
        quote_by_day={q['entry_at']//DAY*DAY:q for q in quotes}
        quote_quality={}
        for cost,w in arms.items():
            positions=w['trades']+([w['open_position']] if w['open_position'] else [])
            matched=sum(quote_by_day.get(t['signal_at'],{}).get('status')=='OBSERVED_QUOTES'
                and quote_by_day[t['signal_at']].get('quotes',{}).get(t['symbol'],{}).get('valid',False) for t in positions)
            comparisons=[]
            for t in positions:
                snapshot=quote_by_day.get(t['signal_at'],{});q=snapshot.get('quotes',{}).get(t['symbol'],{})
                if snapshot.get('status')=='OBSERVED_QUOTES' and q.get('valid'):
                    observed=D(q['ask'] if t['sign']==1 else q['bid'])
                    comparisons.append(dict(symbol=t['symbol'],planned_entry_at=t['opened_at'],observed_at=snapshot['observed_at'],
                        paper_entry=t['entry'],observed_side_quote=observed,
                        adverse_difference_bps=t['sign']*(observed-t['entry'])/t['entry']*10000,
                        book_observed=t['symbol'] in snapshot.get('top3_depth',{}) and 'error' not in snapshot['top3_depth'][t['symbol']]))
            quote_quality[cost]=dict(paper_entries=len(positions),valid_observed_entry_quotes=matched,
                coverage=matched/len(positions) if positions else 0,price_comparisons=comparisons)
        checks=dict(enough_trades=all(w['summary']['positions']>=limits['minimum_closed_trades_per_wallet'] for w in arms.values()),
            positive_base_and_stress=all(w['marked_equity']>D(p['initial_equity']) for w in arms.values()),
            drawdown_within_limit=all(w['summary']['max_drawdown_pct']<=D(limits['maximum_drawdown_pct']) for w in arms.values()),
            no_liquidations=all(not w['summary']['outcomes'].get('LIQUIDACAO',0) for w in arms.values()),
            flat_at_checkpoint=all(w['open_position'] is None for w in arms.values()) if complete else False,
            observed_entry_quote_coverage=all(q['coverage']>=float(limits['minimum_quote_coverage']) for q in quote_quality.values()))
        models[name]=dict(checks=checks,quote_quality=quote_quality,research_screen_passed=all(conditions.values()) and all(checks.values()),
            wallets={c:dict(summary=w['summary'],cash=w['cash'],marked_equity=w['marked_equity'],
                open_position=w['open_position'],valuation=w['valuation']) for c,w in arms.items()})
    status=dict(name=p['name'],asof_utc=iso(asof),phase='COMPLETED_CHECKPOINT' if complete else 'COLLECTING' if asof>=first else 'WARMUP',
        frozen_days=frozen,missed_days=sum(d['status']=='MISSED_FREEZE_WINDOW' for d in days),
        observed_quote_windows=observed,missed_or_late_quote_windows=len(quotes)-observed,
        conditions=conditions,models=models,source_revisions=len(state['source_revisions']),
        execution_validated=False,approved_for_production=False,
        interpretation='Prospective signals, deferred H1 paper replay; quotes are a separate observational lane.')
    write_json(root/'status.json',status)
    return status


def render_status(status):
    lines=['# Momentum — validação prospectiva','','Fase: '+status['phase'],
        'Dados fechados até '+status['asof_utc']+'.',
        f"Dias congelados: {status['frozen_days']}/30; dias perdidos: {status['missed_days']}; janelas de cotação observadas: {status['observed_quote_windows']}.",
        '', '| Carteira | Patrimônio marcado | Operações encerradas | Queda máxima H1 |','| --- | ---: | ---: | ---: |']
    for name,model in status['models'].items():
        for cost,w in model['wallets'].items():
            lines.append(f"| {name} / {cost} | {D(w['marked_equity']):.4f} | {w['summary']['positions']} | {D(w['summary']['max_drawdown_pct']):.3f}% |")
    lines+=['','Sinais congelados antes do desfecho; preenchimentos H1 ainda modelados. Cotações observadas não comprovam execução. Produção e Telegram inalterados.']
    return '\n'.join(lines)+'\n'


def run(protocol_path,directory,client=None):
    p=read_json(protocol_path);root=Path(directory);client=client or MexcClient()
    initial_now=client.server_time();catalog={c['symbol']:c for c in client.contracts()}
    assert set(p['symbols'])<=set(catalog),'Fixed cohort is incomplete'
    if (root/'state.json').exists():
        state=read_json(root/'state.json');verify_state(root,state,protocol_path)
    else:
        assert not (root/'journal.jsonl').exists(),'State missing beside existing journal; never reset'
        state=initialize(root,protocol_path,initial_now,catalog)
    hour=initial_now//HOUR*HOUR
    if state['last_success_hour']==hour:
        return read_json(root/'status.json')
    endpoint=min(hour,stamp(p['evaluation_end_utc']))
    days=load_days(root);pending=collect_increment(client,p,state,endpoint)
    now=client.server_time()
    for row in pending:
        for key in ('hourly','fair','funding'):
            for item in row[key]:
                merge_observation(days,state,row['symbol'],key,jsonable(item),now)
    markets=markets_from_days(days,state,p,endpoint)
    freeze_day(root,state,p,markets,catalog,now)
    record_missing_days(root,state,p,now)
    quote_capture(root,state,p,client,now)
    status=replay(root,state,p,markets,endpoint)
    for day,data in days.items():
        path=root/'prices'/(day+'.json.gz');path.parent.mkdir(exist_ok=True)
        raw=gzip.compress(canonical(data),mtime=0)
        if not path.exists() or path.read_bytes()!=raw:path.write_bytes(raw)
    state['data_end']=endpoint;state['last_success_hour']=hour
    append_event(root,state,'ROUND_COMPLETED',now,dict(asof=endpoint,status_sha256=digest(status)))
    (root/'status.md').write_text(render_status(jsonable(status)))
    state['files']={str(f.relative_to(root)):hashlib.sha256(f.read_bytes()).hexdigest()
        for folder in ('prices','decisions','quotes') for f in (root/folder).glob('*') if f.is_file()}
    for name in ('wallets.json','status.json','status.md'):
        state['files'][name]=hashlib.sha256((root/name).read_bytes()).hexdigest()
    write_json(root/'state.json',state)
    print(json.dumps(jsonable(dict(phase=status['phase'],asof=status['asof_utc'],frozen_days=status['frozen_days']))),flush=True)
    return status


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--protocol',required=True);ap.add_argument('--directory',required=True);a=ap.parse_args()
    try:run(a.protocol,a.directory)
    except Exception as exc:
        root=Path(a.directory);root.mkdir(parents=True,exist_ok=True)
        write_json(root/'round_error.json',dict(error_type=type(exc).__name__,reason=str(exc)[:200]))
        raise
