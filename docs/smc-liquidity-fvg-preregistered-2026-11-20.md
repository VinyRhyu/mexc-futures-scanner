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
