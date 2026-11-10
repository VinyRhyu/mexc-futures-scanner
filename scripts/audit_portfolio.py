"""Chronological single-position paper wallet on frozen historical signals."""
import argparse
from collections import Counter
from dataclasses import replace
from datetime import datetime
import gzip
import json
import os
from pathlib import Path

from mexc_scanner.config import Config
from mexc_scanner.models import D, jsonable
from scripts.audit_pullback import close_outcome, iso, paper_quote
from scripts.audit_sustained_trigger import MODE, read_dataset, restore_plan, restore_variant


def time_exit(price,entry,quantity,tick,cfg,side):
    sign=1 if side=='LONG' else -1
    fill=entry*(1+sign*D('.0001'))
    return quantity*(sign*(price-fill)-max(2*tick,fill*D(cfg.slippage_rate))
                     -max(2*tick,price*D(cfg.slippage_rate))-D(cfg.taker_fee)*(fill+price))


def simulate(rows,datasets,cfg,initial=D(50),decisions=None):
    balance,peak,drawdown,available=initial,initial,D(0),0
    trades,skips,seen=[],Counter(),set()
    first_seen={}
    candidates=sorted((r for r in rows if 'signal' in r[MODE]),
                      key=lambda r:(r[MODE]['signal'],r['symbol'],r['id']))
    for row in candidates:
        signal=int(row[MODE]['signal'])
        key=(row['symbol'],row['side'],signal,row['M1']['stop'],row['M1']['target'])
        event={'id':row['id'],'symbol':row['symbol'],'side':row['side'],'signal':signal,
               'baseline_eligible':'entered_at' in row[MODE],
               'baseline_outcome':row[MODE].get('outcome'),
               'baseline_net_r':row[MODE].get('net_r'),
               'band':[row['M1']['entry_low'],row['M1']['entry_high']],
               'stop':row['M1']['stop'],'target':row['M1']['target']}
        def emit(status,**extra):
            event.update(status=status,**jsonable(extra))
            if decisions is not None:
                decisions.append(event)
        if key in seen:
            skips['DUPLICATA']+=1
            emit('DUPLICATA',duplicate_of=first_seen[key])
            continue
        seen.add(key)
        first_seen[key]=row['id']
        if signal<available:
            skips['POSICAO_EM_ABERTO']+=1
            emit('POSICAO_EM_ABERTO',occupied_by=trades[-1]['symbol'],
                 occupied_until=iso(available),last_settled_balance=trades[-1]['balance_before'])
            continue
        if balance<=0:
            skips['SEM_SALDO']+=1
            emit('SEM_SALDO',balance=balance)
            continue
        data=datasets[row['symbol']]
        m=data['minute_map']
        bars=[m[t] for t in range(signal,signal+14400,60)]
        p,v=restore_plan(row),restore_variant(row['M1'])
        p.status,p.expires_at='ATIVO',int(row['M1']['signal'])+1800
        current=replace(cfg,initial_balance=str(balance))
        quote=paper_quote(p,v,data['contract'],bars[0].open,signal+1,current)
        if quote['status']!='VIAVEL_SIMULADO':
            skips.update(quote['reasons'])
            emit('BLOQUEADA_FINANCEIRO',balance=balance,reasons=quote['reasons'])
            continue
        result=close_outcome(bars,p,v,data['contract'],quote,bars[0].open,current,True)
        if result['outcome']=='ABERTO':
            result={'outcome':'ENCERRAMENTO_4H','exited_at':iso(bars[-1].end),
                    'net_usdt':time_exit(bars[-1].close,bars[0].open,D(quote['base_quantity']),
                                         data['contract'].tick,current,p.side)}
        pnl=D(result['net_usdt'])
        before=balance
        balance+=pnl
        peak=max(peak,balance)
        drawdown=max(drawdown,(peak-balance)/peak)
        available=int(datetime.fromisoformat(result['exited_at']).timestamp())
        trades.append(jsonable(dict(symbol=p.symbol,side=p.side,entered_at=iso(signal),
            balance_before=before,balance_after=balance,planned_risk=quote['loss_usdt'],
            contracts=quote['contracts'],leverage=quote['leverage'],margin=quote['margin_usdt'],
            target=v.target,stop=v.stop,**result)))
        emit('EXECUTADA',balance_before=before,balance_after=balance,
             outcome=result['outcome'],net_usdt=pnl)
    return jsonable({'initial_balance':initial,'final_balance':balance,'net_usdt':balance-initial,
        'return_percent':(balance/initial-1)*100,'trades':trades,'entries':len(trades),
        'wins':sum(D(t['net_usdt'])>0 for t in trades),'losses':sum(D(t['net_usdt'])<0 for t in trades),
        'outcomes':dict(Counter(t['outcome'] for t in trades)),
        'gains_usdt':sum((D(t['net_usdt']) for t in trades if D(t['net_usdt'])>0),D(0)),
        'losses_usdt':-sum((D(t['net_usdt']) for t in trades if D(t['net_usdt'])<0),D(0)),
        'maximum_realized_drawdown_percent':drawdown*100,'skips':dict(skips)})


