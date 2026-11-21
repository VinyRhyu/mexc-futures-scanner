# HYPE — meta-labeling ECONÔMICO em operações confirmadas: pré-registro

**21/11/2026 — registrado ANTES de executar este teste.** Repositório
experimental, HYPE_USDT perpétuo MEXC, candles fechados M5/H1.
Não enviar mensagens ao bot, não realizar ordens e não editar main.

## Objetivo

Investigar se a classificação binária de **retorno econômico líquido da
operação efetivamente elegível** (net_R > 0) melhora a seleção de
oportunidades sobre a antiga classificação WATCH +1,25%/−0,75%.
Não alegar que a previsão do sinal é a previsão de ganho garantido;
R positivos e negativos têm magnitudes diferentes e podem produzir
ROI negativo com precisão >50%.

## Universo/linha temporal fixos

- Períodos T, U, V e W0 EXATAMENTE os de
  `scripts/audit_hype_watch_crossperiod.py`. Não acrescentar
  janelas, nem usar os dias 16/17 como teste de performance.
- 3 folds **expanding walk-forward**: treino T → teste U,
  treino T+U → teste V, treino T+U+V → teste W0.
- WATCHs TURN/BREAK/DRIFT congelados, cooldown e prioridade
  original. Confirmação M5 original até 6 velas. Executor original
  de stop 12 M5 ±0,1 ATR, TP bruto 1,8R, RR líquido >=1,2,
  taxa taker 0,06%+slippage assumida 0,02% por lado,
  TIME 24 M5, risco 1% do saldo e uma posição simultânea.
- Apenas confirmações **elegíveis** com operação válida
  (RR e stop corretos). Duplicar sinais no mesmo timestamp/lado
  não gera exemplos adicionais: deduplicar por hora de sinal e
  direção antes de treinar, usando ordem dos WATCHs original.
- O exemplo de treino tem features no instante de **fechamento
  da vela confirmadora**; o resultado ex post do executor original
  só vira label. O próximo candle de abertura e toda a trajetória
  posterior são PROIBIDOS na construção de features.
- Rótulo `positive_net_r`: 1 se `trade.net_r > 0`,
  0 caso contrário (TIME pode ser positivo ou negativo).
  Rótulos e saída só disponíveis após o encerramento real do
  trade. Em cada fold: remover do treino qualquer trade com
  `exit_at` + 120 min >= horário de início do teste, inclusive
  sobreposição temporal e embargo adicional conservador.
- Mesmo período: treino pode ter operações simultâneas como
  exemplos supervisionados (correlacionados); carteira teste
  mantém apenas uma posição simultânea. Nunca sortear folds.

## Features fixadas no fechamento da confirmação (13)

Retorno direcional 30min, retorno direcional 60min;
EMA9–EMA21 M5 direcional em % do close;
H1 close vs EMA20 direcional em %;
ATR14 M5 em % do close;
log1p(volume relativo do **candle de confirmação** frente
à mediana 12 anteriores);
corpo direcional da vela M5 / ATR;
rompimento direcional da máxima/mínima das 24 M5 anteriores / ATR;
distância do close de confirmação ao stop pré-calculado
da confirmação em %;
minutos WATCH→confirmação;
flag alinhamento H1 à direção;
flags família TURN e BREAK (DRIFT implícito).

Não usar entry da M5 seguinte, TP/SL efetivos pós-fill,
nem o resultado simulado como features. EMA calculada
somente com candles já fechados H1/M5.

## Três seletores (mesmo universo de confirmações elegíveis)

1. `ALL_ELIGIBLE`: todas as operações elegíveis do executor,
   referência validada contra (U 311/−36,532%; V 339/−35,793%;
   W0 286/−18,432%). Se não reproduzir, PARAR.
2. `H1_VOL_SIMPLE`: somente H1 alinhado e volume relativo
   da confirmação >=1,2x.
3. `LOGIT_TOP20_TRAIN`: regressão logística L2 (penalização
   0,02), LR 0,15, 140 épocas, intercepto iniciado com logit da
   prevalência do treino, z-score com média/desvio do TREINO,
   clipping [-5,5]. Score >= percentil 80 dos scores do
   **treino**, fixado antes do teste; não regular ou calibrar
   com labels do teste.

Todos os seletores usam o MESMO executor e mesmo custo;
para as carteiras, ordenar por sinal e selecionar só uma
posição simultânea através da função original.

## Métricas, critérios e limitações

Por U, V e W0: Nº exemplos treino/teste, taxa-base de
retorno líquido >0, Brier score da regressão vs prevalência
do treino, seleções, precisão sobre operações elegíveis,
recall dos positivos, TP/SL/TIME reais de replay, retorno
composto, net_R, max drawdown e trades/dia. Contar *todos*
TIME como sucesso ou fracasso conforme net_R real, não pelo
nome do estado. Agregados três folds SOMENTE de teste.

Critério de triagem: `LOGIT_TOP20_TRAIN` deve trazer ROI
positivo em pelo menos **2 de 3** períodos e ROI acumulado
positivo, DD <=10% por período, frequência <=3 trades/dia
e redução de Brier vs base em >=2 períodos. Não ajustar
parâmetros após resultados negativos.
Mesmo aprovação exploratória **NÃO** autoriza produção:
histórico reutilizado, amostras correlacionadas e slippage
hipotético. Testes futuros precisam coletar candles +
spread/trades/orderbook com timestamps antes de treinamento.

Este teste **não** roda FreqAI, MLfin.py nem NautilusTrader;
implementa rotulagem econômica e logit autocontidos
com mesma metodologia. Não afirma testes de order-flow
imbalance nem execução de trading real.
