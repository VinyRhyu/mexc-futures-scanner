# Hipótese congelada: rompimento de compressão com momentum (BCM-1), LONG e SHORT

Registro anterior a qualquer execução da estratégia: **20/11/2026**.
Somente pesquisa/paper; sem ordens, Telegram, alteração de main ou otimização retrospectiva.

## Motivação
Estratégias de reversão F (falso rompimento de resistência) e SMC-R
(varredura de liquidez + FVG baixista) tiveram resultados líquidos negativos
em períodos longos. Testar uma **família diferente**, que acompanha
um rompimento de faixa comprimida com volume, sem exigir reteste tardio.

## Regra BCM-1 fixa
Sempre considerar SOMENTE candles M5 e H1 fechados no instante da decisão.
M5 armazena [open_timestamp_ms, open, high, low, close, volume, quote_volume].
**H1**: o último H1 fechado deve terminar com close acima de EMA20 para LONG
ou abaixo de EMA20 para SHORT. EMA20 iniciada pela média dos 20 primeiros
candles H1 fechados; nenhuma barra H1 aberta participa.

**Consolidação ANTERIOR ao candle gatilho**:
- Janela dos 12 M5 imediatamente anteriores (60 min), sem o atual.
- Amplitude (max(high)-min(low)) <= **4,0 × ATR14 M5** anterior ao gatilho.
- Média do true range dos 12 M5 anteriores <= **0,85 ×** média do
  true range dos 36 M5 imediatamente anteriores a essa janela.
- ATR14 calculado estritamente antes do gatilho, usando os 14 candles
  M5 anteriores e seus respectivos closes precedentes.

**Rompimento de continuidade**:
- LONG: o M5 gatilho fecha acima da máxima da caixa de 12 candles por
  >= 0,10 ATR14, candle verde, close acima EMA20 H1 (já aferido H1).
- SHORT: fecha abaixo da mínima da caixa por >= 0,10 ATR14,
  candle vermelho, close H1 abaixo EMA20 H1.
- Corpo do gatilho / (high-low) >= **0,60**.
- True range do gatilho entre **1,0 e 3,0 × ATR14 M5**.
- Volume financeiro (amount) do M5 gatilho >= **1,5×** mediana
  dos 12 M5 imediatamente anteriores.
- Acontece **no fechamento do gatilho M5**; entrada simulada no
  **open M5 seguinte**. Não aceitar entradas intrabar não confirmadas.

**Stops e alvos fixos ao entrar**:
- LONG stop = low(gatilho) − 0,10 ATR14, TP = entrada + 1,8× distância até stop.
- SHORT stop = high(gatilho) + 0,10 ATR14, TP = entrada − 1,8× distância.
- Exigir RR líquido >= 1,2 após taxa taker 0,06% por lado + slippage
  hipotético 0,02% por lado. Rejeitar stop inválido ou TP <= 0.
- Timeout **24 M5 (120 min)** contados da primeira barra pós-gatilho,
  liquidando a posição na última close simulada, com custos.
- Caso SL e TP toquem na mesma barra M5, classificar AMBIGUOUS e
  atribuir −1R na carteira, nunca vitória.
- Bloquear novo trade no mesmo ativo enquanto outro trade do mesmo
  ativo continua; simulação portfolio aplica no máximo 1 posição global.
  Desempate para sinais simultâneos: maior volume financeiro relativo
  conhecido no instante do gatilho, seguido ordem alfabética do símbolo.
- Sem stop dinâmico, take-profit parcial, filtro BTC novo ou seleção
  retrospectiva de ativos.

## Dados, períodos, comparação justa
10 contratos fixos MEXC: TAO, SOL, AVAX, ENA, DOT, ZEC, HYPE, AAVE, BTC, ETH.
BTC é incluído como ativo de referência/controle já usado nas análises anteriores,
mas os relatórios de altcoins também o separam explicitamente.
Janelas históricas FIXAS (42 dias cada):
- **S — menos examinada**: 24/04 11:00 UTC → 05/06 11:00 UTC.
- **T**: 05/06 → 17/07, 11:00 UTC.
- **U**: 17/07 → 28/08, 11:00 UTC.
- **V**: 28/08 → 09/10, 11:00 UTC.
- **W**: 09/10 → 20/11, 11:00 UTC.

Incluir warmup mínimo M5 80 barras e H1 80 barras, não inventar dados
ausentes; uma janela incompleta deve falhar, não ter ROI parcial apresentado.
Para cada janela executar **BCM-1 LONG, BCM-1 SHORT e BCM-1 ambos**;
comparar com **F original SHORT inalterada** nos mesmos contratos, datas e
custos. Reportar 21+21 dias, 42 dias, nº candidatos, operações da
carteira, TP/SL/TIME/AMBIGUOUS, R, ROI composto sob 1% risco por
trade, drawdown, número de dias e cobertura. Combinar janelas
temporalmente sem somar percentuais. Todas as análises são
retrospectivas, NÃO são resultados prospectivos nem provas de lucro futuro.

## Critérios de estudo para avançar
- ROI líquido positivo em **S e pelo menos 3 de 4 janelas T–W**,
  considerando a versão global BCM-1 ambos, **sem** escolher
  preferencialmente apenas LONG ou SHORT após observar resultados.
- Positivo no total e superior à F nos mesmos 210 dias.
- Pelo menos 40 trades de carteira nos 210 dias;
  até 3 trades por dia em média; drawdown máximo <=10%
  arriscando hipoteticamente 1% da banca por trade.
- Os dois sentidos LONG e SHORT precisam ser reportados,
  ainda que um lado vá pior. Caso falhe critério, rejeitar,
  não "corrigir" thresholds com base nessas mesmas datas.
- Sensibilidade a taxas dobradas e paper prospectivo obrigatórios
  **somente para a hipótese que passar**.

## Riscos técnicos
OHLC M5 não informa ordem intrabar de toques SL/TP; fill
next-open pode ser irreal com gaps/slippage, e taxas assumidas
não representam confirmação de fee do usuário. Funding, lotes,
liquidação, spread e alavancagem não são simulados. Com capital
de US$1, tamanho mínimo/margem podem tornar o plano não executável.
Nenhum desses testes executa dinheiro ou justifica entrar no
mercado agora.

## Implementação
scripts/audit_compression_momentum.py e
tests/test_compression_momentum.py. Executar em GitHub Actions
em branch experiments/confluence-tao-20261120 sem merge.
