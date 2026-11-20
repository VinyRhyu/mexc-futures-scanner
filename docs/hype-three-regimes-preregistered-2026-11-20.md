# HYPE: três famílias de sinais — pré-registro antes do replay

Data de registro: 20/11/2026. **Hipóteses derivadas da inspeção dos oito
movimentos de HYPE escolhidos pelo usuário. NÃO são fora da amostra,
mesmo ao testar períodos já inspecionados em outros estudos.**
Não executar ordens, mudar main ou enviar Telegram.

## Avaliar separadamente

A) **REVERSÃO por sweep/reclaim contra H1**:
- O último H1 fechado antes da confirmação está abaixo de EMA20 se LONG,
  acima se SHORT. LONG: um dos 3 M5 anteriores varreu o mínimo das 24 M5
  anteriores por 0,10 ATR14, fechou novamente acima desse mínimo,
  pavio inferior >= 35% da faixa da vela e volume da varredura
  >=1,2x mediana 12 anteriores. SHORT simétrico para máxima/pavio superior.
- A vela de confirmação M5 atual fecha na direção do trade acima do ponto
  médio (LONG) ou abaixo (SHORT) da vela de sweep, corpo >=0,25 ATR14
  da vela atual. Stop além da mínima/máxima do sweep por 0,10 ATR.
- Não usar máximo/mínimo observado após o sinal para decidir.

B) **CONTINUAÇÃO IMPULSIVA**:
- Último H1 fechado: LONG close > EMA20 > EMA50 e EMA20 crescente
  (versus H1 imediatamente anterior); SHORT simétrico.
- Candle M5 fecha fora da máxima/mínima das 12 velas anteriores
  para a direção H1, corpo na direção >=0,70 ATR14 pré-candle,
  quote volume >=1,2x mediana das 12 anteriores.
- Stop: extremo oposto das últimas 6 M5 anteriores mais 0,10 ATR.

C) **TENDÊNCIA GRADUAL / retomada de pullback**:
- Último H1 fechado: LONG EMA20 > EMA50 e EMA20 crescente, SHORT simétrico.
- M5 EMA20 > EMA50 e EMA20 crescente versus 6 M5 antes para LONG;
  SHORT simétrico.
- A vela M5 imediatamente anterior fez pullback até tocar EMA20 M5 e
  fechou a até 0,60 ATR14 da EMA20 (para qualquer lado).
- Confirmação atual: LONG verde fecha acima da máxima da M5 anterior
  e acima EMA20 M5; SHORT simétrico; corpo >=0,25 ATR14; volume
  atual >=0,70x mediana das 12 M5 anteriores.
- Stop além do extremo de 6 M5 anteriores +/-0,10 ATR.

## Execução e comparação, sem otimização

- Apenas candles M5/H1 efetivamente fechados; EMA20/50 H1 e M5
  inicializadas com SMA do período sem usar candles futuros.
- Entrada hipotética na abertura M5 seguinte, sem preencher se ainda não
  houver abertura; custo taker 0,06% por lado e slippage 0,02% por lado;
  RR bruto TP=1,8R, RR líquido ex ante >=1,2, stop válido.
- TP, SL ou tempo máximo 24 M5 (2 horas). Se TP e SL no mesmo M5,
  contabilizar como perda (AMBIGUOUS=-1R).
- Uma posição simultânea por **família**, avaliação de LONG e SHORT
  separadamente e combinados; uma posição na união das famílias com
  desempate de mesmo timestamp: REVERSAO > IMPULSO > GRADUAL.
- No replay registrar métricas sem escolher ativos, dias ou horários
  vencedores. Risco hipotético de 1% saldo por trade, capitalização
  simulada, MDD, TP/SL/TIME, trades por dia.
- Baseline F congelada em HYPE exclusivamente, no MESMO intervalo.
- Janelas históricas T,U,V,W de 42d (5/6–20/11) predefinidas em
  `scripts/audit_smc_liquidity_fvg.py`, além da semana
  Wk 16/11 00h até 20/11 19h10 São Paulo.
  A semana Wk é incluída no fim de W (com 11h10 adicionais) e
  NÃO pode ser somada aos 168 dias como período independente.
- A janela final de análise deve ter todo horizonte futuro de 24 M5
  para cada trade; omitir setups tardios e reportar truncamento.
- Registrar sinais de cada família nos oito intervalos escolhidos
  separadamente como **descrição retrospectiva**, não win rate.

## Critérios de honestidade

Um modelo só é candidato para pesquisar fora da amostra se demonstrar
frequência <=3 trades/dia, lucro líquido nas quatro janelas independentes
de calendário, drawdown <=10% a 1% risco e ganho acima da F, e resistência
a custos dobrados. Esses critérios são de TRIAGEM, não de aprovação
para dinheiro real, e dados são reutilizados de análises anteriores.
Se falhar, **reportar negativo e não otimizar**. Não prometer que
modelo detecta o início exato das oito janelas em retrospectiva.
