# Ranking por força relativa ao BTC — melhora histórica, validação futura pendente

O ranking relativo elevou o ROI líquido simulado de **20,39% para 30,18%** em 184 dias, mantendo risco fixo de 1% por operação. O drawdown máximo observado nas marcações H1 caiu de **9,64% para 7,54%**. Com custos agravados, o ROI passou de **14,22% para 23,70%**. A hipótese passou pelo critério exploratório congelado, mas **ainda falhou no critério temporal original** e não está aprovada para produção.

A fórmula e os critérios foram publicados antes da avaliação no commit [f4dcce7b](https://github.com/VinyRhyu/mexc-futures-scanner/commit/f4dcce7b9edb2a75e797902fe6ca71d300cba6ad). Foi testado um único candidato, sem ajustar parâmetros depois de observar os resultados. Todo o histórico já foi examinado no desenvolvimento anterior: estes resultados não são uma validação independente.

## O que mudou

Somente a ordem dos candidatos elegíveis. O novo escore é:

`direção × (retorno do ativo em 7 dias − retorno do BTC em 7 dias) ÷ (ATR14 diário do ativo / preço do ativo)`

A direção continua vindo do retorno absoluto do ativo, com o filtro BTC7 anterior. O ranking favorece força relativa para LONG e fraqueza relativa para SHORT, ajustadas pela volatilidade do próprio ativo. Os retornos usam o fechamento H1 que termina exatamente na fronteira do sinal diário e o fechamento correspondente sete dias antes. O ATR14 é o mesmo já calculado pelo sinal anterior.

Escores negativos continuam elegíveis; não foi introduzido filtro de desempenho relativo. BTC permanece no universo, com escore relativo zero. Empates mantêm custo de entrada/risco planejado e símbolo como desempate. Os preços da hora de atraso e da hora de execução não influenciam a pontuação.

Universo de 26 ativos, liquidez, regras de lotes e margem, uma posição simultânea, risco fixo de 1% incluindo custos/reserva de funding, alavancagem modelada de 10x, entradas diárias com uma hora de atraso, stops e saída máxima de 24h permaneceram iguais. A saída antecipada por EMA20 rejeitada na pesquisa anterior não foi utilizada. Todas as carteiras foram recalculadas integralmente, incluindo os efeitos do saldo sobre lotes e seleção futura.

## Todos os períodos e custos

Intervalos da fonte em UTC, início inclusivo e fim exclusivo. O final em 16/11 00h UTC corresponde a 15/11 às 21h em Brasília. Cada bloco isolado começa com US$ 100; a carteira contínua mantém o saldo ao longo dos 184 dias. Os intervalos se sobrepõem e não são quatro amostras independentes.

| Período | Ranking atual, base | Relativo BTC, base | Atual, custos agravados | Relativo BTC, custos agravados |
|---|---:|---:|---:|---:|
| 16/05–01/07, 46 dias | +0,63% | **+7,76%** | −0,53% | **+6,50%** |
| 01/07–01/10, 92 dias | **+17,15%** | +14,41% | **+14,70%** | +11,71% |
| 24/10–16/11, 23 dias | +4,19% | **+5,59%** | +3,59% | **+5,00%** |
| Contínuo, 16/05–16/11, 184 dias | +20,39% | **+30,18%** | +14,22% | **+23,70%** |

O bloco de 92 dias piorou em ambos os custos. A melhora contínua não significa melhora em todos os regimes.

| Contínuo, 184 operações por carteira | Atual, base | Relativo BTC, base | Atual, agravados | Relativo BTC, agravados |
|---|---:|---:|---:|---:|
| Saldo final, início US$ 100 | US$ 120,39 | **US$ 130,18** | US$ 114,22 | **US$ 123,70** |
| Drawdown máximo nas marcações H1 | 9,64% | **7,54%** | 10,62% | **7,80%** |
| Operações positivas | 83/184 | 88/184 | 83/184 | 88/184 |
| Fator de lucro | 1,352 | 1,466 | 1,248 | 1,370 |
| Tempo médio por operação | 21,50h | 20,99h | 21,50h | 20,99h |
| Taxas de negociação | US$ 4,30 | US$ 4,68 | US$ 6,80 | US$ 7,41 |
| Funding líquido pago | US$ 0,107 | US$ 0,129 | US$ 0,111 | US$ 0,119 |
| Stops | 41 | 45 | 41 | 45 |
| Liquidações modeladas | 0 | 0 | 0 | 0 |

As taxas aumentaram, mas a melhora líquida permaneceu. A base usa taxa de 0,06% por lado, spread total de 0,02% e slippage de 0,02%; o cenário agravado usa 0,10%, 0,04% e 0,04%, respectivamente, com mínimo de dois ticks na derrapagem.

## Consistência e concentração

No contínuo, o ranking mudou o ativo selecionado em **44 das 184 entradas**, mantendo 140 entradas iguais em ativo, direção e horário, nos dois cenários de custo. As saídas seguiram as mesmas regras. Os 44 casos não foram escolhidos a partir do lucro posterior.

| Mês, carteira contínua | Atual, base | Relativo BTC, base | Atual, agravados | Relativo BTC, agravados |
|---|---:|---:|---:|---:|
| Maio, parcial | +3,17% | +3,56% | +2,72% | +3,05% |
| Junho | −2,46% | +4,05% | −3,17% | +3,35% |
| Julho | −3,50% | **−3,37%** | −4,08% | **−3,78%** |
| Agosto | +4,31% | +3,87% | +3,81% | +2,72% |
| Setembro | +15,96% | +14,28% | +14,28% | +13,14% |
| Outubro | −0,66% | +1,29% | −1,84% | +0,15% |
| Novembro, parcial | +3,18% | +3,97% | +2,81% | +3,72% |

Julho continua negativo. No bloco isolado de 92 dias, a divisão previamente fixada em 1º de setembro deixa o subperíodo julho–agosto em **−0,98% sob custos agravados**. Por isso, o critério temporal original continua reprovado. O critério exploratório não substitui nem afrouxa essa exigência.

Há concentração de resultado: QNT somou **US$ 15,91** de contribuição líquida em cinco operações, frente a US$ 30,18 de lucro líquido total. A maior operação foi um LONG de QNT entre 25/09 às 22h e 26/09 às 22h em Brasília, com US$ 13,67 líquidos. Os 24 candles H1 Last e Fair desse intervalo concordam com o movimento amplo da fonte congelada, mas isso não constitui confirmação independente da cotação ou do fill. O código e os relatórios preservam essa operação e as perdas dos demais ativos; não houve remoção seletiva de outliers.

## Critérios e verificações

O critério exploratório registrado exigia melhora do ROI contínuo em ambos os custos, drawdown contínuo base de até 10%, resultado positivo em cada um dos três períodos isolados em ambos os custos e nenhuma liquidação. **Todos esses itens passaram.** O critério temporal original, que exige também subperíodos positivos, **não passou**.

- **8 carteiras de controle reproduzidas exatamente**, incluindo negócios, curva horária, custos, meses e saldo final, contra os resultados anteriores congelados.
- **366 testes passaram**, incluindo 11 novos sobre a fórmula LONG/SHORT, causalidade, normalização, BTC, escores negativos, desempates e manutenção do risco e das saídas.
- **234 verificações com prefixos do histórico** confirmaram pontuações iguais sem os candles posteriores ao sinal, em nove datas de corte dos três períodos separados.
- Mesmos dados congelados H1 Last/Fair, funding e resoluções M5 anteriores, verificados por SHA256. As ambiguidades de stop/liquidação previamente resolvidas mantiveram a resolução M5; não houve nova liquidação modelada.
- Risco planejado de cada entrada do candidato limitado a 1% do saldo antes da entrada; nenhuma sobreposição de posições ou permanência acima de 24h. O risco realizado pode divergir ligeiramente do planejado devido aos custos e ao preço de saída.

Os [resultados de todas as carteiras](research/momentum-relative-btc-v1-results.json) incluem meses, contribuição por ativo, critérios aprovados/reprovados, concentração, hashes e causalidade. O [registro completo das seleções](research/momentum-relative-btc-v1-selection.csv) inclui todas as entradas, inclusive as iguais, nos quatro períodos e dois cenários de custo.

## Reprodução

A fonte pública congelada e o resultado anterior estão no pacote de evidências já entregue. O resultado anterior deve ter SHA256 `75f8226d6fc4819c9c21bd9b745ebfac3cece8edba8724e2ea203aa154e31e3e`. O protocolo desta hipótese tem SHA256 `69dfcbaa793337bf5a018687bb21f7a75aae4f0baf264bd228b6f2a368c6d115`.

```bash
python -m unittest discover -s tests
python -m scripts.audit_momentum_relative_btc \
  --protocol config/momentum-relative-btc-rank-v1-2026-11-16.json \
  --baseline /caminho/resultado-refinado-anterior.json \
  --intrahour-source /caminho/data/reports/momentum-intrahour-source \
  --data-root /caminho/data/reports \
  --output reports/momentum-relative-btc/results.json \
  --summary-output reports/momentum-relative-btc/summary.json \
  --ledger-output reports/momentum-relative-btc/selection.csv
```

Os hashes continuam obrigatórios mesmo com caminhos portáveis. O resumo publicado acrescenta metadados da verificação e diagnóstico da concentração ao resumo produzido pelo comando. As curvas horárias completas são reconstruídas pelo mesmo comando e seu hash consta no resumo.

## Decisão

**Manter como candidato de pesquisa promissor, sem promover para produção.** O próximo passo é uma validação separada com dados novos e parâmetros congelados. A validação prospectiva de 30 dias já em curso permanece intacta; o resultado desta hipótese não será incorporado retroativamente a ela. Nenhuma nova validação prospectiva foi iniciada nesta etapa.

Todo o trabalho está em `research/momentum-relative-btc-v1`. Produção, estado do scanner e Telegram permaneceram sem alterações. Permanecem os vieses do universo/catálogo atuais, histórico já examinado, fills modelados, liquidação aproximada e drawdown medido apenas em marcações H1.
