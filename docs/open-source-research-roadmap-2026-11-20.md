# Pesquisa de bases open source para evoluir o MEXC Futures Scanner
_Data da auditoria: 20/11/2026. Sem merge em main. Nenhuma ordem ou alerta real._

## Diagnóstico do projeto existente

Nos testes F da estratégia SHORT de falso rompimento de resistência, as
3 janelas consecutivas de 42 dias não tiveram rentabilidade consistente:
-1,696%, -2,237%, -1,263% por janela; aproximadamente -5,11% composto com
risco hipotético de 1% do saldo por operação. A versão F+confirmação de outro
M5 piorou para cerca de -14,91% nos três períodos. Testes repetidos não criam
evidência independente; não selecionar moedas ou thresholds vencedores
retrospectivamente.

A coleta de 20/11/2026 (11h35 BRT, 60 contratos com turnover >=US$ 2 milhões,
59 com M5/H1 íntegros) produziu zero novos gatilhos F e um contexto
WATCH (HBAR), sem entrada liberada. Uma tentativa indiscriminada de
1.086 contratos USDT teve 921 falhas de API (rate limit 510) e incluiu
instrumentos não cripto. Não utilizar o censo incompleto para decidir trades.

## Projetos inspecionados e utilidade real

1. https://github.com/jesse-ai/jesse (MIT; framework)
   - Útil: pesquisa de estratégia LONG/SHORT, backtest de futuros, histórico
     de decisões, custos, teste de significância e stress Monte Carlo.
   - Não possui a estratégia vencedora; configuração de exchange e ingestão
     de dados MEXC exigem integração específica. Suporte live da MEXC não
     presumido. Jesse tem componentes premium/live separados: não prometer
     execução sem verificar licença, plano, conector e compatibilidade.

2. https://github.com/joshyattridge/smart-money-concepts (MIT; indicadores)
   - Útil: FVG, Liquidity, BOS/CHoCH, order blocks, zonas de stop hunt.
   - ALERTA CRÍTICO: swing_highs_lows usa janela central com candles
     ANTERIORES E FUTUROS; um pivô só pode entrar no estado em tempo real
     após sua confirmação futura. Nunca tomar marca de pivô na data
     original de formação como se fosse um dado conhecido no instante.
     Implementar testes que mutam candles futuros e exigem sinal inalterado.

3. https://github.com/polakowo/vectorbt (edição community)
   - Útil: comparações rápidas de sinais, custos, drawdown e distribuições.
   - Verificar licença da edição community antes de incorporar código;
     recursos de simulação detalhada de futuros, leverage e limit orders
     citados no site estão em VectorBT PRO comercial. Não exigir PRO
     para a primeira auditoria; scripts próprios event-driven podem suprir.

4. https://github.com/SeanG317/altcoin-scanner (pesquisa de sinais)
   - Útil: arquitetura pré-seleção por liquidez → atributos de candle →
     sinal LONG/SHORT → segundo estágio opcional ML.
   - Avaliado o código original em altcoin_scanner/strategy.py e
     altcoin_scanner/backtest.py. Backtest básico marca entrada no próprio
     close do sinal, não debita custos, contabiliza timeout como 0R e
     cada candidato de candle sem gestão de posição/carteira concorrente;
     os números da versão original NÃO são comparáveis diretamente ao
     nosso replay MEXC. Há pouca evidência pública de performance.
     Não copiar código sem validar licença.

5. https://github.com/frankabingale1111/smc-backtest (MIT)
   - Útil para ideia independente de sweep → FVG e pontuação;
     README indica que reteste FVG real, execução M15 mais precisa e
     walk-forward ainda estão como TODO. Não assumir que estão testados.

6. https://github.com/nautechsystems/nautilus_trader (LGPL-3.0)
   - Backtester de alta fidelidade, tick/order book e lifecycle, mas
     grande demais para nosso scanner sem execução automatizada.
     Reservar para quando custos e book se tornarem o gargalo.

## Experimento prioritário proposto (ainda NÃO executado)

### Hipóteses distintas, sem acoplar vários filtros à F

- **F**: baseline SHORT falso rompimento M5 existente (controle), sem ajustes.
- **SMC-R**: hipótese nova de liquidez varrida + desequilíbrio (FVG)
  confirmado por candle fechado; SHORT e LONG separados, sem swing centrado
  não confirmado. Definir formalmente parâmetros e stops *antes* do replay.
- **BRK-T**: rompimento de compressão + continuidade de momentum; competição
  genuína com reversão, não apenas uma regra extra acoplada à F.

Priorizar primeiro comparar F e SMC-R; BRK-T só no experimento seguinte se
existir novo conjunto de validação independente.

### Dados e testagem

- Congelar data de coleta, universo histórico elegível e símbolos.
- MEXC perp USDT de altcoins criptográficas, sem produtos indexados de ações,
  metais, fiat ou estáveis. Min turnover inicial US$2 milhões/24h;
  se um ativo não tem histórico/quotes inteiros, contabilizar como falha.
- Cache em disco, retries exponenciais e token bucket para respeitar limite
  da API; loteamento em vez de >1000 símbolos concorrentes.
- Apenas H4/H1/M15/M5 efetivamente FECHADOS no momento da decisão.
- Entrar hipoteticamente na próxima abertura, não no close do gatilho;
  spread e taxa taker/slippage MEXC; incluir stress dobrando custos;
  funding e liquidação tratados separadamente quando houver dados.
- Apenas uma posição global por vez; sinal simultâneo desempata por regra
  pública estabelecida antes da avaliação; evitar lookahead e survivorship.
- Saída por TP/SL no candle, caso AMBÍGUO = perda conservadora; timeout
  fecha pelo preço de mercado com custos reais hipotéticos, não 0R.
- 3 splits temporais fixos (desenvolvimento, validação, teste nunca
  inspecionado), e paper prospectivo. Não ajustar ao evento TAO/PUMP
  depois de observar seu resultado.
- Reportar ROI líquido, R esperado, profit factor, DD máximo, frequência,
  taxa TP/SL/TIME, coverage dos dados, custo médio por trade e resultados
  por mês e por regime. Registrar quantidade de testes experimentais.
- Exigir resultados positivos em blocos cronológicos independentes com
  amostra suficiente e sensibilidade razoável aos custos, antes de Telegram.

### Política de integração

Nada de execução de ordens e nada de sinal operável ainda.
Se um estudo passar, adicionar alertas *somente informativos* com estados
WATCH / CONFIRMED / EXPIRED / REJECTED_RR / DATA_STALE e timestamp;
usar duração curta por candle; preços do candle de referência não são fills.
Não acionar ML até reunir uma base rotulada realmente grande e evitar
vazamento entre datas, ativos correlacionados e janelas vizinhas.

**Próxima atividade de implementação:** preparar um adaptador causal de
FVG/liquidez a partir do projeto MIT de SMC, com testes de
ausência de informação futura, e executar um challenger SHORT no mesmo
replay MEXC e mesmo portfólio da baseline F. Esse passo não foi executado
nesta auditoria e portanto não há ROI novo a reportar.