def run(source,sustained,output):
    prior=json.loads((source/'summary.json').read_text())
    cfg=Config(**prior['config']).validate()
    test=json.loads((sustained/'summary.json').read_text())
    if cfg.mode!='paper' or cfg.fingerprint!=test['config_fingerprint']:
        raise ValueError('Frozen configuration mismatch')
    rows=json.loads(gzip.decompress((sustained/'all-formations.json.gz').read_bytes()))
    if len(rows)!=test['formations']:
        raise ValueError('Incomplete frozen cohort')
    datasets={}
    for manifest in prior['datasets']:
        d=read_dataset(source,manifest)
        d['minute_map']={c.ts:c for c in d.pop('minute')}
        datasets[manifest['symbol']]=d
    result=simulate(rows,datasets,cfg)
    result.update(kind='CHRONOLOGICAL_SINGLE_POSITION_WALLET',source_runs=[42879077420,42890505005],
        period=[test['start_brt'],test['end_exclusive_brt']],code_sha=os.environ.get('GITHUB_SHA'),
        limitations=[
            'Uma posição por vez; ordem cronológica. Empates resolvidos por símbolo e ID, sem usar resultados futuros.',
            'Risco até10% do saldo atualizado, sem aportes; lotes, margem, alavancagem até20x e custos recalculados para cada entrada.',
            'Inclui confirmações antes bloqueadas financeiramente com1USDT: reavalia todas com o saldo disponível.',
            'TP/SL/faixa congelados no primeiro gatilho. Entrada após segundo fechamento M1; nenhuma regra nova de sinal.',
            'Posições ainda abertas após4h são encerradas no último fechamento conhecido, com custos de saída.',
            'Drawdown mede saldos realizados; não inclui oscilação intraposição ou margem de manutenção em tempo real.',
            'Mesmo histórico usado para escolher a regra: análise exploratória sem validação fora da amostra.',
            'Funding zero, livro infinito e fills hipotéticos; taxas0,06% por lado, spread0,02%, slippage configurado ou2ticks.',
            'Contratos e universo congelados da coleta; preço LAST não reproduz necessariamente gatilho FAIR. Monitoramento M1 e latência idealizados.'
        ])
    output.mkdir(parents=True,exist_ok=True)
    (output/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--source',default='reports/early-trigger-source')
    p.add_argument('--sustained',default='reports/sustained-source')
    p.add_argument('--output',default='reports/portfolio-history')
    a=p.parse_args()
    r=run(Path(a.source),Path(a.sustained),Path(a.output))
    print('PORTFOLIO_BEGIN')
    print(json.dumps(r,ensure_ascii=False,indent=2))
    print('PORTFOLIO_END')
    if path:=os.environ.get('GITHUB_STEP_SUMMARY'):
        Path(path).write_text('## Carteira cronológica US$50\n\n```json\n'+json.dumps(r,ensure_ascii=False,indent=2)+'\n```')
