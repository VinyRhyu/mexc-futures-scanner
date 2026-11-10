"""Single fixed filter: second trigger minute volume >= half of first."""
import json
from pathlib import Path
from collections import Counter
from mexc_scanner.models import D,jsonable
from scripts.audit_sustained_trigger import read_dataset,metrics


def keep_volume(first,second):
    return first>0 and second>=0 and 2*second>=first


def summarize(rows):
    original=[r['baseline'] for r in rows]
    kept=[r['baseline'] for r in rows if r['accepted']]
    rejected=[r['baseline'] for r in rows if not r['accepted']]
    return {'baseline':metrics(original),'filtered':metrics(kept),
            'removed':dict(Counter(v['outcome'] for v in rejected)),
            'distinct_minutes_baseline':len({(r['symbol'],r['side'],r['signal']) for r in rows}),
            'distinct_minutes_filtered':len({(r['symbol'],r['side'],r['signal']) for r in rows if r['accepted']})}


def run():
    prior=json.loads(Path('reports/early-trigger-source/summary.json').read_text())
    volume=json.loads(Path('reports/trigger-volume-source/result.json').read_text())
    if volume['summary']['entries']!=57 or volume['summary']['valid_volume']!=57:
        raise ValueError('Original57volume cohort mismatch')
    records=[]
    for manifest in prior['datasets']:
        group=[r for r in volume['cases'] if r['symbol']==manifest['symbol']]
        if not group:
            continue
        d=read_dataset(Path('reports/early-trigger-source'),manifest)
        m={c.ts:c for c in d['minute']}
        for row in group:
            signal=int(row['signal'])
            first,second=m[signal-120],m[signal-60]
            if first.end!=second.ts or second.end!=signal or row['volume']['known_at']!=signal:
                raise ValueError('Trigger volume not known before entry')
            records.append(jsonable(dict(row,accepted=keep_volume(first.volume,second.volume),
                first_volume=first.volume,second_volume=second.volume,
                second_over_first=second.volume/first.volume if first.volume>0 else None)))
    if len(records)!=57 or len({r['id'] for r in records})!=57:
        raise ValueError('Incomplete or duplicated comparison cohort')
    result={'kind':'FIXED_HALF_VOLUME_RETENTION_FILTER','threshold':'second volume >= 50% first volume',
        'summary':summarize(records),
        'weekly':{w:summarize([r for r in records if r['week']==w]) for w in ('25–31/10','01–07/11')},
        'by_side':{s:summarize([r for r in records if r['side']==s]) for s in ('LONG','SHORT')},
        'cases':records,'limitations':[
            'Único filtro adicional: volume do segundo candle M1 pelo menos50% do primeiro. Igualdade aceita; primeiro volume zero rejeitado.',
            'Limite fixado antes desta execução, após diagnóstico anterior no mesmo histórico. Não houve busca de outros limites após o resultado.',
            'Volumes brutos reconstruídos da coleta original com checksum validado. Ambos já fechados antes da entrada.',
            'Mesma referência de57operações de25/10–07/11/2026, sem limitar posições simultâneas ou simular carteira.',
            'Preserva TP, SL, horário de entrada, quantidade e custos da referência. Não combina com proteção no zero nem filtro do terço.',
            'Acerto mede TP entre encerradas; abertas após4h excluídas da taxa e somaR. R não é dinheiro nem ROI de carteira.',
            'Sinais podem compartilhar moeda, minuto e movimento; a amostra não contém57eventos independentes.',
            'Análise no mesmo histórico já explorado, sem validação fora da amostra. Melhora retrospectiva não garante desempenho futuro.'
        ]}
    out=Path('reports/volume-retention');out.mkdir(parents=True,exist_ok=True)
    (out/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print('RETENTION_BEGIN');print(json.dumps(result,ensure_ascii=False,indent=2));print('RETENTION_END')

if __name__=='__main__':
    run()
