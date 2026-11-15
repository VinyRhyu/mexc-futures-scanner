# Um filtro de contexto para LONG: fechamento H1 acima da EMA20

**Conclusão: a melhora foi pequena no período anterior de 14 dias.** A regra melhorou mais a semana que motivou a hipótese, mas esse resultado isolado não demonstra um filtro consistente para evitar stops. Nenhuma alteração em produção.

## Regra congelada antes de calcular os resultados

Permitir LONG apenas se o último fechamento H1 completo estiver **estritamente acima da EMA20 H1** no momento original da decisão diária, às 00:00 UTC. SHORT permanece permitido pela regra anterior, sem este filtro. Não exige inclinação da média nem candle adicional.

EMA20 calculada recursivamente em ordem temporal, semente pela média simples dos primeiros 20 fechamentos H1 disponíveis, fator 2/21. Somente candles com fim≤decisão. O horário de entrada continua 01:00 UTC.

A carteira completa é dimensionada antes do filtro: US$ 100 iniciais, margem isolada 10x, risco planejado máximo conjunto 2%, stop limitado à distância da liquidação estimada/1,6 quando o stop 2 ATR seria mais distante, saída em até 24h. O orçamento dos LONGs rejeitados fica em caixa, sem redistribuir risco ou margem às demais posições. Cada cenário recalcula seus lotes a partir do próprio saldo ao longo dos dias.

Foi testado apenas esse filtro, sem comparar múltiplos períodos de EMA, inclinações, prazos ou outros indicadores.

## Verificação principal: 14 dias anteriores

**23/10/2026 22h → 06/11/2026 22h, Brasília (UTC−3)**. Não se sobrepõe à semana usada para diagnosticar as perdas. Os preços já estavam na coleta para aquecimento dos indicadores; a performance dessa regra nesse intervalo não havia sido calculada. Trata-se de verificação retrospectiva, não de teste prospectivo.

| Resultado | Sem filtro | Com filtro |
|---|---:|---:|
| Saldo final | US$ 101,1632 | US$ 101,2064 |
| Retorno líquido | +1,1632% | +1,2064% |
| Operações | 79 | 73 |
| Positivas / negativas | 39 / 40 | 36 / 37 |
| Acerto | 49,37% | 49,32% |
| Fator de lucro | 1,300 | 1,317 |
| Maior recuo da curva Fair H1 | 1,3785% | 1,3785% |
| Stops | 13 | 13 |
| Liquidações simuladas | 0 | 0 |

O ganho adicional foi de **US$ 0,043153**, aproximadamente quatro centavos numa conta de US$ 100, ou 0,0432 ponto percentual. O filtro retirou seis operações do controle: três positivas e três negativas; nenhuma delas era stop. **Não evitou nenhum dos 13 stops** nesse período. A taxa de acerto e o maior recuo praticamente não mudaram.

### Separação LONG/SHORT nos 14 dias

| Grupo | Sem filtro: operações / P&L | Com filtro: operações / P&L |
|---|---:|---:|
| LONG | 21 / −US$ 0,228772 | 15 / −US$ 0,185619 |
| SHORT | 58 / +US$1,392015 | 58 / +US$1,392015 |

Os LONGs permaneceram negativos. O resultado é compatível com uma pequena redução de exposição a algumas entradas ruins, mas não comprova discriminação útil entre os LONGs que acabariam em stop e os demais.

## Semana conhecida: análise explicativa

**06/11/2026 22h → 13/11/2026 22h, Brasília.** Esta semana gerou a hipótese; não conta como validação independente.

| Resultado | Sem filtro | Com filtro |
|---|---:|---:|
| Saldo final | US$ 100,6691 | US$ 101,3426 |
| Retorno líquido | +0,6691% | +1,3426% |
| Operações | 35 | 29 |
| Positivas / negativas | 24 / 11 | 22 / 7 |
| Acerto | 68,57% | 75,86% |
| Fator de lucro | 1,369 | 2,360 |
| Maior recuo da curva Fair H1 | 0,9535% | 0,8985% |
| Stops | 6 | 3 |
| Liquidações simuladas | 0 | 0 |

