"""Retrospective diagnosis and isolated counterfactuals, not a live strategy."""
from copy import deepcopy
from collections import Counter
import gzip,json,os
from pathlib import Path
from mexc_scanner.config import Config
from mexc_scanner.models import D,ceil_step,floor_step,jsonable
from scripts.audit_sustained_trigger import MODE,read_dataset,restore_plan,restore_variant,entry_key
from scripts.audit_pullback import paper_quote,iso


def net(price,mid,side,contract,cfg):
    sign=1 if side=='LONG' else -1
    entry=mid*(1+sign*D('.0001'))
    return (sign*(price-entry)-D(cfg.taker_fee)*(entry+price)
            -max(2*contract.tick,entry*D(cfg.slippage_rate))
            -max(2*contract.tick,price*D(cfg.slippage_rate)))

def level_for_profit(mid,wanted,side,contract,cfg):
    sign=1 if side=='LONG' else -1
    lo,hi=contract.tick,mid*10
    for _ in range(100):
        m=(lo+hi)/2
        if sign*(net(m,mid,side,contract,cfg)-wanted)<0:
            lo=m
        else:
            hi=m
    price=(lo+hi)/2
    return ceil_step(price,contract.tick) if sign==1 else floor_step(price,contract.tick)

def walk(bars,mid,side,v,contract,cfg,protect=False):
    sign=1 if side=='LONG' else -1
    risk=-net(v.stop,mid,side,contract,cfg)
    if risk<=0 or sign*(v.target-mid)<=0 or sign*(mid-v.stop)<=0:
        return {'outcome':'SEM_GEOMETRIA'}
    stop,armed=v.stop,False
    for c in bars:
        bad=c.low<=stop if sign==1 else c.high>=stop
        good=c.high>=v.target if sign==1 else c.low<=v.target
        if bad or good:
            price=(min(stop,c.open) if sign==1 else max(stop,c.open)) if bad else v.target
            return jsonable({'outcome':('PROTECAO' if armed else 'STOP') if bad else 'ALVO',
                'net_r':net(price,mid,side,contract,cfg)/risk,'exited_at':c.end,'ambiguous':bad and good})
        # A close at +1 net R arms protection only for the NEXT minute.
        if protect and not armed and net(c.close,mid,side,contract,cfg)>=risk:
            stop=level_for_profit(mid,D(0),side,contract,cfg)
            armed=True
    return {'outcome':'ABERTO'}

def financial(plan,v,mid,signal,contract,cfg):
    p=deepcopy(plan)
    p.status,p.stop,p.expires_at='ATIVO',v.stop,v.triggered_at+1800
    f=paper_quote(p,v,contract,mid,signal+1,cfg)
    return {'status':f['status'],'reasons':f.get('reasons',[]),'rr':f.get('net_rr')}

