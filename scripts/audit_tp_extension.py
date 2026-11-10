"""One TP-distance extension on the same 28 volume-qualified entries."""
from copy import deepcopy
from collections import Counter
import gzip,json
from pathlib import Path
from mexc_scanner.config import Config
from mexc_scanner.models import D,ceil_step,floor_step,jsonable
from scripts.audit_sustained_trigger import MODE,read_dataset,restore_plan,restore_variant,metrics
from scripts.audit_stop_causes import walk,financial


def extended_target(mid,target,side,tick):
    sign=1 if side=='LONG' else -1
    entry=mid*(1+sign*D('.0001'))
    if sign*(target-entry)<=0:
        raise ValueError('Original target behind entry')
    proposed=entry+D('1.25')*(target-entry)
    value=ceil_step(proposed,tick) if sign==1 else floor_step(proposed,tick)
    if value<=0:
        raise ValueError('Extended target not positive')
    return value


def summarize(rows):
    return {'baseline':metrics([r['baseline'] for r in rows]),
        'extended':metrics([r['extended'] for r in rows]),
        'original_targets_to_stop':sum(r['baseline']['outcome']=='ALVO' and r['extended']['outcome']=='STOP' for r in rows),
        'original_targets_to_open':sum(r['baseline']['outcome']=='ALVO' and r['extended']['outcome']=='ABERTO' for r in rows),
        'financial_gate_outcomes':dict(Counter(r['financial']['status'] for r in rows)),
        'financial_blocks':dict(Counter(x for r in rows for x in r['financial']['reasons']))}


def run():
    source=Path('reports/early-trigger-source')
    prior=json.loads((source/'summary.json').read_text())
    cfg=Config(**prior['config']).validate()
    retention=json.loads(Path('reports/retention-source/result.json').read_text())
    chosen={r['id'] for r in retention['cases'] if r['accepted']}
    original=json.loads(gzip.decompress(Path('reports/sustained-source/all-formations.json.gz').read_bytes()))
    cohort=[r for r in original if r['id'] in chosen]
    if len(cohort)!=28 or len(chosen)!=28:
        raise ValueError('Original28cohort mismatch')
    rows=[]
    for manifest in prior['datasets']:
        group=[r for r in cohort if r['symbol']==manifest['symbol']]
        if not group:continue
        d=read_dataset(source,manifest)
        m={c.ts:c for c in d['minute']}
        for row in group:
            p,v=restore_plan(row),restore_variant(row['M1'])
            base=row[MODE]
            signal=int(base['signal'])
            bars=[m[t] for t in range(signal,signal+14400,60)]
            mid=bars[0].open
            check=walk(bars,mid,p.side,v,d['contract'],cfg)
            if check['outcome']!=base['outcome'] or ('net_r' in check and abs(D(check['net_r'])-D(base['net_r']))>D('1e-20')):
                raise ValueError('Frozen outcome differs')
            new=deepcopy(v)
            new.target=extended_target(mid,v.target,p.side,d['contract'].tick)
            rows.append(jsonable({'id':row['id'],'symbol':row['symbol'],'side':row['side'],'week':row['week'],
                'signal':signal,'entry_mid':mid,'stop':v.stop,'old_target':v.target,'new_target':new.target,
                'baseline':base,'extended':walk(bars,mid,p.side,new,d['contract'],cfg),
                'financial':financial(p,new,mid,signal,d['contract'],cfg)}))
    if len(rows)!=28:raise ValueError('Incomplete comparison')
    result={'kind':'TP_DISTANCE_PLUS25','summary':summarize(rows),
        'weekly':{w:summarize([r for r in rows if r['week']==w]) for w in ('25–31/10','01–07/11')},
        'by_side':{s:summarize([r for r in rows if r['side']==s]) for s in ('LONG','SHORT')},
        'cases':rows,'limitations':[
            'Única mudança: distância da entrada ao TP multiplicada por1,25, com arredondamento para alvo pelo menos tão distante. Não aumenta preço nominal da moeda em25%.',
            'Entrada inclui spread hipotético original. TP novo definido no momento da entrada, sem candles futuros. SL, janela4h e seleção de28sinais permanecem iguais.',
            'Resultados emR usam mesmo risco ao SL e mesmos custos por operação. Custos de saída são calculados no novo preço-alvo. Sem proteção no zero.',
            'Gate financeiro do novo TP informado separadamente; o resumo principal preserva as28entradas para isolar o efeito do alvo, sem redimensionar a posição.',
            'Abertas4h não são vitórias nem entram na soma encerrada. Stops primeiro em ambiguidade. Fills/funding/livro mantêm hipóteses anteriores.',
            'Mesmo histórico já explorado, sem validação fora da amostra. Sinais sobrepostos: somaR não representa dinheiro ou ROI de uma carteira.',
            'Aumento fixado antes do teste; não houve busca de outros multiplicadores após resultados. Produção não alterada.'
        ]}
    out=Path('reports/tp-extension');out.mkdir(parents=True,exist_ok=True)
    (out/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print('TP_BEGIN');print(json.dumps(result,ensure_ascii=False,indent=2));print('TP_END')

if __name__=='__main__':run()
