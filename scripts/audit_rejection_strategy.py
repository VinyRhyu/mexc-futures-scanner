"""Hipótese fixa de recuperação frustrada, isolada da produção."""
from __future__ import annotations

from collections import Counter
from dataclasses import replace
import json
import os
from pathlib import Path

from mexc_scanner.config import load_config
from mexc_scanner.market import atr, parse_candles, select_universe, structure
from mexc_scanner.mexc import MexcClient
from mexc_scanner.models import Contract, D, Plan, Variant, ceil_step, floor_step, jsonable, stable_id
from scripts.audit_historical_trend import midnight
from scripts.audit_pullback import close_outcome, iso, paper_quote


def ema20(q):
    value, result = q[0].close, []
    for c in q:
        value = (D(2) * c.close + D(19) * value) / 21
        result.append(value)
    return result


def setups(symbol, q, h, start, end):
    a, ema, seen, out = atr(q, 14), ema20(q), set(), []
    for i in range(480, len(q)):
        c, prev = q[i], q[i-1]
        if not start <= c.end < end:
            continue
        volatility = a[i-1]
        known_h = [x for x in h if x.end <= c.end][-240:]
        direction = structure(known_h, c.end)
        for side, sign, expected in [('SHORT', -1, 'BAIXA'), ('LONG', 1, 'ALTA')]:
            if direction != expected or sign * (ema[i] - ema[i-1]) <= 0:
                continue
            rejected = (c.high > prev.high and c.close < c.open and c.close < ema[i] if sign == -1 else
                        c.low < prev.low and c.close > c.open and c.close > ema[i])
            if not rejected:
                continue
            impulse = None
            for j in range(i-8, i):
                level = min(x.low for x in q[j-4:j]) if sign == -1 else max(x.high for x in q[j-4:j])
                if sign * (q[j].close - level) > D('0.10') * a[j-1]:
                    impulse = j
            if impulse is None or (side, q[impulse].end) in seen:
                continue
            extreme = min(x.low for x in q[impulse:i]) if sign == -1 else max(x.high for x in q[impulse:i])
            recovery = c.high - extreme if sign == -1 else extreme - c.low
            if recovery < D('0.5') * volatility:
                continue
            local = min(x.low for x in q[i-4:i]) if sign == -1 else max(x.high for x in q[i-4:i])
            broad = min(x.low for x in q[i-8:i]) if sign == -1 else max(x.high for x in q[i-8:i])
            stop = c.high + D('0.10') * volatility if sign == -1 else c.low - D('0.10') * volatility
            seen.add((side, q[impulse].end))
            out.append({'symbol': symbol, 'side': side, 'signal': c.end, 'atr': volatility,
                        'reference': c.close, 'stop': stop, 'level': local, 'levels': sorted(set([local, broad])),
                        'impulse_at': q[impulse].end})
    return out


def make_plan(s, kind, signal, reference, stop, tick):
    sign = 1 if s['side'] == 'LONG' else -1
    levels = [x for x in s['levels'] if sign * (x-reference) > D('0.10') * s['atr']]
    if not levels:
        return None
    level = min(levels) if sign == 1 else max(levels)
    target = level - sign * D('0.10') * s['atr']
    target = floor_step(target, tick) if sign == 1 else ceil_step(target, tick)
    stop = floor_step(stop, tick) if sign == 1 else ceil_step(stop, tick)
    low, high = ceil_step(reference-D('0.25')*s['atr'],tick), floor_step(reference+D('0.25')*s['atr'],tick)
    pid = stable_id(s['symbol'], s['signal'], kind)
    p = Plan(pid,s['symbol'],'REJEICAO_EXPERIMENTAL',s['side'],s['signal'],s['signal'],signal+1800,
             s['atr'],s['level'],low,high,stop,pid,status='ATIVO')
    v = Variant(kind,signal,reference,low,high,stop,target,'NIVEL_LOCAL_CONHECIDO')
    return p,v


