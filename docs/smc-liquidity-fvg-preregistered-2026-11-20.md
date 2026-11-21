# SMC-R: novo challenger SHORT via sweep de liquidez + FVG

**Registro anterior à execução:** 2026-11-20. Hipótese de pesquisa, não sinal operável.
Criado para testar uma estratégia distinta da F (falso rompimento M5) tomando
como referência conceitual https://github.com/joshyattridge/smart-money-concepts
(MIT), SEM copiar a biblioteca ou usar pivôs centrados com candles futuros.
**Nenhuma otimização de limiares com base no resultado da execução.**

## Hipótese fechada de investigação

Uma varredura de liquidez de uma resistência histórica M5, **seguida** por um
desequilíbrio bearish FVG de 3 candles, pode identificar shorts com expectativa
líquida superior à regra F. O FVG é definido somente após fechar seu terceiro
candle. Indicadores H1/M5 sempre usam candles fechados.

Condições para abrir SHORT hipotético:
1. **Contexto:** último H1 fechado com close abaixo de EMA20 H1; essa condição
   precisa ser verdadeira tanto no fechamento do sweep quanto no do FVG.
2. **Sweep M5:** o high de um M5 ultrapassa a maior máxima dos **36 M5 anteriores**
   por >= **0,10 ATR14 M5**, fecha de volta estritamente abaixo daquela máxima;
   pavio superior >= **25%** da amplitude e volume financeiro do M5
   >= **1,0x** mediana dos 12 candles anteriores. É um evento de rejeição,
   não apenas um rompimento simples. Não exige close < open.
3. **Confirmação FVG:** **2 a 4 candles M5 fechados após o sweep**, o candle
   confirmador é bearish (close < open), possui corpo >= **0,6 ATR14 do M5
   imediatamente anterior ao sweep**, volume financeiro >= **1,2x** mediana
   dos 12 M5 anteriores e deixa um bearish FVG:
   **high(confirmador) < low(confirmador-2)**, com gap >= **0,05 ATR14 do
   sweep**, fechando também abaixo do low do candle do sweep.
   O sinal nasce **somente no close do confirmador**.
4. **Entrada hipotética:** open do M5 seguinte à confirmação. Stop fixo acima
   do high do sweep + **0,10 ATR14 do sweep**; TP fixo a **2,0x** o
   risco (distância entry→SL); timeout **24 candles M5 (120 min)**.
5. **Economia:** taxa taker hipotética **0,06% por lado** + slippage
   **0,02% por lado**. Exigir relação R:R **líquida >=1,2** antes de aceitar
   o trade. Nunca escolher evento pelo retorno futuro. SL e TP tocados no
   mesmo candle M5 -> AMBIGUOUS, penalizado como **-1R**.
6. **Controle concorrência:** uma posição por ativo até seu encerramento e
   no máximo uma posição total para a simulação de carteira; desempate em
   timestamps iguais por maior volume relativo conhecido ao confirmar
   (volume M5 confirmador / mediana dos 12 anteriores), seguido símbolo.

### Baseline justa

Comparar com **F_sweep_rejection original**,
scripts/audit_confluence_v3.py, parâmetros intactos, com o mesmo universo,
datas, histórico validado, taxa, modelo de gestão global e carteira.
A F usa 1,8R e sua própria regra RR>=1,2; **não** alterar sua parametrização
apenas para igualar o challenger, pois cada regra é uma estratégia separada.

Somente SHORT por ora: um modelo LONG é uma hipótese separada com condições
diferentes, não uma simetria inferida sem teste.

## Conjuntos temporais declarados sem olhar os resultados SMC-R

10 contratos fixos TAO, SOL, AVAX, ENA, DOT, ZEC, HYPE, AAVE, BTC, ETH
(MEXC_USDT perps). Cada um tem 42 dias, analisados em duas metades cronológicas.
- T (nova janela relativamente menos examinada): 2026-06-05T11:00Z até
  2026-07-17T11:00Z.
- U: 2026-07-17T11:00Z até 2026-08-28T11:00Z.
- V: 2026-08-28T11:00Z até 2026-10-09T11:00Z.
- W: 2026-10-09T11:00Z até 2026-11-20T11:00Z.

T é uma validação histórica exploratória e NÃO um teste prospectivo ou
evidência independente de verdade: decisões foram tomadas depois de observar
diversas janelas posteriores. Nenhum dos blocos é garantido como amostra
independente e sinais de altcoins são correlacionados.

O replay deve recusar cobertura parcial (histórico H1/M5 contínuo e íntegro
em todos 10 ativos) e registrar ausência de dados sem preencher silenciosamente.
Permitir execução de janela isolada para evitar limite da API.

## Métricas e decisão pré-fixadas