Aqui, o filtro retirou seis operações do controle, incluindo quatro negativas e duas positivas; três negativas foram stops. O P&L das posições removidas, nas quantidades originais, era −US$ 0,667444. O efeito final foi ligeiramente diferente porque o saldo preservado alterou alguns lotes nas operações posteriores. As regras de SHORT são iguais, mas seu tamanho pode mudar com o saldo.

**A diferença entre os períodos é o resultado central.** Olhar apenas a semana conhecida faria a regra parecer mais convincente do que a verificação anterior sustenta. O teste não autoriza excluir todas as compras nem levar este filtro à produção.

## LONGs rejeitados, com resultado das posições originais

| Período | Abertura BRT | Ativo | Resultado original | P&L líquido US$ |
|---|---|---|---|---:|
| 14 dias anteriores | 23/10 22:00 | ENA_USDT | TIME | +0.000120 |
| 14 dias anteriores | 26/10 22:00 | ENA_USDT | TIME | +0.004687 |
| 14 dias anteriores | 27/10 22:00 | QNT_USDT | TIME | -0.008170 |
| 14 dias anteriores | 05/11 22:00 | AAVE_USDT | TIME | -0.020945 |
| 14 dias anteriores | 05/11 22:00 | QNT_USDT | TIME | +0.021068 |
| 14 dias anteriores | 05/11 22:00 | UNI_USDT | TIME | -0.039913 |
| Semana conhecida | 06/11 22:00 | ARB_USDT | TIME | +0.063280 |
| Semana conhecida | 08/11 22:00 | ARB_USDT | TIME | +0.096174 |
| Semana conhecida | 09/11 22:00 | AAVE_USDT | STOP | -0.242780 |
| Semana conhecida | 09/11 22:00 | ARB_USDT | STOP | -0.246550 |
| Semana conhecida | 10/11 22:00 | ARB_USDT | STOP | -0.277065 |
| Semana conhecida | 12/11 22:00 | AVAX_USDT | TIME | -0.060503 |

## Verificações e limites

- Os 15 testes direcionados passaram, incluindo EMA sem leitura do candle aberto/futuro, filtro restrito a LONG e ausência de redistribuição para SHORT.
- A reprodução da semana conhecida sem filtro foi idêntica ao controle anterior em todos os campos de resumo, operações, dias, curva H1, descartes e verificações causais.
- Foram verificadas 79 avaliações de contexto no período anterior e 35 na semana conhecida: retirar os dados posteriores à decisão não altera a EMA ou o resultado do filtro. A seleção de momentum também manteve as verificações causais por dia.
- Históricos de funding cobrem os dois períodos para 26/26 ativos. A coleta contém preços Last/Fair H1 e aquecimento a partir de 08/10/2026; os 14 dias anteriores têm pelo menos 15 dias completos anteriores para o contexto diário.
- Custos iguais aos testes anteriores: taxa 0,06% por execução, spread total 0,02%, slippage por execução = max(0,02% do preço, dois ticks), funding histórico. Retornos já incluem os custos considerados.
- Universo atual com viés de sobrevivência; especificações atuais de contratos, lotes e margem aplicadas retrospectivamente. Liquidação e execução são estimadas; a curva H1 não captura o pior movimento intrahora.
- Fonte original: [coleta 43655552665](https://github.com/VinyRhyu/mexc-futures-scanner/actions/runs/43655552665). Hashes dos arquivos-fonte, protocolo, operações, avaliações da EMA e curvas H1 constam no JSON adjacente.
- Sem ordens reais, alterações no Telegram ou no scanner de produção.

```sh
python -m unittest tests.test_momentum_week10x tests.test_momentum_risk_ladder tests.test_momentum_entry_exit tests.test_momentum_long_context -q
python -m scripts.audit_momentum_long_context --source SOURCE_DIR --protocol config/audit-momentum-long-context-2026-11-14.json --baseline RISK_LADDER_RESULTS --output results.json
```
