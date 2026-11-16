"""Read captured operational evidence only; never invokes scanner, Telegram or Git."""
import argparse,hashlib,json
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path

from mexc_scanner.models import stable_id
from mexc_scanner.config import load_config


def stamp(value):
    return datetime.fromisoformat(value.replace('Z','+00:00')).timestamp()


def stats(values):
    v=sorted(values)
    if not v:return dict(n=0)
    def q(p):
        x=(len(v)-1)*p;i=int(x);j=min(i+1,len(v)-1)
        return v[i]+(v[j]-v[i])*(x-i)
    return dict(n=len(v),min=v[0],p50=q(.5),p95=q(.95),max=v[-1],mean=sum(v)/len(v))


def counter_dict(values):return dict(Counter(values))


def parse_json_log(line):
    index=line.find('{')
    return json.loads(line[index:]) if index>=0 else None


def run(directory,protocol):
    directory=Path(directory);p=json.loads(Path(protocol).read_text())
    state=json.loads((directory/'state.json').read_text())
    report=json.loads((directory/'latest-report.json').read_text())
    github=json.loads((directory/'github-metadata.json').read_text())
    config=load_config('config/default.toml')
    assert state['config_fingerprint']==config.fingerprint
    start,end=stamp(p['window_start_utc']),stamp(p['window_end_utc'])
    runs=github['runs'];assert len({r['id'] for r in runs})==len(runs)
    assert all(start<=stamp(r['created_at'])<end and r['head_sha']==p['main_commit'] for r in runs)
    successful=sorted([r for r in runs if r['conclusion']=='success'],key=lambda r:r['created_at'])
    intervals=[stamp(b['created_at'])-stamp(a['created_at']) for a,b in zip(successful,successful[1:])]
    timing=[]
    for row in github['jobs']:
        if row['run_conclusion']!='success':continue
        assert len(row['jobs'])==1
        job=row['jobs'][0];step=next(s for s in job['steps'] if s['name']=='Coletar, persistir e notificar')
        timing.append(dict(run_id=row['run_id'],job_id=job['id'],
            dispatch_to_job_s=stamp(job['started_at'])-stamp(row['run_created_at']),
            job_s=stamp(job['completed_at'])-stamp(job['started_at']),
            main_step_s=stamp(step['completed_at'])-stamp(step['started_at']),
            dispatch_to_main_step_s=stamp(step['started_at'])-stamp(row['run_created_at'])))
    canceled=[r for r in github['jobs'] if r['run_conclusion']=='cancelled']
    failures=[]
    for row in github['failure_samples']:
        events=[parse_json_log(x) for x in row['lines'] if x.find('{')>=0]
        scan=next((e for e in events if 'source_status' in e),None)
        notify=next((e for e in events if 'sent' in e),None)
        failures.append(dict(run_id=row['run_id'],job_id=row['job_id'],scan=scan,notify=notify))
    confirmed=[plan for plan in state['plans'].values() if plan['strategy']=='ROMPIMENTO_M1_VOLUME'
        and (v:=plan['variants'].get('CONFIRMADA')) and start<=v['triggered_at']<end]
    late=[plan for plan in confirmed if plan['reason']=='GATILHO_M1_ATRASADO']
    timely=[plan for plan in confirmed if plan['reason']!='GATILHO_M1_ATRASADO']
    finance=counter_dict(plan['variants']['CONFIRMADA']['financial'].get('status','UNEVALUATED') for plan in timely)
    block_reasons=counter_dict(reason for plan in timely for reason in plan['variants']['CONFIRMADA']['financial'].get('reasons',[]))
    cohort_entries=[]
    for plan in confirmed:
        v=plan['variants']['CONFIRMADA'];event=stable_id(plan['id'],'CONFIRMADA','GATILHO',state['mode'])
        m=state['outbox'].get(event)
        if not m:continue
        row=dict(symbol=plan['symbol'],side=plan['side'],status=m['status'],trigger_at=v['triggered_at'],
                 enqueued_at=m['created_at'],quote_at=m.get('quote_at'))
        if m['status']=='SENT':
            row.update(sent_at=m['sent_at'],signal_to_enqueue_s=m['created_at']-v['triggered_at'],
                signal_to_telegram_ack_s=m['sent_at']-v['triggered_at'],
                enqueue_to_ack_s=m['sent_at']-m['created_at'],quote_to_ack_s=m['sent_at']-m['quote_at'],
                remaining_validity_at_ack_s=m['expires_at']-m['sent_at'])
            assert row['remaining_validity_at_ack_s']>0
        cohort_entries.append(row)
    sent=[r for r in cohort_entries if r['status']=='SENT']
    messages=[m for m in state['outbox'].values() if start<=m['created_at']<end]
    status=counter_dict(m['category']+':'+m['status'] for m in messages)
    retry=[m for m in messages if m.get('last_error')]
    movement=[m for m in messages if m.get('movement_at') is not None and m['status']=='SENT']
    unbuffered=[]
    for row in github['phase_samples']:
        lines=row['lines'];stamps=[stamp(s.split(' ',1)[0]) for s in lines]
        span=max(stamps)-min(stamps) if stamps else None
        unbuffered.append(dict(run_id=row['run_id'],phase_lines=len(lines),log_timestamp_span_s=span,
                              phase_timing_reconstructible=False))
    return dict(protocol=p,provenance=dict(state_commit=p['state_commit'],main_commit=p['main_commit'],
            source_sha256={name:hashlib.sha256((directory/name).read_bytes()).hexdigest()
                for name in ('state.json','latest-report.json','github-metadata.json')},
            snapshot_last_success_utc=datetime.fromtimestamp(state['last_success'],timezone.utc).isoformat()),
        workflow=dict(runs=len(runs),outcomes=counter_dict(r['conclusion'] or r['status'] for r in runs),
            events=counter_dict(r['event'] for r in runs),
            cancellation_pct=sum(r['conclusion']=='cancelled' for r in runs)/len(runs)*100,
            success_pct=len(successful)/len(runs)*100,
            success_dispatch_spacing_s=stats(intervals),
            timing_sample={k:stats([x[k] for x in timing]) for k in
                ('dispatch_to_job_s','job_s','main_step_s','dispatch_to_main_step_s')},
            successful_sample_rows=timing,canceled_sample_n=len(canceled),
            canceled_sample_with_no_jobs=sum(not r['jobs'] for r in canceled),failures=failures,
            buffered_phase_samples=unbuffered),
        confirmed_cohort=dict(plans=len(confirmed),
            distinct_symbol_side_signal=len({(x['symbol'],x['side'],x['variants']['CONFIRMADA']['triggered_at']) for x in confirmed}),
            late_marked=len(late),late_pct=len(late)/len(confirmed)*100 if confirmed else None,
            nonlate=len(timely),last_financial_status_nonlate=finance,last_financial_block_reasons_nonlate=block_reasons,
            entry_event_status=counter_dict(r['status'] for r in cohort_entries),
            sent_entry_timing={k:stats([r[k] for r in sent]) for k in
                ('signal_to_enqueue_s','signal_to_telegram_ack_s','enqueue_to_ack_s','quote_to_ack_s','remaining_validity_at_ack_s')},
            sent_entry_rows=sent),
        messages_created_window=dict(count=len(messages),category_status=status,
            watch_stages=counter_dict(str(m.get('watch_stage'))+':'+m['status'] for m in messages if m.get('watch_symbol')),
            movement_to_ack_s=stats([m['sent_at']-m['movement_at'] for m in movement]),
            recovered_error_messages=sum(m['status']=='SENT' for m in retry),
            expired_error_messages=sum(m['status']=='EXPIRED' for m in retry),
            stored_error_types=counter_dict(m['last_error'] for m in retry)),
        latest_snapshot=dict(source_status=report['source_status'],selected=report['selected_symbols'],analyzed=report['analyzed_symbols'],
            diagnostic_count=len(report['diagnostics']),state_bytes=(directory/'state.json').stat().st_size,
            report_bytes=(directory/'latest-report.json').stat().st_size,total_state_plans=len(state['plans']),
            total_state_messages=len(state['outbox']),journal_entries=len(state['journal']),mode=state['mode']),
        cost_verification=dict(configured_taker_fee=config.taker_fee,fees_verified=config.fees_verified,
            account_rules_verified=config.account_rules_verified,fair_trigger_verified=config.fair_trigger_verified,
            realized_fee_events_recorded=sum('fees' in entry for entry in state['journal']),
            viable_fee_rates=sorted({str(plan['variants']['CONFIRMADA']['financial'].get('fee_rate'))
                for plan in timely if plan['variants']['CONFIRMADA']['financial'].get('status')=='VIAVEL_SIMULADO'}),
            note='Live evaluator consults currentfunding forplanning;historicalM1replay usedzero. No actualaccountfee confirmation orrealizedexecution ledger.'),
        limitations=['Snapshot values are retained latest decisions, not a per-event immutable evaluation ledger.',
            'Confirmation counts are by plan and may share market movement;not independent trades.',
            'TelegramSENT means API response received,not handset delivery/read or actual trade.',
            'Runcreation-to-job is dispatch/queue delay,not technicalsignal-to-analysis latency.',
            'No exact internal phase timing recoverable from buffered stdouttimestamps.',
            'Realaccountfees andrealexecutions not observed;no recordedjournal events in snapshot.',
            'Six-hour window and24job sample cannot establish all-day statistics or strategyprofitability.'],
        production_changed=False)


if __name__=='__main__':
    ap=argparse.ArgumentParser()
    for k in ('source','protocol','output'):ap.add_argument('--'+k,required=True)
    a=ap.parse_args();r=run(a.source,a.protocol)
    Path(a.output).write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n')
    compact=dict(r)
    compact['workflow']={k:v for k,v in r['workflow'].items() if k not in ('successful_sample_rows','failures','buffered_phase_samples')}
    compact['confirmed_cohort']={k:v for k,v in r['confirmed_cohort'].items() if k!='sent_entry_rows'}
    print(json.dumps(compact,ensure_ascii=False,indent=2))