Mostrar por janela e duas metades: nº de candidatos, nº de execuções na
carteira, TP/SL/TIME/AMBIGUOUS, retorno líquido R e ROI com risco hipotético
de 1% do saldo por trade, drawdown máximo, operações/dia, RR médio, custos,
quais ativos contribuíram, sinais ignorados por concorrência; comparar com F
nos MESMOS dados. Resultado favorável na pesquisa exige:
- ROI líquido >0 em **T, U, V e W** individualmente.
- Pelo menos 40 operações selecionadas no total, não >2 por dia.
- Máximo drawdown de carteira contínua <=10% com risco hipotético 1%.
- ROI >baseline F no período total e expectativa líquida R positiva.
- Robustez: refazer depois custos dobrados (sensibilidade), sem escolher
  novos parâmetros, antes de considerar paper trading prospectivo.

Falha de um requisito => **não integrar**, apenas analisar causas de erro.
Comparações em múltiplos períodos e diversas variantes geram risco real de
seleção/overfit; a estratégia não está validada por lucrar em um recorte.

Sem Telegram, main, execução de ordens, alavancagem real ou alteração de
configurações existentes. Toda pesquisa na PR experimental.


---

## Resultados reais do experimento retrospectivo (após congelamento, 20/11/2026)

Execução completa e **CI aprovada**:
https://github.com/VinyRhyu/mexc-futures-scanner/actions/runs/44759118107

A ação primeiro executou testes unitários, incluindo causalidade temporal
do sweep/FVG, bloqueio de candles futuros, preço de entrada após confirmação
e vela OHLC com ambos TP e SL (AMBIGUOUS). Depois avaliou **todos os 10
contratos** em cada janela. Nenhum erro de cobertura reportado.

| Janela UTC (42d) | F: operações | F: ROI | SMC-R: operações | SMC-R: ROI |
|---|---:|---:|---:|---:|
| T 05/06–17/07 | 24 | +0,893% | 29 | -4,750% |
| U 17/07–28/08 | 10 | -1,696% | 31 | -1,962% |
| V 28/08–09/10 | 27 | -2,237% | 24 | -7,068% |
| W 09/10–20/11 | 20 | -1,263% | 31 | -8,902% |
| 168 dias, ROI encadeado aproximado | **81** | **-4,261%** | **115** | **-20,944%** |

O ROI combinado usa a multiplicação dos quatro fatores de retorno
(1+ROI_janela), e não soma de percentuais; cada backtest de janela foi
feito separadamente. **Não calculamos o drawdown global de 168 dias
a partir de logs por janela; não inferir** esse valor.

### Breakdown da carteira

- F: 81 operações, 26 TP, 43 SL e 12 TIME; R acumulado das quatro
  carteiras -3,894R; janela T foi positiva, porém U/V/W negativas.
- SMC-R: 115 operações, **12 TP**, **42 SL**, **61 TIME**;
  R acumulado -23,082R. Todas as quatro janelas tiveram ROI negativo.
- Por janela SMC-R:
  - T: 29 trades, 2 TP, 12 SL, 15 TIME, -4,746R, DD máx 9,384%.
  - U: 31 trades, 6 TP, 8 SL, 17 TIME, -1,866R, DD máx 5,965%.
  - V: 24 trades, 2 TP, 8 SL, 14 TIME, -7,259R, DD máx 8,479%.
  - W: 31 trades, 2 TP, 14 SL, 15 TIME, -9,211R, DD máx 9,662%.

Custos *assumidos*: taker 0,06% + slippage 0,02% **por lado**.
Risco hipotético 1% do saldo por trade; sem modelar funding, order book,
lotes mínimos, preço de marca, liquidação, diferenças de fill ou alavancagem.
Sinal formado exclusivamente com candles M5/H1 fechados e entrada simulada
na próxima abertura. TP/SL simultâneos no mesmo candle penalizados, nunca
contados como vitória. Não houve indicação de AMBIGUOUS nos registros das
carteiras selecionadas.

### Decisão

**SMC-R reprovada e rejeitada para integração no Telegram/main.**
O experimento não alcançou o primeiro critério de retorno positivo em
T/U/V/W; estresse de custos dobrados não foi executado por não justificar
aprovação. Os parâmetros não devem ser ajustados iterativamente com esses
mesmos resultados para extrair lucro de amostra.

O fato de a regra produzir 61 timeouts e só 12 alvos sugere investigar
se o *deslocamento após o FVG já está esgotado* no momento do sinal,
mas isto é uma **hipótese causal não testada**. Próxima comparação
independente, se autorizada, deve vir de outra família pre-registrada,
por exemplo rompimento de compressão/continuidade LONG e SHORT; ou medir
a execução real/custos antes de desenvolver novos sinais. Reservar novas
datas e fazer paper prospectivo para qualquer candidato que passar.
