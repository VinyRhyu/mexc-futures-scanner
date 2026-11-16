# Momentum: coleta ampliada, resolução intrahora e redução de risco

Atualização de 16/11/2026. **A publicação e as coletas autorizadas foram executadas. O protótipo com proteção automática teve retorno líquido de +12,93% e queda máxima H1 de 7,94% na carteira contínua de 184 dias.** Com custos elevados, +9,99% e queda de 8,48%. Essa melhora atende à triagem de risco registrada para este histórico; ainda não comprova desempenho em dados futuros nem satisfaz a antiga exigência de todos os subperíodos positivos.

## Dados efetivamente obtidos

- [Coleta Last/Fair/funding concluída](https://github.com/VinyRhyu/mexc-futures-scanner/actions/runs/43867049880): 26/26 contratos completos, 4.776 candles H1 Last e 4.776 Fair por contrato, sem erros. Abrange 30/04 às 21h a 15/11 às 21h de Brasília; primeiros dias usados como aquecimento.
- [Primeira tentativa M1](https://github.com/VinyRhyu/mexc-futures-scanner/actions/runs/43868816323): histórico incompleto para as duas horas antigas; falhou explicitamente. Nenhum dado foi inventado.
- [Coleta intrahora concluída](https://github.com/VinyRhyu/mexc-futures-scanner/actions/runs/43869203294): M5 completo para as duas horas. A ordem de consulta M1 → M5 → M15 foi fixada antes desta nova consulta. Escolheu-se a menor granularidade completa com OHLC exatamente igual ao H1 congelado, sem escolher pela rentabilidade.

Todos os hashes de arquivos, protocolos e artefatos foram conferidos. O universo permaneceu nos mesmos 26 ativos. Os Last históricos e as taxas de funding coincidiram com os arquivos anteriores no intervalo comum. Foram identificadas atualizações em faixas de margem de PEPE e WLD; uma comparação separada, mantendo os contratos antigos e trocando somente Fair, isolou essa mudança. A introdução de Fair, por si, alterou pouco os retornos anteriores; não explica o desempenho negativo de alguns meses.

## Carteira contínua de 184 dias

De **15/05/2026 às 21h até 15/11/2026 às 21h, Brasília**, equivalente a 16/05–16/11 UTC. Saldo inicial US$ 100, alavancagem 10× e uma posição global por vez. Saldo não reinicia nas divisões mensais. Houve 184 operações por configuração.

| Configuração | Saldo final US$ | Retorno líquido | Queda máxima H1 | Retorno sob custos altos | Queda sob custos altos |
| --- | ---: | ---: | ---: | ---: | ---: |
| Sem alinhamento ao Bitcoin, risco 2% | 149,87 | 49,87% | 35,66% | 34,23% | 36,85% |
| Alinhado ao Bitcoin, risco 2% | 137,92 | 37,92% | 20,81% | 25,87% | 22,54% |
| Alinhado ao Bitcoin, risco 1% | 120,39 | 20,39% | 9,64% | 14,22% | 10,62% |
| Alinhado ao Bitcoin, proteção automática | 112,93 | 12,93% | 7,94% | 9,99% | 8,48% |

O modelo sem alinhamento produziu maior retorno, mas com perda desde o pico muito maior. O risco fixo de 1% melhorou o equilíbrio, porém ultrapassou por pouco o teto de 10% de queda no cenário de custos elevados. A proteção automática permaneceu abaixo de 10% nos dois cenários desse histórico. Essa constatação não é uma garantia de perda máxima.

A taxa-base continua sendo uma hipótese de 0,06% por execução, spread total de 0,02% e slippage de 0,02% ou dois ticks, o que for maior. No cenário elevado: 0,10%, 0,04% e 0,04% ou dois ticks, respectivamente. Todas as carteiras foram novamente dimensionadas e selecionadas com esses custos; não se aplicou uma subtração fixa de taxas sobre os mesmos trades. As taxas pessoais da conta continuam não verificadas.

## Proteção automática implementada

A regra técnica de momentum ficou congelada: retorno de sete dias, direção concordante com o Bitcoin, classificação por força normalizada por ATR, liquidez mínima estimada, uma hora de atraso, stops e prazo de 24h mantidos. A mudança é exclusivamente no risco das novas posições:

1. Risco planejado normal de até 2% do patrimônio disponível, incluindo custos e reserva de funding conhecida.
2. Se a curva marcada no último fechamento H1 cair 5% desde seu maior valor conhecido, reduzir o risco para 0,5% nas novas posições.
3. Restaurar o risco de 2% somente quando a queda desde o pico recuar a 2,5% ou menos.
4. A política não altera posições retrospectivamente e não usa recuperação futura para decidir o tamanho atual.

Os limiares 5%/2,5% e os riscos 2%/0,5% foram registrados antes do teste dessa política. Também foi testado o risco fixo de 1%, sem varrer dezenas de alternativas. A política usa patrimônio e máximas já observados; não utiliza o resultado futuro da operação para ligar ou desligar a proteção.

## Por que os números mudaram após a inspeção intrahora

O modelo H1 dava prioridade conservadora à liquidação quando stop e preço de liquidação eram tocados na mesma hora. As duas horas eram de WLD e ARB. A fonte M5 reconstituiu exatamente os OHLC Last e Fair congelados e mostrou o stop em um candle anterior ao toque de liquidação. As carteiras foram refeitas integralmente, incluindo quantidades, saldo, ranking e estados da proteção depois desses eventos. As 32 carteiras H1 originais foram reproduzidas antes dessa mudança de resolução.

| Modelo alinhado | Retorno H1 conservador | Retorno após resolução M5 |
| --- | ---: | ---: |
| Risco 2% | +32,53% | +37,92% |
| Risco 1% | +18,14% | +20,39% |
| Proteção automática | +11,97% | +12,93% |

Não houve liquidações no replay refinado nem novas horas de liquidação sem resolução. Isso descreve o resultado do modelo, não uma garantia de que um stop real seria preenchido. Se stop e liquidação fossem tocados no mesmo candle M5, a prioridade conservadora de liquidação seria preservada. Fora dessas duas horas, a trajetória continua em H1; a queda máxima apresentada é amostrada em H1, sem capturar todos os extremos intrahora.

## Recorte recente ampliado

De 23/10 às 21h a 15/11 às 21h, Brasília, 23 dias, com saldo reiniciado em US$ 100 para comparar esse recorte. Não é o mesmo início da carteira contínua de seis meses; o estado da proteção e as quantidades podem divergir.

| Modelo | Retorno líquido | Retorno com custos altos |
| --- | ---: | ---: |
| Sem alinhamento | +3,81% | +2,64% |
| Alinhado, risco 2% | +8,94% | +7,57% |
| Alinhado, risco 1% | +4,19% | +3,59% |
| Alinhado, proteção automática | +8,94% | +7,57% |

## Consistência e limites preservados

A proteção automática ainda teve meses negativos: julho −1,49% e outubro −0,29% na carteira contínua base. Os percentuais mensais são definidos em UTC para reprodução; maio e novembro são parciais. O critério anterior de todos os subperíodos positivos continua reprovado e não foi relaxado. A triagem de risco desta política é uma avaliação adicional, explicitamente identificada, não uma substituição silenciosa do critério anterior.

As datas antigas ainda não examinadas por este experimento são anteriores ao desenvolvimento da estratégia. Essa verificação é retrospectiva, não validação prospectiva. O universo tem viés de sobrevivência e regras de contratos atuais aplicadas ao passado. Faltam livro histórico de ofertas, fila das ordens, taxas efetivas da conta e execução real observável. Houve seleção adaptativa entre estratégias e políticas; não foram calculadas significância após seleção ou probabilidade de lucro futuro.

**Candidata preservada para avaliação em simulação:** momentum alinhado ao Bitcoin com proteção automática. As alternativas, os resultados negativos anteriores e o risco fixo de 1% permanecem registrados. Não houve alteração em main, scanner-state, parâmetros do bot ou Telegram, nem execução de ordens reais.

## Verificação e reprodução

355 testes passaram, incluindo funding conhecido versus futuro, caixa, lotes, LONG/SHORT, gap, histerese do controle de risco, prioridade de eventos e rejeição de dados intrahora incoerentes. As 32 carteiras H1 foram reproduzidas exatamente antes do refinamento; todos os replays finais reconciliaram saldo e fluxos, sem sobreposição de posições.

O pacote de evidências contém os dados e os três estágios completos de resultados. A fonte e os protocolos estão nesta branch. Após extrair o pacote, da raiz do projeto:

```bash
python -m unittest discover -s tests
python -m scripts.audit_momentum_intrahour \
  --protocol config/momentum-intrahour-evaluation-v1-2026-11-16.json \
  --data-root DATA/data \
  --intrahour-source DATA/data/reports/momentum-intrahour-source \
  --parent DATA/results/expanded.json \
  --allocation-parent DATA/results/allocation.json \
  --output reports/reproducao-refinada.json
```

`DATA` é a pasta onde o pacote de evidências foi extraído. A rotina é somente de pesquisa: não acessa negociação, conta ou notificações. Os diretórios de dados podem mudar; os hashes e os parâmetros congelados permanecem os mesmos.
