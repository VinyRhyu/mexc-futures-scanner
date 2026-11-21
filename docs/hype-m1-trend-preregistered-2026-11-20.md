# HYPE Min1: antecipação de entradas com contexto H1/M5 — protocolo congelado

**Data:** 20/11/2026, antes da execução M1. Pesquisa paper, jamais ordens reais.
Hipótese motivada pelos movimentos de HYPE observados em 16/11 e 17/11:
o WATCH em M5 sinalizou movimentos cedo, mas a entrada M5 às vezes foi tardia.
Os períodos anteriores já foram usados em outras pesquisas: **NÃO holdout intocado**.

## Amostra fixa

- **REF:** 16/11 00h–18/11 00h BRT (os dois dias estudados pelo usuário).
- **CMP:** 09/11 00h–11/11 00h BRT (comparação cronológica distinta).
- **CMP2:** 02/11 00h–04/11 00h BRT (segunda comparação cronológica distinta).

Cada janela: início inclusivo, fim exclusivo. Até 2h posteriores exclusivamente
para avaliar trades; evitar novas entradas depois do fim. M1, M5 e H1 públicos
do mesmo contrato HYPE_USDT na MEXC; 90 minutos M1, 10h M5 e 160h H1
para aquecimento. Exigir integridade estrita de timestamp, OHLC e lacunas.
Min1: paginação em lotes de no máximo 1.400 candles.

## Etapa 1 — WATCH de M5 **inalterado**

Importar diretamente watch_at de `scripts/audit_hype_two_stage_1617.py`:
- TURN: cruzamento EMA9/EMA21 M5, corpo ≥0,25 ATR e volume >=0,8x.
- BREAK: fechamento fora das 6 M5 anteriores, corpo >=0,35 ATR e volume >=0,8x.
- DRIFT: M5 EMA9/21 e retorno 30min >=0,35%, volume >=0,55x.
- Repetição máxima por família/direção a cada 30min; união deduplicada
  por direção 30min, prioridade TURN/BREAK/DRIFT.
- Rótulo de avaliação (+1,25% favorável antes de −0,75% adverso em 90min)
  mantido estritamente diagnóstico, jamais usado para decisões.

## Etapa 2 — Três tratamentos FIXOS de confirmação com 1 minuto

Confirmar apenas depois da vela M5 que disparou WATCH, durante
os **30 minutos seguintes**, apenas com M1 totalmente fechado:

Regra M1 comum aos três braços:
- M1 fecha fora do extremo de 5 candles M1 ANTERIORES na direção do WATCH;
- corpo M1 na direção >=0,35 ATR14 M1 **antes** desse candle;
- volume cotado M1 >=1,0x mediana das 10 M1 anteriores;
- fechamento no lado coerente da EMA9 M1, EMA9 inclinada nos 3 últimos M1.

Três tratamentos, sem mudar limiares após ver resultados:

1. `M1_FAST`: primeiro M1 de confirmação, sem veto por M5/H1.
2. `M1_M5_TREND`: M1_FAST mais último M5 FECHADO com EMA9 acima
   de EMA21 e EMA9 crescente vs 2 M5 atrás (LONG), inverso SHORT.
3. `M1_H1_TREND`: M1_M5_TREND mais último H1 FECHADO com preço
   acima de EMA20 (LONG) ou abaixo de EMA20 (SHORT).

Para comparação `M5_ORIGINAL`: importar confirmação e execução
inalteradas de `scripts/audit_hype_two_stage_1617.py`,
com cutoff adequado ao fim da janela. WATCHs originais exatamente iguais.

## Execução M1 exploratória

- Entrada na abertura M1 seguinte ao fechamento confirmador, antes do cutoff.
- Stop na mínima/máxima das 15 M1 **anteriores à confirmação** mais
  buffer 0,15 ATR14 M1; TP 1,8R bruto; RR líquido >=1,2.
- TP/SL examinados nos 120 M1 seguintes (máximo duas horas).
  Se TP e SL no mesmo M1, contar stop; timeout no close do 120º M1.
- Taker 0,06% + slippage 0,02% **por lado** da posição
  (0,16% roundtrip notional), sem funding, book/spread dinâmico, fills.
- Risco fictício de 1% saldo por posição, seleção global cronológica
  de uma posição por vez para cada braço; carteira independente por braço.
- **Comparação M1 vs M5 não altera apenas o tempo do candle: os stops
  e critérios de confirmação também diferem.** Descrever como pacote
  experimental, não atribuir eventual diferença exclusivamente ao M1.
- Não usar nenhum dado M5/H1 ainda aberto; H1 fechado vigente em cada M1.
- Evitar sinais/entradas após cutoff, mas permitir 2h de dados de saída.
- Usar somente sinais disponíveis na linha temporal em cada decisão.
  Nenhuma ordenação por resultado para selecionar trades.

## Saídas e decisão

Por janela, reportar todos WATCHs, M1 confirmados, rejeições de RR,
trades elegíveis, carteira 1-at-a-time, TP/SL/TIME, ROI, MDD, custo,
frequência por dia, mediana de latência WATCH→confirmação, exemplos
e horários de cada posição. Comparar com original em REF:
73 WATCHs, 32 elegíveis, 17 escolhidas, −3,204% ROI.
Se divergirem, interromper interpretações e corrigir a reprodutibilidade.

**Critério prévio de triagem:** no máximo 3 trades/dia e ROI líquido
positivo em ambas comparações mais referência, MDD <=10%, sem
reprovação de custo; nenhum resultado permite operar de verdade
porque os dados foram previamente observados. Não otimizar limiares
após ver resultados negativos.
