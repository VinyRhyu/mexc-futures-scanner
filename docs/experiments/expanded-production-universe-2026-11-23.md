# Pesquisa: universo ampliado e elegibilidade por liquidez no momento do sinal

Especificação congelada em 23/11/2026, antes de olhar os resultados da nova amostra. Base da pesquisa: `research/shadow-a-historical-holdout-20261123`, sem alteração da produção.

## Pergunta

O filtro A, que elimina sinais M1 quando o deslocamento direcional de preço nos últimos 4h é **>=2 ATR(14) M15**, aumenta o **resultado líquido em R** quando testado em moedas de maior liquidez, sem escolher apenas as 12 moedas que examinamos anteriormente?

Critério comparado: **BASE vs A**. Outros filtros B/A+B são diagnósticos opcionais, não novas regras otimizadas. O filtro A permanece exatamente congelado.

## Congelar a amostra, antes de olhar o resultado

1. Usar o método **`select_universe` de produção** com `config/default.toml` (top 50, giro mínimo atual 5.000.000 USDT, allowlist atual, contratos perpétuos USDT ativos) para formar **um único retrato do universo ATUAL**.
2. Guardar essa lista com ranking, giro atual, data e SHA256 ordenado no arquivo `frozen/universe.json`. Esse mesmo arquivo é usado por todos os jobs históricos — sem reranking ou troca de ativo baseada no retorno posterior.
3. **Limitação fundamental:** não existem snapshots completos e contemporâneos de todo o mercado na data histórica. Portanto, o retrato de hoje é selecionado **depois** das janelas avaliadas. É enviesado por sobrevivência e universo futuro e **não** permite afirmar que o conjunto era exatamente o top 50 operável em outubro/novembro. A elegibilidade passada top50 continua NÃO VERIFICADA.
4. Em cada confirmação, reconstruir a soma USDT de **exatos 1.440 candles M1 anteriores** e exigir >=5 milhões USDT no passado do sinal. Os candles futuros não entram nesse teste de giro.
5. Exigir M1, M15 e H1 completos e OHLC M1/M15 sem divergência. Símbolos excluídos por lacuna são **contabilizados explicitamente**, não preenchidos e não tratados como sem trades. O pré-teste de elegibilidade retornou apenas **24 contratos**, abaixo do mínimo de 35 originalmente exigido; o job parou antes de acessar resultados históricos. Mudamos então o requisito para **no mínimo 20 símbolos completos** (dos 24 elegíveis) para testar o universo efetivamente disponível; todas as exclusões serão explicitadas. Isso é um ajuste de capacidade da fonte, não resultado de otimização de trades.
6. Alguns sinais M1 compartilham moeda, direção e minuto por múltiplos planos técnicos. Para uma mesma tríade, selecionar deterministicamente o `plan_id` lexicograficamente primeiro **entre planos financeiramente viáveis**, antes de consultar seu resultado de saída. Registrar quantidade removida e preservar o plano escolhido.
7. Refazer a carteira sequencial de **uma posição por vez** para BASE e A separadamente, de modo que entradas liberadas por um veto possam ser avaliadas, incluindo se foram negativas.

## Janelas fixas UTC (fim exclusivo)

| Bloco | Início | Fim | Duração |
|---|---|---|---|
| E1 | 2026-10-31 00:00 | 2026-11-07 00:00 | 7 dias |
| E2 | 2026-11-07 00:00 | 2026-11-14 00:00 | 7 dias |
| E3 | 2026-11-15 20:00 | 2026-11-22 20:00 | 7 dias |

As datas já foram usadas em outras pesquisas das **12 moedas originais**. A principal novidade aqui é **ampliar a amostra de símbolos**, portanto **NÃO** chamar E1/E2/E3 de holdout temporal inteiramente novo ou não contaminado.

## Resultado a reportar

- Quantidade de símbolos congelados / disponíveis / com história incompleta, sinais confirmados, sinais com >=5M no momento e planos financeiramente viáveis.
- Eventos únicos (moeda/direção/minuto) e duplicatas técnicas removidas.
- BASE / A: quantidade de operações, vencedoras líquidas, R total/médio, máximo drawdown realizado em R e contagem por LONG/SHORT.
- Saídas conservadoras: tocar TP e SL no mesmo candle implica primeiro STOP; saída após 4h se não tocar nenhum.
- Vitórias e stops excluídos pelo filtro A; entradas que surgem apenas depois da liberação de slot; TP/SL originais para auditoria.
- Custos hipotéticos: taker 0,06% por lado, spread 0,02%, slippage mínimo 0,02% por ponta (ou 2 ticks); **stress 0,10%**. Stress é comparado sobre os **mesmos planos do cenário base** quando ainda permitidos, nunca diferentes conjuntos com médias incomparáveis.
- Contagem de trades com P&L líquido positivo, não confundir com ganho percentual alavancado ou resultado de uma conta.
- Uma amostra grande de sinais mas pequena de trades executáveis continua inconclusiva. Lucro positivo em um bloco não valida vantagem estatística.

## Não prometer o que não foi medido

- Ausência de snapshots completos do top50 no momento histórico implica **viés de seleção temporal**.
- A corretora não disponibiliza histórico confiável de livro de ofertas, spread e fill pessoal, funding e alterações de contratos para este backtest.
- O replay usa **50 USDT fictícios** por trade para verificar viabilidade, não reproduz automaticamente a banca operacional atual de **1 USDT**. O cenário de 1 USDT requer teste independente antes de equiparar à produção.
- A pesquisa **não altera** `main`, `scan.yml`, Telegram, `scanner-state`, cronjob.org ou a regra live de 5M.

## Execução

`.github/workflows/research-expanded-universe.yml`: um job congela a seleção atual e os demais usam o mesmo arquivo do artefato, com testes offline e arquivos JSON/CSV.
