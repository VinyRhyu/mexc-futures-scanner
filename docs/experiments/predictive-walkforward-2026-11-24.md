# Pesquisa paralela: previsibilidade de TP antes do SL

**Pré-registro:** 24/11/2026. **Status:** exclusivamente pesquisa, branch isolada, PR em rascunho. **Produção permanece idêntica.**

## Hipótese mensurável

A partir de características **observáveis na confirmação M1**, um classificador probabilístico simples pode estimar a chance de alcançar o **TP técnico antes do SL** nas próximas **4 horas**, melhor que a proporção histórica fixa de TPs. A expectativa é uma hipótese a testar, não lucro comprovado.

**Isto não é ainda previsão antes de começar o movimento**: nesta fase usamos atributos já disponíveis quando a segunda vela M1 fechou. Isso permite construir e auditar um modelo probabilístico com rótulos e custos existentes, antes de investir na coleta necessária para antecipação ao primeiro M1. Nenhuma série de price action futura entra como feature.

## Base congelada (sem novo ajuste de seleção histórica)

Reusar exatamente os **cinco artefatos** `breakout-quality-{discovery,check}_*-45280197720` do GitHub Actions [run #45280197720](https://github.com/VinyRhyu/mexc-futures-scanner/actions/runs/45280197720), que já possuem `one_usdt_viable_unique_events.csv` com features calculadas antes da saída e o resultado posterior simulado. Aproximadamente **224 eventos únicos financeiramente viáveis** em 24 ativos hoje congelados. As janelas são:

| Janela UTC (início) | Uso pré-definido | Cuidado |
|---|---|---|
| 26/out/2026 | TRAIN | Histórico já analisado em outras pesquisas |
| 31/out/2026 | TRAIN | Histórico já analisado em outras pesquisas |
| 07/nov/2026 | TRAIN | Histórico já analisado em outras pesquisas |
| 14/nov/2026 | VALIDATION | Sem otimização por resultado |
| 15/nov/2026 20h | TEST retrospectivo | **Não é blind out-of-sample** |

Labels de treinamento devem estar **resolvidos antes da validação** (purge temporal). Não se treina com validação nem com teste, e não se ajustam features, limites, classes ou hiperparâmetros olhando seus resultados. Os eventos repetidos por plano de uma mesma moeda/sentido/minuto são rejeitados. Na série, `ALVO` = 1 e `STOP / STOP_AMBIGUO / TIME_4H` = 0, logo previsão significa *alvo antes de stop dentro do horizonte*; eventos `TIME_4H` **não** devem ser confundidos com stop realizado.

## Features disponíveis antes da entrada

`projected_net_RR`, `turnover24_USDT` (log10), M1 volume versus média anterior de 20, tamanho relativo e posição do fechamento no candle M1, range relativo ao ATR M15 fechado, extensões direcionalmente assinadas de 1h M1, 4h M1 e 2h M15, alinhamento com estrutura H1 fechada, direção LONG/SHORT. O modelo não recebe `outcome`, `exit_utc`, `net_R` ou `net_USDT_fixed_paper` durante treino de features, cotação ou decisão.

## Procedimento congelado

- Treinar **uma única regressão logística com regularização L2**, somente com biblioteca padrão Python. Padronização e probabilidade-base aprendidas no TRAIN; 500 passos, taxa 0,1, L2 0,08, features escaladas e winsorizadas em ±5 desvios — todos parâmetros fixados antes do teste.
- Validar as probabilidades com **Brier Score**, **Log Loss** e confronto com a previsão constante da taxa de alvo do próprio treinamento. Brier menor é melhor, mas só aceitaremos melhoria robusta com dados independentes.
- Para cada caso, avaliar `expected_R = P(TP) * RR_liquido_projetado - (1-P(TP)) * 1`, aproximação que supõe perda de uma unidade de risco no SL; só aceita quando `P(TP) > 1/(1+RR) + 0,03`. **O cálculo é estimado e não substitui validador financeiro completo.**
- Comparar **quatro variantes congeladas**: (1) confirmado atual com RR ≥1, (2) confirmado com RR ≥1,5, (3) escore preditivo com expectativa teórica positiva, (4) híbrido RR ≥1,5 mais escore positivo. Todas sobre o **mesmo universo de eventos**, mesmo corte temporal e até **uma posição simulada aberta por vez**. Em conflitos, ranking prévio por RR para baselines e valor esperado para modelos; não se usa futuro para decidir.
- Mostrar números aceitos, TP/SL/tempo, probabilidade estimada, Brier e somatório de P&L hipotético do tamanho fixo original. **Não** apresentar soma de resultados como crescimento composto real de uma banca de 1 USDT, nem comparar exposição variável com exposição fixa de forma enganosa.
- **Meta do usuário:** explorar 35% ROI líquido sobre margem por operação vencedora em pesquisas futuras. Esse CSV **não inclui margem exata da carteira mutável para cada hipótese**, portanto o estudo **não** prova nem exige 35% ROI fechado em cada sinal. Antes de produção, cruzar o preditor com simulação completa de margem, taxas, funding e liquidação.

## Critérios de avanço ou descarte

Só avançar de pesquisa exploratória se o desempenho probabilístico superar taxa histórica constante e o resultado financeiro for pelo menos não negativo em janelas temporais distintas, com amostra e confiança adequadas. **Um único bloco final positivo, ou uma combinação retrospectiva favorável, não autoriza produção.**

**Fase 2 — antecedência verdadeira:** coletar em paralelo eventos ainda sem confirmação, com features ao fechamento M1 anterior/primeiro M1 e rótulos futuros separados, incluindo **todos** os ativos e horários elegíveis, inclusive não sinais (para evitar viés de seleção). Exigir rótulos completos, escala de contrato e livros/funding históricos contemporâneos. Treinar modelo que antecipe movimento **antes do rompimento** e confrontar (a) entrada antecipada, (b) predição no segundo M1, (c) confirmação clássica no mesmo intervalo futuro e custos idênticos. Avaliação forward shadow independente antes de qualquer mudança na estratégia.

## Limitações e proteções

- O MEXC público M1 teve lacunas antigas na investigação de 60 dias; **não completar ou sintetizar barras** para preencher histórico e não extrapolar janela para 60 dias.
- Os 24 ativos e os critérios RR já foram escolhidos/examinados em estudos prévios: risco de survivorship e overfitting significativo.
- `one_usdt_viable_unique_events.csv` só contém eventos tecnicamente confirmados e financeiramente viáveis com carteira de referência, **não** todos os contextos de mercado. O preditor nesta fase não gera sinais inéditos.
- `net_USDT_fixed_paper` considera custos hipotéticos do replay; não equivale a ordens executadas na MEXC ou capital composto com posição única real e funding real.
- Não tocar `main`, `.github/workflows/scan.yml`, `config/default.toml`, motor de produção, financeiro, cronjob.org (1/min), Telegram somente de entradas validadas, estado, carteira paper ou alavancagem 10x–20x.
- Toda saída de CI fica em artefatos JSON/CSV auditáveis, **nunca no Telegram**. PR fica **draft** até revisão científica, independentemente de CI verde.
