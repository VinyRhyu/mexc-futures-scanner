# Diagnóstico de entradas e saídas: momentum diário em 10x

**US$ 100 iniciais, margem isolada 10x, risco conjunto planejado máximo de 2% por ciclo diário. Período: 06/11/2026 22h → 13/11/2026 22h, Brasília.** Usa a variante com stop limitado para ficar antes da liquidação estimada, já testada anteriormente. Não representa o scanner intradiário em produção.

## Única alteração testada: saída por prazo de 6 horas

| Resultado | Até 24h, controle | Até 6h, variante |
|---|---:|---:|
| Saldo final | US$ 100,6691 | US$ 100,0215 |
| Retorno líquido | +0,6691% | +0,0215% |
| Operações | 35 | 35 |
| Positivas / negativas | 24 / 11 | 22 / 13 |
| Acerto | 68,57% | 62,86% |
| Fator de lucro | 1,369 | 1,020 |
| Maior recuo da curva H1 Fair | 0,9535% | 0,4676% |
| Stops / saídas por prazo | 6 / 29 | 2 / 33 |
| Liquidações simuladas | 0 | 0 |

**Encerrar todas as operações em seis horas piorou o retorno nesta amostra.** Reduziu o recuo da curva, mas cortou parte dos ganhos posteriores. A regra de seis horas foi registrada antes de calcular estes novos diagnósticos e resultados; não houve busca pelo melhor prazo.

Entradas diárias de 01:00 UTC e seleção permanecem iguais. Stop, alavancagem, limite de risco, custos e funding são os mesmos. A margem liberada fica ociosa até a próxima entrada diária; não há operações adicionais. Há 35 aberturas comuns entre os cenários. Em 33 delas as quantidades foram idênticas; em duas mudaram por arredondamento de lotes após a diferença no saldo. A variante recalcula o tamanho por risco a cada ciclo, sem simplesmente multiplicar os resultados. A última saída da variante ocorre 18 horas antes da do controle, com saldo ocioso no restante da janela.

## Onde as operações perderam qualidade

### Lucro devolvido

- Das 11 operações perdedoras do controle, **cinco apresentaram lucro líquido positivo em pelo menos um fechamento H1 anterior à saída**; seis não apresentaram fechamento H1 positivo observado.
- As mesmas cinco chegaram a pelo menos **+10% líquido sobre a margem da posição** em fechamento H1; quatro chegaram a 20% e uma a 30%. Esses percentuais são sobre a margem alocada, não sobre os US$100 totais.
- Cinco perdedoras chegaram a 0,25R líquido em fechamento H1; uma chegou a 0,5R; nenhuma a 1R. R é a perda planejada em dólares no stop, incluindo custos.
- Essas cinco terminaram somando−US$0,473284. Os seis demais resultados negativos somaram −US$ 1,340543.
- Seis das 24 operações positivas terminaram com metade ou menos do seu melhor lucro líquido observado em um fechamento H1.
- A mediana do horário do melhor fechamento H1 positivo foi 16 horas após a entrada. Somente quatro das 35 operações tiveram seu melhor fechamento H1 positivo dentro das primeiras seis horas. Isso ajuda a explicar por que a saída geral em 6h reduziu o retorno.

“Melhor fechamento” é medido depois de conhecer o caminho. Não havia sinal causal para vender exatamente naquele ponto. A soma desses picos individuais seria US$ 4,584248, contra o lucro final de US$ 0,669073; essa diferença não é um lucro recuperável demonstrado nem uma nova estratégia. Os picos ocorrem em horários diferentes e foram escolhidos retrospectivamente.

### Direção das entradas

| Direção | Operações | Positivas / negativas | P&L líquido | Stops |
|---|---:|---:|---:|---:|
| LONG | 11 | 4 / 7 | −US$ 1,417190 | 6 |
| SHORT | 24 | 20 / 4 | +US$ 2,086263 | 0 |

**Os seis stops foram LONG.** Nesta semana, as compras consumiram boa parte do resultado das vendas. Isso sugere investigar o contexto das compras e as reversões depois de força anterior de sete dias. Não autoriza eliminar todos os LONGs: essa decisão usaria o resultado desta semana para construir um filtro ajustado ao passado.

### Atraso da entrada

Entre os 11 resultados negativos, sete já vinham de um movimento favorável nas seis horas anteriores à entrada. Porém, isso também ocorreu em 14 dos 24 resultados positivos. Essa característica isolada não separou bem os grupos: 63,64% das perdedoras contra 58,33% das vencedoras.