def analyze(row,data,cfg):
    p,v=restore_plan(row),restore_variant(row['M1'])
    original=row[MODE]
    signal=int(original['signal'])
    m=data['mm']
    bars=[m[t] for t in range(signal,signal+14400,60)]
    mid=bars[0].open
    sign=1 if p.side=='LONG' else -1
    risk=-net(v.stop,mid,p.side,data['contract'],cfg)
    base=walk(bars,mid,p.side,v,data['contract'],cfg)
    if base['outcome']!=original['outcome'] or ('net_r' in base and abs(D(base['net_r'])-D(original['net_r']))>D('1e-20')):
        raise ValueError('Original outcome reconstruction mismatch')
    diagnostic={}
    if original['outcome']=='STOP':
        exit_at=int(base['exited_at'])
        before=[c for c in bars if c.end<exit_at]
        later=[c for c in bars if c.ts>=exit_at]
        diagnostic={'minutes_to_stop':(exit_at-signal)//60,
            'best_close_r_before_stop':str(max([D(0)]+[net(c.close,mid,p.side,data['contract'],cfg)/risk for c in before])),
            'best_wick_r_before_stop':str(max([D(0)]+[net(c.high if sign==1 else c.low,mid,p.side,data['contract'],cfg)/risk for c in before])),
            'returned_inside_before_stop':any(sign*(c.close-p.level)<=0 for c in before),
            'original_tp_after_stop_within_4h':any(c.high>=v.target if sign==1 else c.low<=v.target for c in later)}
    variants={}
    for name,multiple in [('TP_1R',D(1)),('TP_1_5R',D('1.5'))]:
        trial=deepcopy(v)
        trial.target=level_for_profit(mid,multiple*risk,p.side,data['contract'],cfg)
        variants[name]={'path':walk(bars,mid,p.side,trial,data['contract'],cfg),
                        'finance':financial(p,trial,mid,signal,data['contract'],cfg),
                        'target_changed':True,'target':trial.target,'stop':trial.stop}
    known=[c for c in data['quarter'] if c.end<=signal][-8:]
    trial=deepcopy(v)
    structural=(min(c.low for c in known)-D('.1')*p.atr if sign==1 else max(c.high for c in known)+D('.1')*p.atr)
    trial.stop=(floor_step(min(v.stop,structural),data['contract'].tick) if sign==1 else
                ceil_step(max(v.stop,structural),data['contract'].tick))
    variants['SL_ESTRUTURAL']={'path':walk(bars,mid,p.side,trial,data['contract'],cfg),
        'finance':financial(p,trial,mid,signal,data['contract'],cfg),'target_changed':False,
        'stop':trial.stop,'target':trial.target}
    variants['PROTEGER_ZERO_APOS_1R']={'path':walk(bars,mid,p.side,v,data['contract'],cfg,True),
        'finance':financial(p,v,mid,signal,data['contract'],cfg),'target_changed':False}
    pull={'path':{'outcome':'SEM_RECUO'},'finance':{'status':'SEM_ENTRADA'}}
    for c in bars[:15]:
        bad=c.low<=v.stop if sign==1 else c.high>=v.stop
        good=c.high>=v.target if sign==1 else c.low<=v.target
        if bad or good:
            pull['path']={'outcome':'NIVEL_TOCADO_ANTES_ENTRADA'}
            break
        if sign*(mid-c.close)>=D('.25')*abs(mid-v.stop):
            price=m[c.end].open
            quoted=price*(1+sign*D('.0001'))
            if not v.entry_low<=quoted<=v.entry_high or sign*(mid-price)<D('.25')*abs(mid-v.stop):
                pull['path']={'outcome':'RECUO_FORA_FAIXA'}
            else:
                pull={'path':walk([x for x in bars if x.ts>=c.end],price,p.side,v,data['contract'],cfg),
                      'finance':financial(p,v,price,c.end,data['contract'],cfg),'target_changed':False,
                      'entry_at':c.end,'entry_mid':price}
            break
    variants['ENTRADA_RECUO_025R']=pull
    return jsonable({'id':row['id'],'symbol':row['symbol'],'side':p.side,'signal':signal,
        'baseline':base,'diagnostic':diagnostic,'variants':variants})

def summarize(cases):
    result=[]
    for name in cases[0]['variants']:
        vals=[r['variants'][name]['path'] for r in cases]
        admitted=[r for r in cases if r['variants'][name]['finance']['status']=='VIAVEL_SIMULADO']
        result.append({'variant':name,'target_changed':name.startswith('TP_'),
            'stops_to_target':sum(r['baseline']['outcome']=='STOP' and r['variants'][name]['path']['outcome']=='ALVO' for r in cases),
            'stops_to_target_financially_valid':sum(r['baseline']['outcome']=='STOP' and r['variants'][name]['path']['outcome']=='ALVO' for r in admitted),
            'original_targets_lost':sum(r['baseline']['outcome']=='ALVO' and r['variants'][name]['path']['outcome']!='ALVO' for r in cases),
            'outcomes':dict(Counter(v['outcome'] for v in vals)),
            'closed_net_r':str(sum((D(v.get('net_r',0)) for v in vals),D(0))),
            'financially_valid_entries':len(admitted),
            'admitted_closed_net_r':str(sum((D(r['variants'][name]['path'].get('net_r',0)) for r in admitted),D(0))),
            'blocks':dict(Counter(x for r in cases for x in r['variants'][name]['finance'].get('reasons',[])))})
    return sorted(result,key=lambda r:(-r['stops_to_target'],-D(r['closed_net_r'])))

