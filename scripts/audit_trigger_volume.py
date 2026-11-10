"""Descriptive, causal RVOL features; no threshold optimization or live edits."""
from collections import Counter,defaultdict
import gzip,json
from pathlib import Path
from statistics import median
from mexc_scanner.models import D,jsonable
from scripts.audit_sustained_trigger import MODE,read_dataset,entry_key,metrics


def features(first_signal,minutes):
    start=int(first_signal)-60
    timestamps=list(range(start-1200,start,60))+[start,start+60]
    if any(t not in minutes for t in timestamps):
        return {'status':'HISTORICO_1M_INSUFICIENTE'}
    prior=[minutes[t] for t in timestamps[:20]]
    a,b=minutes[start],minutes[start+60]
    if any(c.end>start for c in prior) or a.end!=int(first_signal) or b.end!=int(first_signal)+60:
        raise ValueError('Volume windows not aligned to closed trigger candles')
    mean=sum((c.volume for c in prior),D(0))/20
    if mean<=0:
        return {'status':'MEDIA_VOLUME_ZERO'}
    r=(a.volume+b.volume)/(2*mean)
    bucket='ABAIXO_1X' if r<1 else '1X_A_2X' if r<2 else '2X_OU_MAIS'
    return {'status':'OK','rvol_pair':r,'rvol_first':a.volume/mean,'rvol_second':b.volume/mean,
            'prior_mean':mean,'bucket':bucket,'known_at':b.end}


def distribution(values):
    values=sorted(values)
    if not values:
        return {'n':0}
    n=len(values)
    return {'n':n,'median':median(values),'mean':sum(values,D(0))/n,
            'min':values[0],'max':values[-1],
            'q1':median(values[:n//2]) if n>1 else values[0],
            'q3':median(values[(n+1)//2:]) if n>1 else values[0]}


def summarize(rows):
    valid=[r for r in rows if r['volume']['status']=='OK']
    return jsonable({'entries':len(rows),'valid_volume':len(valid),
        'distinct_symbol_side_minutes':len({(r['symbol'],r['side'],r['signal']) for r in rows}),
        'outcomes':dict(Counter(r['baseline']['outcome'] for r in rows)),
        'rvol_by_outcome':{o:{key:distribution([D(r['volume'][key]) for r in valid if r['baseline']['outcome']==o])
                             for key in ('rvol_pair','rvol_first','rvol_second')}
                           for o in ('ALVO','STOP','ABERTO')},
        'buckets':{b:metrics([r['baseline'] for r in valid if r['volume']['bucket']==b])
                   for b in ('ABAIXO_1X','1X_A_2X','2X_OU_MAIS')},
        'data_errors':dict(Counter(r['volume']['status'] for r in rows if r['volume']['status']!='OK'))})


def run():
    source=Path('reports/early-trigger-source')
    sustained=Path('reports/sustained-source')
    prior=json.loads((source/'summary.json').read_text())
    archive=json.loads(gzip.decompress((sustained/'all-formations.json.gz').read_bytes()))
    unique={entry_key(r,MODE):r for r in archive if 'entered_at' in r[MODE]}
    if len(unique)!=57:
        raise ValueError('Original57cohort differs')
    rows=[]
    for manifest in prior['datasets']:
        group=[r for r in unique.values() if r['symbol']==manifest['symbol']]
        if not group:
            continue
        data=read_dataset(source,manifest)
        minutes={c.ts:c for c in data['minute']}
        for r in group:
            v=features(r['M1']['signal'],minutes)
            if v['status']=='OK' and v['known_at']!=int(r[MODE]['signal']):
                raise ValueError('Volume information was not available at entry')
            rows.append(jsonable({'id':r['id'],'symbol':r['symbol'],'side':r['side'],'week':r['week'],
                                 'signal':r[MODE]['signal'],'baseline':r[MODE],'volume':v}))
    if len(rows)!=57:
        raise ValueError('Incomplete data mapping')
    result={'kind':'DESCRIPTIVE_TRIGGER_RVOL','summary':summarize(rows),
        'weekly':{w:summarize([r for r in rows if r['week']==w]) for w in ('25–31/10','01–07/11')},
        'by_side':{s:summarize([r for r in rows if r['side']==s]) for s in ('LONG','SHORT')},
        'cases':rows,'limitations':[
            'Métrica principal pré-definida: média do volume dos dois candles M1 de gatilho dividida pela média dos20minutos anteriores ao primeiro candle.',
            'Os dois volumes e a média histórica já são conhecidos antes da entrada. Não usa volume de candles posteriores nem o candle15m ainda aberto.',
            'Volumes são normalizados dentro de cada contrato. Dados OHLCV medem atividade, não agressão compradora/vendedora nem causa do movimento.',
            'Faixas fixadas antes do resultado: menor1x, de1x até menos2x e2xoumais. Não houve busca de melhor limiar ou alteração dos sinais.',
            'Grupo de57operações já explorado, incluindo sinais próximos e mesmo movimento de mercado. Associação retrospectiva não é previsão ou validação causal.',
            'Acerto considera apenas TP entre encerradas; abertas após4h ficam separadas. ResultadoR inclui os custos hipotéticos anteriores e não é carteira.',
            'Resumo por semana e direção mostra heterogeneidade; subgrupos pequenos não sustentam estimativa confiável de desempenho futuro.'
        ]}
    out=Path('reports/trigger-volume');out.mkdir(parents=True,exist_ok=True)
    (out/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print('VOLUME_BEGIN');print(json.dumps(result,ensure_ascii=False,indent=2));print('VOLUME_END')

if __name__=='__main__':
    run()