def simulate(s, kind, signal, reference, stop, m, contract, cfg):
    pair = make_plan(s,kind,signal,reference,stop,contract.tick)
    if pair is None:
        return {'outcome':'SEM_ALVO_ESTRUTURAL'}
    p,v = pair
    bars = [c for c in m if signal <= c.ts < signal+14400]
    if (not bars or bars[0].ts != signal or bars[-1].end != signal+14400
            or any(a.end != b.ts for a,b in zip(bars,bars[1:]))):
        return {'outcome':'SEM_DADOS'}
    f = paper_quote(p,v,contract,bars[0].open,signal+1,cfg)
    base = {'stop':v.stop,'target':v.target,'entry_low':v.entry_low,'entry_high':v.entry_high}
    if f['status']!='VIAVEL_SIMULADO':
        return jsonable(dict(base,outcome='BLOQUEADA',reasons=f['reasons']))
    r=close_outcome(bars,p,v,contract,f,bars[0].open,cfg,True)
    r.update(base,entered_at=iso(signal),entry_mid=bars[0].open,net_rr=f['net_rr'])
    return jsonable(r)


def evaluate_setup(s,m,h,contract,cfg):
    early=simulate(s,'ANTECIPADA',s['signal'],s['reference'],s['stop'],m,contract,cfg)
    confirmed={'outcome':'SEM_CONFIRMACAO_EM_1H'}
    sign=1 if s['side']=='LONG' else -1
    wait=[c for c in m if s['signal']<=c.ts<s['signal']+3600]
    if (len(wait)!=60 or wait[0].ts!=s['signal'] or wait[-1].end!=s['signal']+3600
            or any(a.end!=b.ts for a,b in zip(wait,wait[1:]))):
        return {'symbol':s['symbol'],'side':s['side'],'signal':iso(s['signal']),
                'setup':jsonable(s),'ANTECIPADA':early,'CONFIRMADA':{'outcome':'SEM_DADOS'}}
    for i,c in enumerate(wait):
        if (c.low<=s['stop'] if sign==1 else c.high>=s['stop']):
            confirmed={'outcome':'INVALIDADA_ANTES_DA_CONFIRMACAO'}
            break
        if sign*(c.close-s['level'])>D('0.10')*s['atr']:
            known_h=[x for x in h if x.end<=c.end][-240:]
            if structure(known_h,c.end)!=('ALTA' if sign==1 else 'BAIXA'):
                confirmed={'outcome':'ESTRUTURA_1H_MUDOU'}
                break
            recent=wait[max(0,i-2):i+1]
            stop=(min(x.low for x in recent)-D('0.10')*s['atr'] if sign==1 else
                  max(x.high for x in recent)+D('0.10')*s['atr'])
            confirmed=simulate(s,'CONFIRMADA',c.end,c.close,stop,m,contract,cfg)
            break
    return {'symbol':s['symbol'],'side':s['side'],'signal':iso(s['signal']),
            'setup':jsonable(s),'ANTECIPADA':early,'CONFIRMADA':confirmed}


def summary(rows):
    out={}
    for kind in ('ANTECIPADA','CONFIRMADA'):
        vals=[r[kind] for r in rows]
        entries=[v for v in vals if 'entered_at' in v]
        closed=[v for v in entries if 'net_r' in v]
        out[kind]={'setups':len(rows),'entries':len(entries),'targets':sum(v['outcome']=='ALVO' for v in closed),
            'stops':sum(v['outcome'] in {'STOP','STOP_AMBIGUO'} for v in closed),
            'ambiguous':sum(v['outcome']=='STOP_AMBIGUO' for v in closed),
            'open':sum(v['outcome']=='ABERTO' for v in entries),
            'closed_r_independent':str(sum((D(v['net_r']) for v in closed),D(0))),
            'outcomes':dict(Counter(v['outcome'] for v in vals)),
            'blocked':dict(Counter(t for v in vals for t in v.get('reasons',[])))}
    return out


