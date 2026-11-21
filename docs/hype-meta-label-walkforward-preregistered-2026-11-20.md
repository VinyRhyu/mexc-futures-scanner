# HYPE — triagem de oportunidades por triple barrier + meta-labeling (pré-registro)

**Registro: 20/11/2026, antes de executar a nova experiência.**
**Pesquisa histórica read-only** sobre HYPE_USDT perpétuo MEXC, candles
fechados M5/H1. NENHUMA ordem, Telegram, produção, main ou merge.
Todos os períodos já foram estudados por outras abordagens, portanto
**NÃO** são holdout verdadeiramente intocado nem prova prospectiva.

Referências conceituais: MLfin.py Triple Barrier & Meta-labeling
https://mlfinpy.readthedocs.io/en/stable/Labelling.html e
scikit-learn TimeSeriesSplit com gap
https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html

A implementação usa Python stdlib para ser autocontida, mas **não
alega usar/corresponder integralmente ao pacote mlfinpy**; reproduz
somente rotulagem por primeira barreira e fluxo de validação causal.

## Regra WATCH original e rótulo

Reutilizar funções sem alterações de
`scripts/audit_hype_two_stage_1617.py`:
TURN (cruzamento M5 EMA9/21), BREAK (rompimento 6 M5), DRIFT
(EMA9/21 alinhada + 30min), volume/ATR originais, cooldown
30min por família/direção e 30min por direção na união;
prioridade TURN > BREAK > DRIFT.

Cada WATCH tem direção própria fixada naquele instante, nunca
inferida do preço futuro. LABEL exclusivamente ex post:
barreira superior direcional +1,25% do close WATCH, barreira
adversa −0,75%, tempo limite 18 M5 (90min);
primeira barreira acionada vence, empate intrabar = adversa,
sem barreira favorável = rótulo 0. Isso é uma classificação
WATCH, não TP/SL das entradas reais do replay. Registrar
tempo real em que a barreira ocorreu e excluir do treino
qualquer evento cujo tempo final ultrapasse o início da
janela de teste (embargo de 90min conservador).

## Períodos fixos

Reusar exatamente:
- T: 2026-06-05 11:00 UTC → 2026-07-17 11:00 UTC
- U: 2026-07-17 11:00 UTC → 2026-08-28 11:00 UTC
- V: 2026-08-28 11:00 UTC → 2026-10-09 11:00 UTC
- W0: 2026-10-09 11:00 UTC → 2026-11-16 03:00 UTC

Validação **expanding walk-forward**, sem embaralhar:
(1) treinar T e testar U; (2) treinar T+U e testar V;
(3) treinar T+U+V e testar W0. Purge adicional:
retirar treino os WATCH com watch_end+90min >= começo do teste,
mesmo se rótulo chegasse mais cedo. Apenas dados completos da
API pública MEXC; abortar ao faltar M5/H1 (não fabricar valores).

## Características predefinidas (só dados até WATCH)

- Retorno direcional M5 30min e 60min;
- M5 EMA9/EMA21 distância na direção do WATCH;
- Distância direcional close H1 último fechado vs EMA20 H1;
- Inclinação EMA20 H1 últimos 3 H1 fechados, direcional;
- ATR14 M5 como % do preço;
- log(1+volume cotado relativo últimas 12 M5);
- corpo M5 / ATR14 na direção;
- dist. relativa para máxima/mínima últimas 24 M5 / ATR14;
- flag direção alinhada H1; 3 flags família TURN/BREAK/DRIFT.

NÃO incluir preços futuros, estatísticas globais normalizadas com
testes, resultado do WATCH nem desfecho do trade como features.

## Seletores congelados

1. **BASE:** todos WATCHs com entrada M5 original elegível.
2. **H1_SIMPLE:** WATCHs a favor do último H1 fechado vs EMA20
   e volume relativo >=1,2x; aplicar às mesmas entradas originais.
3. **LOGIT_META_TOP20:** regressão logística L2 (regularização
   positiva e fixada), 140 épocas, learning rate 0,15,
   padronizar médias e desvios calculados APENAS no treino,
   clipping de standardized [-5,5] e intercepto calibrado
   para prevalência de treino antes de otimização.
   Selecionar WATCHs do teste com probabilidade >= percentil 80
   das probabilidades **do treino**; nunca ajustar threshold
   pelo resultado do período de teste. Não treinar em U
   antes de prever U; aplicar embargo temporal.

Treinamento usa TODOS WATCHs rotulados; NÃO selecionar
somente trades vencedores nem treinar em labels de outras
estratégias. Modelo prediz QUALIDADE do WATCH, mas executa
a regra original: confirmação M5 em até seis M5 depois,
SL 12 M5 ±0,1 ATR, TP 1,8R bruto, RR líquido >=1,2,
máximo 24 M5 (2h), custo 0,06% taker + slippage 0,02%
por lado; 1% de risco fictício por operação e 1 posição
simultânea global por seletor. Não usar resultado futuro
para decidir selecionar.

## Métricas e critérios anteriores ao replay

Em cada U,V,W0: nº WATCHs, prevalência, frequência de
alertas selecionados, precisão da label vs BASE e H1_SIMPLE,
Brier do modelo vs constante de prevalência de treino,
precision/recall, resultados financeiros reais no replay
paper (trades, TP, SL, TIME, retorno e drawdown) e
delta contra BASE. Agregado de três blocos de TESTE apenas:
soma de operações, retornos compostos por bloco e
blocos positivos; não somar T (treino).

Não aprovar LOGIT se retorno não positivo nos 3 blocos
OU se frequência >3 trades/dia OU se Brier não melhorar
consistentemente sobre constante. Para aprovar qualquer
coisa em produção ainda exigir forward paper genuíno.
Não ajustar parâmetros/variáveis/threshold depois de
ver os resultados desse estudo, não escolher período vencedor
ou trocar modelo com base no desfecho.

## Limitações específicas de dados

Candles públicos M5/H1 não incluem livro de ordens completo,
bid/ask histórico, slippage executado nem agressão taker
historicamente persistida pelo script. Portanto **não
afirmar que testou order-flow imbalance**; requer gravar
snapshots/eventos e timestamps antes de avaliação futura.
NautilusTrader/FreqAI/Freqtrade não são usados como
"caixa preta" neste estudo; testamos as HIPÓTESES de
meta-label, classificação e filtros simples sobre o
executor existente.
