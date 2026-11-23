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


## Resultado executado (23/11/2026 UTC, sem operações)

Execução final e evidência: [GitHub Actions 45092062278](https://github.com/VinyRhyu/mexc-futures-scanner/actions/runs/45092062278). A suíte [45092062272](https://github.com/VinyRhyu/mexc-futures-scanner/actions/runs/45092062272) passou. Resultado completo está no artefato da execução (JSON e Markdown).

A primeira execução [45091394222](https://github.com/VinyRhyu/mexc-futures-scanner/actions/runs/45091394222) foi inválida por cursor desatualizado durante minutos ociosos; a segunda [45091759379](https://github.com/VinyRhyu/mexc-futures-scanner/actions/runs/45091759379) revelou que planos encerrados podiam ser recriados no replay devido à limpeza da memória. Ambos os defeitos **eram no experimento**, não no scanner principal. A rodada final preserva os IDs vitalícios dos planos e apresenta cobertura válida 12/12, com 1.440 M15 comparados a M1 por símbolo, sem divergência.

### Amostra retrospectiva com custos-base

| Grupo segundo giro de 24h conhecido no momento do gatilho | Confirmações M1* | Entradas hipotéticas com saldo 50 USDT | Lucro líquido >0 | Acerto observado | Média R líquida por entrada |
| --- | ---: | ---: | ---: | ---: | ---: |
| 200 mil–5 milhões USDT | 351 | 17 | 1 | 5,9% | -0,885 R |
| 5 milhões USDT ou mais | 290 | 40 | 6 | 15,0% | -0,687 R |
| Abaixo de 200 mil USDT | 110 | 0 | — | indisponível | indisponível |

*Confirmações podem ser sobrepostas, de formações múltiplas e ativos correlacionados. Não equivalem a observações estatísticas independentes.

Desfechos no grupo 200 mil–5 milhões: 15 stops, 2 encerramentos em 4h, zero alvo; no grupo >=5 milhões: 34 stops, 5 alvos e 1 encerramento em 4h. O caso ORCA teve **100 confirmações técnicas** do motor no conjunto e **nenhuma entrada financeiramente viável** no cenário simulativo.

**Contagem por evento único** (mesmo símbolo, direção e minuto, desempate determinístico pelo ID do plano, sem resultado futuro): entre as entradas simuladas, 14 eventos distintos no grupo menor com 1 positivo (7,1%; média -0,860 R) e 34 eventos distintos no grupo maior com 6 positivos (17,6%; média -0,632 R). A conclusão permanece negativa após eliminar duplicidades.

Na carteira sequencial (uma posição por vez, desempate alfabético, R normalizado e saldo de referência fixo): **33 operações, 6 resultados positivos, soma -20,9572 R**, máximo drawdown realizado **22,3781 R**. Isso **não é uma curva de saldo real, ROI nem simulação de recomposição dinâmica de banca**. Não podemos somar a soma de R das operações independentes e chamá-la de lucro.

Estresse de slippage de 0,10% por ponta, mantendo taxas e demais regras: apenas 4 fills hipotéticos aceitos no grupo de giro baixo (zero positivo), e zero fills aceitos no grupo acima de 5M. A seleção de operações muda com a hipótese de custo; não interpretar ausência de fills como zero perda nem tratar as médias de R de cenários com amostras diferentes como comparação direta.

### Interpretação e decisão

**Este experimento não encontrou evidência de expectativa matemática positiva em nenhum dos grupos.** É um resultado retrospectivo exploratório limitado a 12 contratos escolhidos por liquidez presente, 14 dias de dados, entradas idealizadas e regras já estudadas em outros históricos. A taxa de acerto observada não é previsão de probabilidade futura; intervalos binomiais ignoram dependência entre trades e podem ser excessivamente confiantes.

**Manter o piso de 5 milhões, a estratégia e o modo paper na produção.** Não reduzir o filtro a partir de ORCA ou de desempenho isolado. Investigar em outra branch, se desejado, uma estratégia de impulso/volume realmente distinta voltada a contratos de baixo giro, com controle de spreads, profundidade e perdas. Reunir dados prospectivos e histórico contínuo antes de afirmar qualquer vantagem.

