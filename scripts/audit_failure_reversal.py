"""One pre-specified first-failed-break reversal; research only, no live calls."""
import argparse
from collections import Counter
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path

from mexc_scanner.config import load_config
from mexc_scanner.models import D, Plan, Variant, ceil_step, floor_step, jsonable, stable_id
from scripts.audit_wallet_entry import build_inputs, fixed_fill_stress, levels_touched, run_wallet, ts


def first_failure(original, minutes):
    plan=original['plan'];sign=1 if original['side']=='LONG' else -1
    signal=original['signal'];tick=original['contract'].tick
    for at in range(signal,signal+5*60,60):
        bar=minutes[at]
        if any(levels_touched(bar,original['side'],original['stop'],original['target'])):
            return None,'ORIGINAL_SL_TP_ANTES_DA_FALHA'
        if sign*(bar.close-plan.level)>=0:
            continue
        known=[minutes[t] for t in range(signal-120,bar.end,60)]
        reverse='SHORT' if sign==1 else 'LONG'
        midpoint=(plan.upper+plan.lower)/2
        if (bar.low<=midpoint if reverse=='SHORT' else bar.high>=midpoint):
            return None,'MEIO_DA_FAIXA_JA_TOCADO'
        if reverse=='SHORT':
            stop=ceil_step(max(c.high for c in known)+D('.10')*plan.atr,tick)
            target=ceil_step(midpoint,tick)
            low=ceil_step(max(midpoint+tick,bar.close-D('.25')*plan.atr),tick)
            high=floor_step(min(plan.upper-tick,bar.close+D('.25')*plan.atr),tick)
        else:
            stop=floor_step(min(c.low for c in known)-D('.10')*plan.atr,tick)
            target=floor_step(midpoint,tick)
            low=ceil_step(max(plan.lower+tick,bar.close-D('.25')*plan.atr),tick)
            high=floor_step(min(midpoint-tick,bar.close+D('.25')*plan.atr),tick)
        if low>high:return None,'FAIXA_REVERSAO_VAZIA'
        pid=stable_id('FIRST_FAILED_BREAK_REVERSAL_V1',original['id'],bar.end)
        reverse_plan=Plan(id=pid,symbol=plan.symbol,strategy='FIRST_FAILED_BREAK_REVERSAL_V1',side=reverse,
            formed_at=bar.end,detected_at=bar.end,expires_at=bar.end+120,atr=plan.atr,level=plan.level,
            lower=plan.lower,upper=plan.upper,stop=stop,family=pid,status='ATIVO',last_bar=bar.end,
            reaction_at=bar.end,entry_started_at=bar.end,revision=1,reason='PRIMEIRO_FECHAMENTO_DENTRO_DA_FAIXA')
        variant=Variant('CONFIRMADA',bar.end,bar.close,low,high,stop,target,'MEIO_DA_FAIXA_ORIGINAL')
        reverse_plan.variants={'CONFIRMADA':variant}
        return dict(id=pid,symbol=plan.symbol,side=reverse,signal=bar.end,stop=stop,target=target,
            plan=reverse_plan,variant=variant,contract=original['contract'],original_id=original['id'],
            original_signal=signal,failure_bar=bar.ts),None
    return None,'NAO_RETORNOU_PARA_FAIXA_EM_5M'


def reverse_signals(originals,histories):
    generated=[];reasons=Counter();checks=0
    for original in originals:
        minutes=histories[original['symbol']]['minute']
        reverse,reason=first_failure(original,minutes)
        if reverse is None:
            reasons[reason]+=1;continue
        truncated={t:c for t,c in minutes.items() if c.end<=reverse['signal']}
        causal,_=first_failure(original,truncated)
        assert jsonable(reverse)==jsonable(causal),'Future data changed the reversal signal'
        checks+=1;generated.append(reverse)
    unique={(r['symbol'],r['side'],r['signal'],r['stop'],r['target']):r for r in generated}
    return list(unique.values()),dict(generated=len(generated),unique=len(unique),causal_prefix_checks=checks,reasons=dict(reasons))


def run(sources,valuation,protocol,amendment,parent_results):
    p=json.loads(Path(protocol).read_text());a=json.loads(Path(amendment).read_text())
    original,histories,compat,vm=build_inputs(sources,valuation,p)
    reversals,diagnostic=reverse_signals(original,histories)
    cfg=replace(load_config('config/default.toml'),initial_balance=p['capital'],minimum_leverage=10,max_leverage=10,
        risk_fraction=p['risk_fraction'],max_cost_fraction=a['max_cost_fraction']).validate()
    parent=json.loads(Path(parent_results).read_text())
    assert hashlib.sha256(Path(parent_results).read_bytes()).hexdigest()==p['parent_result_sha256']
    result=dict(protocol=p,amendment=a,compatibility=compat,valuation_manifest=vm,
        protocol_sha256=hashlib.sha256(Path(protocol).read_bytes()).hexdigest(),diagnostic=diagnostic,
        weekly={},continuous={},production_changed=False)
    for label,start,end in [('continuous',p['start_brt'],p['end_exclusive_brt'])]+[(str(i+1),w[0],w[1]) for i,w in enumerate(p['weeks'])]:
        control=run_wallet(original,histories,ts(start),ts(end),'MARKET',p,cfg)
        expected=parent['continuous']['MARKET'] if label=='continuous' else parent['weekly'][label]['MARKET']
        assert jsonable(control)=={k:v for k,v in expected.items() if k!='fixed_fill_stress'},'Control differs from parent experiment'
        candidate=run_wallet(reversals,histories,ts(start),ts(end),'MARKET',p,cfg)
        candidate['fixed_fill_stress']=fixed_fill_stress(candidate,p)
        arms=dict(CONTROL=expected,REVERSAL=candidate)
        if label=='continuous':result['continuous']=arms
        else:result['weekly'][label]=arms
        print(json.dumps(jsonable(dict(stage='reversal',period=label,positions=candidate['positions'],
            final=candidate['final'],return_pct=candidate['return_pct'],outcomes=candidate['outcomes']))),flush=True)
    candidate=result['continuous']['REVERSAL'];latest=result['weekly']['3']['REVERSAL']
    screen=(candidate['final']>max(D(p['capital']),D(result['continuous']['CONTROL']['final']))
        and candidate['max_drawdown_pct']<=10 and candidate['positions']>=30 and latest['positions']>=15
        and latest['final']>D(p['capital']) and all(w['REVERSAL']['final']>=D(p['capital']) for w in result['weekly'].values())
        and candidate['fixed_fill_stress']['final']>D(p['capital']) and candidate['fixed_fill_stress']['fixed_size_margin_violations']==0)
    result.update(exploratory_screen_passed=screen,independent_validation=False,approved_for_production=False)
    return jsonable(result)


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--source',action='append',required=True)
    for key in ('valuation','protocol','amendment','parent-results','output'):ap.add_argument('--'+key,required=True)
    a=ap.parse_args();result=run(a.source,a.valuation,a.protocol,a.amendment,a.parent_results)
    Path(a.output).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('diagnostic','exploratory_screen_passed','approved_for_production')},indent=2))
