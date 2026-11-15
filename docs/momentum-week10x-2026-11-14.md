# Momentum diário: sete ciclos completos, US$ 100 e margem isolada 10x

Período congelado na solicitação: **06/11/2026 22:00 a 13/11/2026 22:00, Brasília (UTC−3)**. O ciclo seguinte ainda estava aberto e foi excluído. Este relatório simula a estratégia de momentum diário previamente testada; não mede o scanner intradiário de produção.

## Resultado líquido

| Medida | Isolada 10x | Controle 1x |
|---|---:|---:|
| Saldo inicial | US$ 100,00 | US$ 100,00 |
| Saldo final | US$ 100,1289 | US$ 100,0928 |
| Lucro líquido | US$ 0,1289 | US$ 0,0928 |
| Retorno sobre o saldo | +0,1289% | +0,0928% |
| Operações positivas / negativas | 20 / 11 | 20 / 11 |
| Acerto após custos e funding | 64,52% | 64,52% |
| Fator de lucro | 1,230 | 1,156 |
| Maior recuo da curva, marcação Fair H1 | 0,3712% | 0,3394% |
| Liquidações simuladas | 2 | 0 |
| Saídas por prazo de 24 horas | 29 | 31 |
| Saídas por stop | 0 | 0 |
| Taxas de negociação modeladas | US$ 0,05013 | US$ 0,05159 |
| Impacto modelado de execução | US$ 0,03771 | US$ 0,03881 |
| Funding histórico recebido líquido | US$ 0,00170 | US$ 0,00226 |
| Exposição inicial média da carteira por ciclo | US$ 6,2166 | US$ 6,2166 |
| Margem inicial média da carteira por ciclo | US$ 0,6217 | US$ 6,2166 |

As 31 aberturas foram pareadas por ativo e horário: direção, quantidade e preço de entrada iguais. A margem é a soma das posições em cada ciclo, não a média por operação. O lucro pequeno resulta do dimensionamento por risco: mantivemos limite conjunto de 2% do saldo para a perda planejada nos stops, sem usar os US$ 100 inteiros como margem. Arredondamento para lotes mínimos reduziu o risco efetivamente aplicado. Houve 18 descartes por lote mínimo em cada cenário.

## Problema encontrado

**Nas 31 posições de 10x, o stop ficou além do preço estimado de liquidação.** Todas também falhariam na proteção de distância de liquidação de 1,5 vez a distância do stop usada pelo bot. Esta simulação manteve as posições para evidenciar o problema; com essa proteção habilitada, as 31 seriam bloqueadas. Não foram movidos stops nem excluídas operações depois de observar o resultado.

Os stops de 2 ATR diários são amplos para margem isolada 10x. O fato de a semana ter terminado positiva não valida essa combinação. A pequena vantagem observada sobre 1x veio das diferentes trajetórias após as liquidações; não demonstra que a alavancagem melhora a estratégia.

| Posição liquidada | Abertura BRT | Hora final do candle de liquidação BRT | Margem inicial | P&L líquido |
|---|---|---|---:|---:|
| ARB_USDT LONG | 09/11 22:00 | 10/11 14:00 | US$ 0.139730 | US$ -0.140339 |
| TIA_USDT LONG | 12/11 22:00 | 13/11 13:00 | US$ 0.133273 | US$ -0.134051 |

## Resultado por ciclo em 10x

| Início → fim BRT | Operações | P&L líquido US$ | Saldo final US$ |
|---|---:|---:|---:|
| 06/11 22:00 → 07/11 22:00 | 3 | +0.066118 | 100.066118 |
| 07/11 22:00 → 08/11 22:00 | 4 | +0.080513 | 100.146631 |
| 08/11 22:00 → 09/11 22:00 | 4 | -0.013300 | 100.133330 |
| 09/11 22:00 → 10/11 22:00 | 4 | -0.147822 | 99.985509 |
| 10/11 22:00 → 11/11 22:00 | 4 | -0.031610 | 99.953899 |
| 11/11 22:00 → 12/11 22:00 | 5 | +0.192039 | 100.145938 |
| 12/11 22:00 → 13/11 22:00 | 7 | -0.017080 | 100.128858 |

## Regras mantidas e execução

- Universo fixo de 26 ativos atuais, com filtro histórico de liquidez por proxy de volume financeiro das últimas 24h ≥ US$ 5 milhões.
- Ranking de retorno de sete dias: caudas superior/inferior de 20%; LONG apenas com retorno positivo e SHORT apenas com retorno negativo; pesos por slots, sem redistribuir slots vazios.
- Decisão diária às 00:00 UTC, apenas dados fechados; entrada na abertura de 01:00 UTC. Sete verificações de prefixo causal por cenário.
- Stop de 2 × ATR14 diário simples, conhecido no momento da decisão; sem TP fixo ou filtro de risco-retorno baseado em TP. Saída após 24h, stop ou liquidação.
- Limite conjunto de perda planejada de 2% do saldo, incluindo custos de execução do stop; margem isolada 10x fixa e sem reposição automática. A alavancagem não multiplica a quantidade após o limite de risco.
- Preços Last H1 para execução e stops; Fair H1 para liquidação e marcação; taxas e lotes atuais aplicados retrospectivamente. Todos os contratos coletados usavam stopOnlyFair=false.
- Taxa de 0,06% por execução; spread total de 0,02%; slippage por execução igual ao maior entre 0,02% do preço e dois ticks. Os custos de spread/slippage já estão incorporados nos fills e não devem ser subtraídos de novo.
- Funding histórico efetivo, com marcação Fair H1. Verificação de caixa livre suficiente para funding sem consumir a margem isolada.
- Preço de liquidação aproximado pelo preço de entrada, alavancagem e taxas atuais de manutenção/liquidação. Ao tocar o nível, perda conservadora da margem isolada inteira, mais taxa de entrada e funding já acumulado; sem cobrar novamente taxa de saída.
- Se stop Last e liquidação Fair fossem tocados no mesmo candle H1, liquidação teria prioridade e seria marcada ambígua. Nesta amostra houve zero casos ambíguos. A ordem exata intrahora não foi observada.

## Limites e reprodutibilidade

Amostra curta, universo atual com viés de sobrevivência, especificações de contratos e faixas de margem atuais usadas no passado, execução sem livro de ofertas histórico e liquidação aproximada. A curva H1 não captura o maior drawdown intrahora. Os resultados não comprovam rentabilidade futura e não representam ordens reais.

Fonte: [coleta GitHub Actions 43655552665](https://github.com/VinyRhyu/mexc-futures-scanner/actions/runs/43655552665), 26/26 ativos completos, preços Last/Fair H1 e funding; artefato `momentum-week10x-source-2026-11-14` (retenção original de 30 dias). Hashes SHA-256 de cada arquivo-fonte, resultados completos, operações, curva H1 e protocolo estão no JSON adjacente.

Quatro testes direcionados passaram: cálculo do nível de liquidação LONG/SHORT, disparo por Fair e ambiguidade, dimensionamento 1x/10x com mesmo risco e ausência de dupla cobrança na liquidação. Contabilidade final reconciliada com a soma dos P&Ls das operações.

Execução:

```sh
python -m unittest tests.test_momentum_week10x -q
python -m scripts.audit_momentum_week10x --source SOURCE_DIR --protocol config/audit-momentum-week10x-2026-11-14.json --output results.json
```

Configuração e código registrados somente na branch de auditoria. Produção e mensagens do Telegram não foram alteradas.