Em oito das 11 perdedoras, o preço estava contra a direção da entrada no fechamento de seis horas depois. É uma descrição posterior do caminho, não uma informação disponível na entrada. Alguns desses preços são posteriores ao stop e não representam retorno mantido em posição.

A observação do movimento prévio não demonstra que havia um gatilho válido mais cedo. Este teste não valida antecipar entradas nem afirma que os sinais estão atrasados em geral.

## As 11 operações negativas do controle

| Abertura BRT | Ativo / direção | Saída | P&L líquido US$ | Melhor ROI líquido H1 sobre margem | Melhor lucro H1 em R |
|---|---|---|---:|---:|---:|
| 07/11 22:00 | UNI_USDT LONG | STOP | -0.262821 | 0.00% | 0.000 |
| 08/11 22:00 | ENA_USDT SHORT | TIME | -0.039272 | 35.67% | 0.581 |
| 08/11 22:00 | TIA_USDT SHORT | TIME | -0.080516 | 27.62% | 0.439 |
| 08/11 22:00 | WLD_USDT SHORT | TIME | -0.015928 | 18.81% | 0.298 |
| 09/11 22:00 | AAVE_USDT LONG | STOP | -0.242780 | 0.00% | 0.000 |
| 09/11 22:00 | ARB_USDT LONG | STOP | -0.246550 | 0.00% | 0.000 |
| 10/11 22:00 | ARB_USDT LONG | STOP | -0.277065 | 29.78% | 0.485 |
| 10/11 22:00 | XRP_USDT SHORT | TIME | -0.031350 | 0.00% | 0.000 |
| 12/11 22:00 | AVAX_USDT LONG | TIME | -0.060503 | 25.02% | 0.407 |
| 12/11 22:00 | FET_USDT LONG | STOP | -0.278193 | 0.00% | 0.000 |
| 12/11 22:00 | TIA_USDT LONG | STOP | -0.278851 | 0.00% | 0.000 |

## Método e verificações

- Controle de 24h reproduzido de forma idêntica ao teste anterior em resumo, dias, operações, curva H1, descartes e sete verificações causais.
- Doze testes direcionados passaram, incluindo proteção contra usar o lucro máximo do candle do stop, não usar funding futuro num lucro anterior, extremos de SHORT, tratamento de gap no stop e manutenção do tamanho inicial ao reduzir o prazo.
- MFE/MAE de preço usam extremos Last H1. No candle que contém stop, seu máximo favorável é apenas limite superior de oportunidade incerta; não conta como lucro observado antes do stop. MAE inclui o preço modelado da saída e pode omitir os extremos dentro da hora do stop.
- Melhor lucro líquido H1 considera somente candles completos anteriores à hora do stop ou até a saída por prazo; custos de entrada e saída, spread/slippage e funding até aquele instante. Não considera funding posterior.
- “Não mostrou lucro” significa que não houve fechamento H1 positivo observado antes da saída. Não exclui lucro intrahora.
- Stop permanece a menor distância entre2ATR14 diário e a distância estimada da liquidação/1,6, com verificação de folga mínima 1,5. Margem isolada sem reposição automática.
- Taxa de negociação 0,06% por execução; spread total 0,02%; slippage por execução = max(0,02% do preço, dois ticks). Funding histórico e marcação Fair H1. Execução e liquidação são estimativas.
- Universo fixo de 26 ativos sobreviventes atuais, especificações atuais de contratos, lotes e margem aplicadas retrospectivamente. Semana já observada: comparação exploratória, sem validação independente.
- Código e relatório somente na branch de auditoria. Produção, Telegram e ordens reais não foram alterados.

Fonte: [coleta 43655552665](https://github.com/VinyRhyu/mexc-futures-scanner/actions/runs/43655552665), mesma usada nos dois testes anteriores. Protocolo em `config/audit-momentum-entry-exit-2026-11-14.json`; resultados completos, trajetórias H1 e hashes dos arquivos-fonte no JSON adjacente.

```sh
python -m unittest tests.test_momentum_week10x tests.test_momentum_risk_ladder tests.test_momentum_entry_exit -q
python -m scripts.audit_momentum_entry_exit --source SOURCE_DIR --protocol config/audit-momentum-entry-exit-2026-11-14.json --baseline RISK_LADDER_RESULTS --output results.json
```
