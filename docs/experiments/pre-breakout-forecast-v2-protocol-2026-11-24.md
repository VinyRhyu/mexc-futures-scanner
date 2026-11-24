# PREDICT V2 — protocolo de pesquisa pré-rompimento

**Status:** protocolo inicial, sem resultados V2. Pesquisa isolada; não é uma estratégia aprovada.
**Base congelada de comparação:** main @ f348de4b3bc313b483a342b3c7f96e3b85de0250.
**Antecedente:** [V1, resultado negativo](https://github.com/VinyRhyu/mexc-futures-scanner/blob/research/predictive-probability-walkforward-20261124/docs/experiments/predictive-walkforward-results-2026-11-24.md).

## Pergunta e hipóteses

H0: features observáveis antes do rompimento não geram vantagem probabilística nem financeira líquida fora da amostra, comparadas a referências simples.
H1: existe informação incremental em compressão, posição dentro da faixa, volume e comportamento relativo ao BTC para antecipar movimentos antes do gatilho M1, sem exigir tendência confirmada.

A V1 classificava entradas após confirmação; AUC 0,2691 e Brier 0,2668 no teste contra 0,2023 da referência constante. Não inverter o score V1 a posteriori.

## Amostragem e dados

- MEXC Futures USDT; universo elegível reconstruído com informação disponível no instante, incluindo ativos removidos quando recuperáveis; não usar liquidez ou listagem futura.
- Meta inicial: 60 dias históricos completos de M1 (UTC), com warmup suficiente para todos os indicadores; registrar cobertura, lacunas, exclusões, versões e fonte. Não imputar preços ausentes. Histórico já consultado é exploratório, não holdout intocado.
- Criar snapshots a cada 5 minutos, para cada símbolo elegível, independentemente de haver sinal, inclusive períodos laterais e sem rompimento. Registrar todos, e destacar coorte pré-rompimento: fechamento no interior da faixa das 60 barras M1 anteriores à última barra fechada (limites calculados sem ela); excluir dessa coorte quando a regra de confirmação PRD já tiver sido acionada para o setup em questão, a partir de replay causal. Se este estado não puder ser reconstruído, declarar a coorte apenas como aproximação geométrica.
- Dados de features com timestamp de disponibilidade <= instante t. Sem OHLC de barra aberta, sem preenchimento retroativo de OI ou funding e sem usar seleção condicionada à trajetória futura.
- Feature inicial: retornos de 1/5/15/30/60 min; volatilidade realizada 15/60 min e razão; amplitude e posição relativa no range anterior; volume relativo à mediana anterior; pavios e corpo; retorno relativo ao BTC sincronizado; regime de mercado. OI, agressão compradora/vendedora e livro apenas em uma ablação separada quando dados históricos com disponibilidade comprovada existirem.
- Primeiro artefato: dataset com chave (symbol, asof_utc), features, flags de disponibilidade e labels em tabela separada. Relatório de cobertura por dia/símbolo e rejeições; snapshot sem rótulo futuro completo fica censurado, nunca vira negativo.

## Alvos e execução simulada

- LONG e SHORT avaliados separadamente, usando a abertura M1 seguinte ao snapshot como aproximação de entrada, com latência/slippage adicional em sensibilidade; não assumir fill no fechamento observado.
- Horizonte primário pré-fixado: 30 min; secundários: 15 e 60 min.
- Barreiras iniciais de diagnóstico: stop a 1 ATR(14) M15 fechado e alvo a 1,5 ATR, distâncias congeladas em t, arredondadas pelo tick conforme lado. Isto é uma hipótese experimental, não parâmetros de PRD. Classes: TP primeiro, SL primeiro, timeout; dupla colisão na mesma barra: SL primeiro; gaps com preço executável conservador. Registrar MFE, MAE, tempo até barreira e retorno de timeout. Sensibilidade de execução não é seleção de melhores parâmetros.
- Comparar a antecipação e a confirmação PRD no mesmo universo/período com replay das regras vigentes, contabilizando oportunidades não operadas, diferença de instante de entrada, custos, número de trades, exposição e capital. Não confundir melhor preço de entrada em subconjunto vencedor com edge.
- Taxas, spread, slippage, funding disponível, limites de tamanho, margem e liquidação considerados na simulação financeira; quando algum dado não existir, declarar aproximação e cenários conservadores. Não ajustar alavancagem para transformar retorno percentual em lucro aparente; começar com risco normalizado em R, depois carteira paper de risco igual por trade, sem ordens reais.

## Validação e critérios

1. Auditar ingestão, timestamps, integridade, features e labels com testes de causalidade (alterar futuro não muda features); verificar exemplos de TP, SL, timeout, dupla colisão, gap e censura.
2. Benchmark constante por lado/horizonte estimado só no treino, regra simples de compressão e scanner PRD via replay, além de regressão logística regularizada como primeiro modelo. Árvores/boosting só como ablação pré-registrada depois.
3. Walk-forward cronológico com datas iguais entre símbolos: treino inicial, validação para calibração/decisão e blocos posteriores separados; expurgar rótulos com horizonte cruzando fronteiras e embargo mínimo de 60 min. Fit de normalização, imputation policy e calibração só no treino/validação próprios.
4. Reportar Brier, log loss, calibração, AUC/PR-AUC, frequência dos alvos, cobertura, ganho/perda líquido, expectativa por trade, profit factor e drawdown. Usar bootstrap por blocos temporais para intervalos de confiança e considerar dependência entre moedas e snapshots; controlar testes múltiplos (um horizonte primário).
5. Freeze da versão, universo, features, limiar e custos antes da janela prospectiva; reservar pelo menos 14 dias futuros a partir do freeze, ampliar se insuficiente. Janela já observada jamais rebatizada de holdout. Nenhum limiar recalibrado sobre o teste.
6. Só considerar shadow se o modelo bater benchmark probabilístico, tiver expectativa líquida positiva com incerteza compatível com edge (IC 95% inferior > 0 no critério primário), e estabilidade fora da amostra e sob custos adversos. Resultado negativo ou inconclusivo é resultado válido; não promover por AUC ou ROI isolado.

## Entregas

- E0 (feito): protocolo e branch isolada.
- E1: auditoria de disponibilidade histórica M1/universo/BTC e definição de dataset causal.
- E2: implementação e testes do construtor de snapshots e barreiras.
- E3: backtest exploratório e benchmarks financeiros comparáveis.
- E4: freeze e avaliação prospectiva intocada.
- E5: eventual shadow sem alertas PRD, somente após evidência e revisão.

Não alterar main, scan.yml, cronjob.org, Telegram, carteira de produção, TP/SL, alavancagem ou enviar ordens. Não programar execução nesta etapa. V2 não usa o resultado de V1 como validação.
