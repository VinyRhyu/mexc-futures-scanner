"""Causal M1 breakout with frozen first-trigger levels and volume retention."""
from copy import deepcopy
from .market import atr
from .models import D,Plan,ceil_step,floor_step,stable_id
from .strategies import make_variant

MODEL='m1_volume50_v1'
STRATEGY='ROMPIMENTO_M1_VOLUME'
MAX_SIGNAL_AGE=120

def validate_minute_ohlc(quarter,minute):
    groups={}
    for c in minute:groups.setdefault((c.ts//900)*900,[]).append(c)
    for q in quarter:
        bars=groups.get(q.ts,[])
        if len(bars)==15:
            values=(bars[0].open,max(c.high for c in bars),min(c.low for c in bars),bars[-1].close)
            if values!=(q.open,q.high,q.low,q.close):
                raise ValueError('OHLC M1 diverge do M15')


def prepare_model(state,model,now):
    if state.get('active_signal_model')==model:
        return
    # Existing ledger/position/balance are deliberately retained.
    for p in state['plans'].values():
        if p['status'] not in {'EXPIRADO','INVALIDADO','AMBIGUO','EVENTO_PASSADO'}:
            p['status'],p['reason']='EXPIRADO','MODELO_SUBSTITUIDO'
            for v in p.get('variants',{}).values():
                v['status']='ENCERRADA'
                v['financial']={'status':'BLOQUEADA','reasons':['MODELO_SUBSTITUIDO']}
    for message in state['outbox'].values():
        if message['category']=='ENTRY' and message['status']=='PENDING':
            message['status']='EXPIRED'
    state['active_signal_model']=model
    state['model_activated_at']=now
    state['minute_cursors']={}
    state['minute_activation']={}


def form_plans(symbol,quarter,tick,not_before,minute_start):
    result=[]
    for i in range(478,len(quarter)):
        at=quarter[i].end
        if at<max(not_before,minute_start):continue
        known=quarter[i-478:i+1]
        a=atr(known,14)[-1]
        box=known[-8:]
        lo,hi=min(c.low for c in box),max(c.high for c in box)
        if not a or not a<=hi-lo<=4*a:continue
        if sum(c.high>=hi-D('.25')*a for c in box)<2 or sum(c.low<=lo+D('.25')*a for c in box)<2:continue
        for side,sign in [('LONG',1),('SHORT',-1)]:
            level=hi if sign==1 else lo
            stop=level-sign*D('.5')*a
            stop=floor_step(stop,tick) if sign==1 else ceil_step(stop,tick)
            pid=stable_id(MODEL,symbol,side,at,lo,hi)
            result.append(Plan(pid,symbol,STRATEGY,side,at,at,at+1800,a,level,lo,hi,stop,pid))
    return result


def end_plan(p,status,reason):
    p.status,p.reason=status,reason
    for v in p.variants.values():v.status='ENCERRADA'


def process_minutes(symbol,quarter,hourly,minute,plans,cursor,now,tick,config,not_before):
    if not minute:raise ValueError('Histórico M1 ausente')
    if any(a.end!=b.ts for a,b in zip(minute,minute[1:])):
        raise ValueError('Lacuna no histórico M1')
    if any(c.end+10>now for c in minute):
        raise ValueError('Candle M1 ainda não fechado')
    diagnostics=[]
    if cursor and cursor<minute[0].ts:
        for p in plans:
            if p.strategy==STRATEGY and not p.terminal:
                end_plan(p,'EXPIRADO','LACUNA_M1')
        not_before=now
        diagnostics.append('LACUNA_M1_REINICIO_APENAS_FUTURO')
    ids={p.id for p in plans}
    for p in form_plans(symbol,quarter,tick,not_before,minute[0].ts):
        if p.id not in ids:
            plans.append(p);ids.add(p.id)
    mm={c.ts:c for c in minute}
    for p in plans:
        if p.strategy!=STRATEGY or p.terminal:continue
        sign=1 if p.side=='LONG' else -1
        threshold=p.level+sign*D('.10')*p.atr
        begin=max(0,(max(p.formed_at,p.last_bar)-minute[0].ts)//60)
        end=min(len(minute),(p.formed_at+3600-minute[0].ts)//60+1)
        for c in minute[begin:end]:
            if c.ts<p.formed_at or c.end<=p.last_bar:continue
            if c.end>p.expires_at:
                end_plan(p,'EXPIRADO','PRAZO_ENCERRADO');break
            p.last_bar=c.end
            first=p.variants.get('ANTECIPADA')
            confirmed=p.variants.get('CONFIRMADA')
            if first:
                bad=c.low<=first.stop if sign==1 else c.high>=first.stop
                good=c.high>=first.target if sign==1 else c.low<=first.target
                if bad or good:
                    end_plan(p,'AMBIGUO' if bad and good else 'INVALIDADO' if bad else 'EVENTO_PASSADO',
                             'STOP_E_ALVO_NO_MESMO_CANDLE' if bad and good else 'STOP_ANTES_DA_ENTRADA' if bad else 'ALVO_JA_ATINGIDO')
                    break
            if confirmed:
                continue
            if first is None:
                if sign*(c.close-threshold)>0:
                    h=[x for x in hourly if x.end<=c.end][-240:]
                    if len(h)!=240:raise ValueError('Histórico H1 fechado insuficiente')
                    v=make_variant(p,'ANTECIPADA',c,h,tick)
                    v.status='AGUARDANDO_CONFIRMACAO'
                    p.variants['ANTECIPADA']=v
                    p.reaction_at,p.entry_started_at=c.end,c.end
                    p.expires_at=c.end+1800
                continue
            if c.ts!=p.reaction_at:
                end_plan(p,'EXPIRADO','SEGUNDO_M1_INDISPONIVEL');break
            trigger=mm.get(p.reaction_at-60)
            if trigger is None:
                end_plan(p,'EXPIRADO','SEGUNDO_M1_INDISPONIVEL');break
            if sign*(c.close-threshold)<=0:
                end_plan(p,'INVALIDADO','SEGUNDO_M1_NAO_SUSTENTOU');break
            if trigger.volume<=0 or 2*c.volume<trigger.volume:
                end_plan(p,'INVALIDADO','VOLUME_M1_INSUFICIENTE');break
            v=deepcopy(first)
            v.kind,v.triggered_at,v.status='CONFIRMADA',c.end,'VALIDA'
            first.status='ENCERRADA'
            p.variants['CONFIRMADA']=v
            p.expires_at=min(p.reaction_at+1800,c.end+MAX_SIGNAL_AGE)
            p.status,p.revision='ATIVO',1
            p.observations.append('VOLUME_M1_PERCENT='+str(c.volume/trigger.volume*100))
            if now-c.end>MAX_SIGNAL_AGE:
                end_plan(p,'EVENTO_PASSADO','GATILHO_M1_ATRASADO');break
        if not p.terminal and now>=p.expires_at:
            end_plan(p,'EXPIRADO','PRAZO_ENCERRADO')
    return plans,minute[-1].end,diagnostics
