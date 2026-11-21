# Roadmap de pesquisa — projetos open source e melhoria de sinais

20/11/2026. Plano de pesquisa experimental, sem modificar o scanner main, Telegram ou executar ordens.

## Evidências já apuradas

- Modelo F SHORT M5 falso rompimento: ROI simulado -5,11% em três janelas de 42 dias com risco 1% por operação.
- Modelo F com confirmação M5: ROI -14,91%, pior; não repetir confirmação só por estética de gráfico.
- Varredura mais recente 20/11 11h39 BRT: 59/60 perps USDT líquidos verificados; zero gatilhos F novos no M5 11h35; SOL e RARE eram setups M5 anteriores já vencidos.
- Tentativa sem limites teve 921 falhas em 1086 contratos por código de API 510. Sem cobertura suficiente, proibir afirmação de censo integral.
- O F atual usa a maior máxima em 24 M5 anteriores como resistência, um proxy simplista e potencial fonte de sinais falsos.

## Projetos para usar por função, não por promessas de lucro

1. CacheCarti/Crypto-Strategies (MIT): https://github.com/CacheCarti/Crypto-Strategies — 2.742 estratégias rejeitadas, relatórios sobre 7 gates: in-sample, out-of-sample, walk-forward, randomized starts, custos, holdout. Ênfase na metodologia; não tem estratégia comprovadamente vencedora na MEXC.
2. Khaymat/pyvsmc (MIT): https://github.com/Khaymat/pyvsmc — módulos Python para fractal swings, BOS/CHoCH, liquidez, FVG e order blocks; permite trocar máxima arbitrária de M5 por estrutura. Não é motor de estratégia ou lucro validado.
3. kayasolomon/poi-liquidity-detector (MIT): https://github.com/kayasolomon/poi-liquidity-detector — indicadores de sweep, CHoCH, zonas e timestamps de confirmação; testes de prefix-property documentados. É TypeScript/Node e jovem; preservar a ideia, não acrescentar runtime sem necessidade.
4. freqtrade/freqtrade-strategies (GPL-3.0): https://github.com/freqtrade/freqtrade-strategies — candidatos de estratégia externos para comparação justa; vários são LONG/spot, logo inaplicáveis diretamente a SHORT M5. Não copiar código GPL para projeto próprio sem avaliar obrigações.
5. freqtrade/freqtrade (GPL-3.0): https://github.com/freqtrade/freqtrade — backtesting, lookahead-analysis e recursive-analysis; MEXC Futures não consta da lista oficial de futures no README consultado. Usar ferramentas de teste com dados importados se compatíveis, não presumir integração.
6. ccxt/ccxt (MIT): https://github.com/ccxt/ccxt — API normalizada de OHLCV, derivados e instrumentos, rate-limit. Não elimina limites nem lacunas de histórico da MEXC.
7. nautechsystems/nautilus_trader (LGPL-3.0): https://github.com/nautechsystems/nautilus_trader — futura simulação event-driven e maior realismo de fill; complexidade elevada para a etapa atual.
8. darkvolg/Trading (GPL-3.0): https://github.com/darkvolg/Trading — protocolo público de paper e walk-forward; estratégia pública revisada é H1, can_short=False, leverage=1, por isso não serve como SHORT M5 direto.

## Experimento prioritário 1: qualidade da resistência

Hipótese a pré-registrar: o sweep de uma resistência composta por swing highs M5 já CONFIRMADOS, no contexto H1, tem menor taxa de SL e maior retorno líquido que a maior máxima arbitrária dos últimos 24 M5.

Construção mínima: usar pyvsmc para produzir somente níveis confirmados no momento t, com testes prefix (nenhum candle posterior a t pode afetar o sinal); congelar regras de entrada, SL, TP, custos, timeout e seleção da carteira.

Comparar baseline F contra F+nível estrutural em U/V/W (126 dias) e outra janela não consultada quando disponível. U/V/W já foram vistos: contam como desenvolvimento/exploração, não prova independente.

## Experimento prioritário 2: contexto externo, isolado do 1

Testar uma regra baseada em regime (volatilidade normalizada, dispersão da queda, funding/open-interest se fonte completa e cronológica) e comparar separadamente. Não somar filtros até a amostra ficar positiva.

## Correções de infraestrutura antes de uma nova varredura integral

- Filtrar criptomoedas reais USDT perp ativas, sem tokens de ações, índices, ouro, stablecoins e contratos de histórico insuficiente.
- Filtrar volume negociado de pelo menos 2M USDT/24h e spread/profundidade suficientes; mostrar total elegível, válido, falhas e horários.
- Cachear candles fechados por par/timeframe, buscar somente candle novo, usar concorrência limitada, backoff em código 510 e orçamento de requests, não 1086 downloads em rajada.
- Classificar PREPARAÇÃO, GATILHO_TÉCNICO, APROVADO_PELO_RR e EXPIRADO. Não converter sinal gráfico em operação sem calcular RR líquido e execução.
- Arquivar snapshots para reprodutibilidade, nunca preencher candle ausente artificialmente.

## Gates de aceitação

Exigir lucro líquido em cada período, pior cenário de taxas e slippage, pelo menos 40 operações selecionadas ou classificar a amostra como insuficiente, limite de até 2-3 seleções por dia, drawdown <=10% com risco simulado 1%, ausência de lookahead, resultados distribuídos por diferentes moedas e dias. Metodologia já examinada não conta como out-of-sample independente.

Se um experimento passar, realizar 30 dias de paper prospectivo sem alterações de parâmetros e com registros de preços realmente executáveis, spread, funding e tamanho mínimo. Até então, nada de ordens ou sinais apresentados como entradas seguras.
