# Experimento 5 — liquidez × M1 (22/11/2026)

Status: **pesquisa exclusivamente histórica**; nenhuma ordem, Telegram, alteração do scanner ou dos filtros de produção. A branch nasce da `main`, separada da correção experimental de cadastro ORCA.

## Hipótese e desenho fixados ANTES de executar esta nova coorte

Queremos saber se contratos com giro de 24h entre **200 mil e 5 milhões de USDT** têm sinais M1 tecnicamente interessantes, sem assumir que podem ser operados com o mesmo slippage que ativos acima de 5 milhões.

- Janela histórica de sinais **07/11/2026 00:00 a 21/11/2026 00:00 UTC (exclusivo)**, 14 dias. Não abrange o ganho de ORCA relatado em 21/11 por volta das 10h45 BRT, embora ORCA tenha sido escolhida porque esse caso já é conhecido.
- Cohort de seleção: ORCA + cinco outros contratos regulares cripto USDT abaixo de 5M, escolhidos pela proximidade do giro atual à ORCA; mais seis elegíveis imediatamente acima do piso de 5M. A política é determinística **antes de saber os resultados de preço**; seu uso de ticker atual causa viés de sobrevivência e o conjunto não é representativo.
- Na análise, o grupo de cada sinal é calculado novamente pelo **volume financeiro acumulado de 1.440 candles M1 anteriores à confirmação**, sem olhar o volume futuro. Faixas históricas: 0,2M–5M; >=5M; abaixo de 0,2M (separada).
- Warmup causal H1 de 240 candles, M15 de 480 candles e pelo menos um dia M1 antes do início; exigir dados completos e consistência OHLC M1/M15. Fontes incompletas ou divergentes são descartadas e relatadas.
- Usar `form_plans` + `process_minutes` de `mexc_scanner.minute_breakout`: consolidação em 8 M15, rompimento além de 0,10 ATR, dois candles M1 seguidos, segundo volume >=50%, TP/SL/faixa fixados no primeiro.
- Hipótese de entrada no **próximo M1 aberto**, somente dentro da faixa de entrada e com viabilidade financeira pelo avaliador atual. Candle tocando simultaneamente TP e SL conta stop. Ao completar 4h, encerrar hipoteticamente no último fechamento.
- Saldo de referência para dimensionamento: 50 USDT, e avaliação adicional de 1 USDT, sem modificar a carteira operacional.
- Custo-base: taxa taker suposta 0,06% por lado, spread sintético ~0,02%, slippage 0,02% por execução ou 2 ticks, funding zero. Estresse: slippage 0,10% por execução ou 2 ticks para ambos os grupos. Livro histórico é **desconhecido**, não presumir os fills executáveis.
- Métricas: oportunidades técnicas, bloqueios financeiros, entradas hipotéticas, acertos líquidos por saída, intervalo Wilson descritivo de 95%, R médio e total, saídas, e estresse de uma posição por vez. A carteira sequencial usa R com saldo de referência fixo, **não produz saldo real ou lucro em USDT verificável**.
- Nenhum limiar novo será escolhido com base no resultado desse mesmo conjunto de dados.

## Critérios de interpretação

**Não basta taxa de acerto alta.** Se R médio líquido <=0, drawdown severo ou viabilidade quase nula, não há base para liberar baixo giro. Se houver amostra pequena, zero confirmações, coorte incompleta, custos desconhecidos ou alta correlação, classificar como inconclusivo. Intervalos de Wilson em operações dependentes podem exagerar precisão; não usar como prova formal.

Resultado promissor exige acompanhamento prospectivo e amostra realmente independente, além de profundidade de livro histórica/realista e custo da conta. A posterior validação de 60 dias está condicionada à fonte de dados: a consulta à MEXC de 22/11 retornou zero M1 em uma amostra exatamente 60 dias atrás, ainda que amostras de 14 e 30 dias fossem consultáveis.

## Como reproduzir

`python -m unittest tests.test_research_liquidity_cohort -v`

`python -m scripts.research_liquidity_cohort`

O segundo comando acessa somente endpoints **GET públicos** do catálogo, ticker e klines MEXC. No GitHub, o workflow de pesquisa gera `reports/liquidity-cohort/result.json` e `report.md` como artefatos, sem alterar `scanner-state` e sem notificar.

**A `main` e os parâmetros de produção permanecem intocados.**
