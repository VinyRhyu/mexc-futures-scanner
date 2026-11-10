"""Explain the original 57 opportunities without changing wallet decisions."""
from collections import Counter
import gzip
import json
from pathlib import Path
from mexc_scanner.config import Config
from scripts.audit_portfolio import simulate
from scripts.audit_sustained_trigger import read_dataset,MODE


def mapped_summary(events):
    eligible=[e for e in events if e['baseline_eligible']]
    return {'original_opportunities':len(eligible),
        'statuses':dict(Counter(e['status'] for e in eligible)),
        'financial_reasons':dict(Counter(x for e in eligible for x in e.get('reasons',[]))),
        'by_original_outcome':{o:dict(Counter(e['status'] for e in eligible if e['baseline_outcome']==o))
                               for o in ('ALVO','STOP','ABERTO')},
        'new_executions_outside_original_57':sum(e['status']=='EXECUTADA' and not e['baseline_eligible'] for e in events)}


def run():
    source=Path('reports/early-trigger-source')
    sustained=Path('reports/sustained-source')
    previous=json.loads(Path('reports/portfolio-source/result.json').read_text())
    prior=json.loads((source/'summary.json').read_text())
    cfg=Config(**prior['config']).validate()
    rows=json.loads(gzip.decompress((sustained/'all-formations.json.gz').read_bytes()))
    datasets={}
    for manifest in prior['datasets']:
        d=read_dataset(source,manifest)
        d['minute_map']={c.ts:c for c in d.pop('minute')}
        datasets[manifest['symbol']]=d
    events=[]
    result=simulate(rows,datasets,cfg,decisions=events)
    plain=simulate(rows,datasets,cfg)
    if result!=plain or any(previous[k]!=v for k,v in result.items()):
        raise ValueError('Instrumentation changed the prior wallet result')
    summary=mapped_summary(events)
    if summary['original_opportunities']!=57:
        raise ValueError('Original opportunity cohort differs')
    by_id={e['id']:e for e in events}
    duplicates=[]
    for e in events:
        if e['baseline_eligible'] and e['status']=='DUPLICATA':
            parent=by_id[e['duplicate_of']]
            duplicates.append({'candidate':e,'previous':parent,'same_band':e['band']==parent['band']})
    report={'kind':'UNCHANGED_PORTFOLIO_TRACE','validation':'Identical wallet result with and without instrumentation; identical to previous artifact.',
        'summary':summary,'wallet':result,'original_57':[e for e in events if e['baseline_eligible']],
        'duplicate_details':duplicates,
        'limits':['No strategy, risk or position-count changes. Same frozen data and chronological wallet.',
                  'Original outcome labels are used only for retrospective mapping, never for selecting entries.',
                  'Risk/price/cost blocks must be distinguished from the single-position restriction.']}
    output=Path('reports/portfolio-trace')
    output.mkdir(parents=True,exist_ok=True)
    (output/'result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    (output/'all-decisions.json.gz').write_bytes(gzip.compress(json.dumps(events).encode(),mtime=0))
    print('TRACE_BEGIN')
    print(json.dumps(report,ensure_ascii=False,indent=2))
    print('TRACE_END')


if __name__=='__main__':
    run()
