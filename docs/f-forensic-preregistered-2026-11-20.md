# Diagnóstico causal dos resultados da estratégia F — 20/11/2026

**Pesquisa descritiva; não define filtros operacionais novos.** Registrar o protocolo antes
de executar qualquer nova análise no GitHub Actions. Nenhuma mudança em `main`,
Telegram ou execução de ordens.

## Universo fixado

Manter os 10 contratos históricos do replay BRK-T/SMC-R
TAO, SOL, AVAX, ENA, DOT, ZEC, HYPE, AAVE, BTC, ETH, com quatro janelas
iguais de 42 dias: T, U, V, W entre 05/06 e 20/11/2026, total de 168 dias.
A população de análise é a **carteira global de uma posição por vez**
calculada por `select_portfolio`, 1% de saldo de risco hipotético por trade.
Usar `replay_structural(...,"F_sweep_rejection")`, sem alterar nem uma regra.
Exigir reprodução de 24, 10, 27 e 20 trades nas quatro janelas, total **81**,
com 26 TP, 43 SL e 12 TIME (registros anteriormente observados).
Não comparar todos os sinais independentes com a carteira global.

## Atributos conhecidos na decisão ou na abertura seguinte

Sem acesso a candles futuros, para cada sinal F armazenar:
- `vol_ratio`: quote volume da vela de rejeição / mediana de 12 anteriores;
- `atr_pct`: ATR14 M5 (calculado antes da rejeição) dividido pelo close do sinal;
- `stop_pct`: distância do stop até a abertura M5 seguinte / entrada;
- `wick_frac`: fração do pavio superior no range da vela de rejeição;
- `sweep_atr`: excesso da máxima da vela acima da resistência dos 24 M5 anteriores,
  dividido pelo ATR14 pré-sinal;
- `range_atr`: amplitude da vela M5 / ATR14 pré-sinal;
- `body_frac`: tamanho do corpo bearish / range da vela de rejeição;
- `m5_return_60m_pct`: close da rejeição vs close 12 M5 anteriores;
- `m5_return_120m_pct`: close da rejeição vs close 24 M5 anteriores;
- `h1_below_ema20_pct`: diferença percentual (EMA20 - último close H1),
  usando apenas H1 fechado até o timestamp do sinal;
- `h1_return_3h_pct`: último close H1 / close 3 H1 atrás - 1;
- `relative_stop_to_atr`: stop distance (entry) / ATR14 pré-sinal;
- `utc_hour`: hora UTC do sinal (descritivo; não extrair janelas vencedoras para operar).

`stop_pct` só pode ser usado para decidir aceitar/rejeitar **na abertura seguinte**,
pois a abertura é um preço futuro relativamente ao candle de sinal; nunca usá-lo
para fabricar uma decisão antes de acontecer. Os demais atributos são causais ao
fechamento do gatilho.

## Relatório necessário

- TP / SL / TIME por janela e por contrato, medianas e média por TP vs SL e
  TIME de cada atributo, distância padronizada robusta e AUC meramente descritiva
  TP versus SL, sem atribuir significância causal.
- Para cada variável, divisão exploratória na mediana dos trades selecionados,
  com número de trades, TP, SL, TIME, ROI líquido estimado, R médio e balanço
  por janela de 42 dias. **Time-out fica nos resultados econômicos**.
- Testar visualmente estabilidade entre as quatro janelas e não selecionar
  percentil/limiar vencedor para usar em produção.
- Observações sobre seleção retrospectiva, correlação de altcoins, custos,
  amostra reduzida, ausência de fills reais e sobreajuste.
- Não incluir V4/SMC-R/BRK-T no diagnóstico de F nem misturar sinais perdedores
  não escolhidos pela carteira.

Uma correlação com TP/SL não prova que seja um filtro rentável. A próxima
hipótese só pode ser validada **prospectivamente** após pré-registro,
com amostra nova e custos de mercado realistas.