def run():
    cfg=replace(load_config('config/default.toml'),mode='paper')
    client=MexcClient(cfg.api_base)
    start,end=midnight('2026-11-01'),midnight('2026-11-08')
    observed=end+18000
    catalog,tickers=client.contracts(),client.tickers()
    assets=set(json.loads(Path('config/crypto-assets.json').read_text())['assets'])
    selected,_=select_universe(catalog,tickers,assets,D(cfg.minimum_turnover),50)
    if not selected:
        raise ValueError('Universo vazio; teste não realizado')
    rows,errors=[],{}
    for num,raw in enumerate(selected,1):
        symbol=raw['symbol']
        try:
            contract=Contract.from_api(raw)
            qn,hn=480+(observed-start)//900,240+(observed-start)//3600
            q=parse_candles(client.candles(symbol,'Min15',qn,observed+10),900,observed+10,qn)
            h=parse_candles(client.candles(symbol,'Min60',hn,observed+10),3600,observed+10,hn)
            candidates=setups(symbol,q,h,start,end)
            m=[]
            if candidates:
                right=observed
                while right>start:
                    count=min(1800,(right-start)//60)
                    chunk=parse_candles(client.candles(symbol,'Min1',count,right+10),60,right+10,count)
                    m=chunk+m
                    right-=count*60
                if (m[0].ts!=start or m[-1].end!=observed
                        or any(a.end!=b.ts for a,b in zip(m,m[1:]))):
                    raise ValueError('Histórico de 1m com lacunas entre lotes')
                for c in q:
                    if start<=c.ts and c.end<=observed:
                        group=m[(c.ts-start)//60:(c.end-start)//60]
                        if (group[0].open,max(x.high for x in group),min(x.low for x in group),group[-1].close)!=(c.open,c.high,c.low,c.close):
                            raise ValueError('OHLC de 1m diverge da fonte de 15m')
            rows.extend(evaluate_setup(s,m,h,contract,cfg) for s in candidates)
            print(json.dumps({'progress':f'{num}/{len(selected)}','symbol':symbol,'setups':len(candidates)}),flush=True)
        except Exception as exc:
            errors[symbol]={'type':type(exc).__name__,'reason':str(exc)[:160]}
    limits=['Hipótese nova definida a partir do ETH de 10/11; avaliação em 1–7/11, período já usado para outras regras, portanto exploratória.',
        'Tendência 1h e EMA20 15m alinhadas; ruptura de mínima/máxima das quatro barras anteriores nos últimos oito candles; recuo >=0,5 ATR.',
        'Rejeição: máxima maior e fechamento abaixo da abertura/EMA20 para SHORT; espelhado para LONG. Uma rejeição por impulso.',
        'Antecipada entra após rejeição; SL no extremo da rejeição +/-0,10 ATR. Confirmação em 1m rompe nível local por 0,10 ATR em até 1h.',
        'SL da confirmada usa extremos das três barras 1m conhecidas, com buffer 0,10 ATR15m; nenhuma informação posterior escolhe níveis.',
        'Alvos: próximo extremo das janelas anteriores de 1h/2h, com buffer 0,10 ATR. Sem nível seguinte, não há entrada confirmada.',
        'Mesmo validador: RR líquido >=2, risco até10%, referência1USDT, teto20x, lote/margem; custos simulados de0,06% por lado +spread/slippage.',
        'Universo e regras de contratos atuais. Livro infinito e funding zero hipotéticos; somaR independente não representa carteira.',
        'Entrada na abertura do minuto seguinte; janela de4h por modalidade. Stops primeiro em ambiguidade. Abertas não são vitórias.']
    limits.append('Confirmação em 1m pressupõe monitoramento por minuto; a execução atual de 15m não garante a mesma entrada.')
    if len(errors)==len(selected):
        raise ValueError('Nenhum histórico completo analisado: '+json.dumps(errors))
    return jsonable({'kind':'REJECTION_STRATEGY_HISTORY','selected':len(selected),'analyzed':len(selected)-len(errors),
        'summary':summary(rows),'by_side':{side:summary([r for r in rows if r['side']==side]) for side in ('LONG','SHORT')},
        'errors':errors,'limitations':limits,'cases':rows})


if __name__=='__main__':
    r=run()
    print('REJECTION_RESULT_BEGIN')
    print(json.dumps(r,ensure_ascii=False,indent=2))
    print('REJECTION_RESULT_END')
    if path:=os.environ.get('GITHUB_STEP_SUMMARY'):
        lines=['## Rejeição da recuperação: histórico de1ºa7/11', '',
            '| Tipo | Setups | Entradas | Alvos | Stops | Abertas | R encerradas |','| --- | ---: | ---: | ---: | ---: | ---: | ---: |']
        for kind,v in r['summary'].items():
            lines.append(f"| {kind} | {v['setups']} | {v['entries']} | {v['targets']} | {v['stops']} | {v['open']} | {D(v['closed_r_independent']):.3f} |")
        lines+=['','### Regras e limites','']+['- '+x for x in r['limitations']]
        lines+=['','```json',json.dumps({'summary':r['summary'],'errors':r['errors']},ensure_ascii=False,indent=2),'```']
        Path(path).write_text('\n'.join(lines))