def run():
    source=Path('reports/early-trigger-source')
    frozen=Path('reports/sustained-source')
    prior=json.loads((source/'summary.json').read_text())
    cfg=Config(**prior['config']).validate()
    rows=json.loads(gzip.decompress((frozen/'all-formations.json.gz').read_bytes()))
    unique={entry_key(r,MODE):r for r in rows if 'entered_at' in r[MODE]}
    cases=[]
    for manifest in prior['datasets']:
        selected=[r for r in unique.values() if r['symbol']==manifest['symbol']]
        if not selected:
            continue
        d=read_dataset(source,manifest)
        d['mm']={c.ts:c for c in d['minute']}
        cases.extend(analyze(r,d,cfg) for r in selected)
    stops=[r for r in cases if r['baseline']['outcome']=='STOP']
    if len(cases)!=57 or len(stops)!=33:
        raise ValueError('Original cohort mismatch')
    diag={'stops':len(stops),
        'stopped_within_5min':sum(r['diagnostic']['minutes_to_stop']<=5 for r in stops),
        'reached_05R_on_close_before_stop':sum(D(r['diagnostic']['best_close_r_before_stop'])>=D('.5') for r in stops),
        'reached_1R_on_close_before_stop':sum(D(r['diagnostic']['best_close_r_before_stop'])>=1 for r in stops),
        'returned_inside_before_stop':sum(r['diagnostic']['returned_inside_before_stop'] for r in stops),
        'tp_original_after_stop':sum(r['diagnostic']['original_tp_after_stop_within_4h'] for r in stops)}
    report={'kind':'STOP_PATH_DIAGNOSIS','diagnosis':diag,'ranking':summarize(cases),'cases':cases,
        'limitations':[
            'Contrafactuais retrospectivos independentes, não uma estratégia validada nem causas comprovadas dos movimentos.',
            'Todos os57sinais:33stops,18alvos,6abertas; não escolhe apenas as perdedoras para calcular o efeito dos ajustes.',
            'TP1R e1,5R mudam a definição de sucesso e não satisfazem o RR mínimo atual de2. Não são recuperação do TP original.',
            'SL estrutural usa oito candles15m fechados antes da entrada e buffer0,1ATR; volume hipotético reduzido para comparar em1R de risco.',
            'Recuo exige fechamento0,25da distância original ao SL melhor, em até15min, entrada seguinte dentro da faixa original; prazo final comum de4h.',
            'Proteção no zero líquido só ativa após fechamento conhecido em+1R, valendo a partir do minuto seguinte; não conta como TP.',
            'Stop primeiro em ambiguidade; MFE exclui minuto do stop por ordem intrabar desconhecida. Retomar alvo após stop não prova que bastava ampliar SL.',
            'Mesmo universo, custos e fills hipotéticos anteriores. Gate financeiro recalculado com referência1USDT. SomaR não é carteira.',
            'Hipóteses fixas para esta auditoria, sem ajustes após resultados; mesmo histórico já explorado, sem validação fora da amostra.'
        ]}
    out=Path('reports/stop-causes');out.mkdir(parents=True,exist_ok=True)
    (out/'result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print('CAUSES_BEGIN');print(json.dumps(report,ensure_ascii=False,indent=2));print('CAUSES_END')

if __name__=='__main__':
    run()
