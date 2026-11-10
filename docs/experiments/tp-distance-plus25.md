# TP com distância25%maior: teste isolado

Período25/10–07/11/2026, Brasília. Mesmas28entradas que passaram na sustentação de50%do volume. [Execução](https://github.com/VinyRhyu/mexc-futures-scanner/actions/runs/42910537795) · [Resultado completo](https://github.com/VinyRhyu/mexc-futures-scanner/actions/runs/42910537795/artifacts/13807530673).

## Definição

O novo TP fica25%mais distante da entrada efetiva hipotética, com tick arredondado para longe. Não é aumento de25%no preço nominal da moeda. SL, entradas, quantidade, custos, janela4h e filtro de volume não mudaram. Não houve proteção no zero.

## Resultado

| Medida | TP original | Distância TP+25% |
| --- | ---: | ---: |
| Entradas | 28 | 28 |
| TP atingido | 14 | 8 |
| SL atingido | 11 | 11 |
| Abertas após4h | 3 | 9 |
| Acerto entre encerradas | 56,0% (14/25) | 42,1% (8/19) |
| R encerradas por TP/SL | +25,42 | +14,86 |
| R incluindo avaliação das abertas no fechamento4h | +26,80 | +29,92 |

Seis TPs originais passaram a permanecer abertos até4h; nenhum virou SL dentro da janela. Os11stops originais continuaram stops.

A soma encerrada não conta as9abertas como perdas ou vitórias. Para evitar comparar apenas resultados já realizados quando um modelo deixa mais posições abertas, foi acrescentada uma avaliação simétrica das abertas, ao último fechamento de4h e com custos hipotéticos de saída, em ambos os modelos. Isso é marcação de valor, não execução observada nem TP atingido.

As28entradas continuam passando no validador financeiro com o alvo novo, mas o experimento principal conserva as quantidades originais para isolar a mudança no alvo.

## Semanas

| Período | R encerradas original | R encerradas novo | R com marcação4h original | R com marcação4h novo |
| --- | ---: | ---: | ---: | ---: |
| 25–31/10 | +19,35 | +6,56 | +20,20 | +21,10 |
| 01–07/11 | +6,07 | +8,29 | +6,60 | +8,83 |

O efeito agregado é uma melhora de aproximadamente3,12R na avaliação total4h, acompanhada de menor frequência de TP e mais posições não resolvidas por TP/SL. Não comprova superioridade futura.

## Conversão simbólica

Se1RrepresentarUS$1fixo por ensaio, a soma encerrada equivale aUS$14,86com TP maior, contraUS$25,42no original. Incluindo avaliação das abertas4h, a comparação passa aUS$29,92contraUS$26,80.

São operações independentes possivelmente sobrepostas; essas conversões não constituem ROI de uma carteira deUS$50. Para a avaliação com abertas, o preço de4h e os custos de saída são hipotéticos.

## Limites

- Única mudança: distância da entrada ao TP multiplicada por1,25, com arredondamento para alvo pelo menos tão distante. Não aumenta preço nominal da moeda em25%.
- Entrada inclui spread hipotético original. TP novo definido no momento da entrada, sem candles futuros. SL, janela4h e seleção de28sinais permanecem iguais.
- Resultados emR usam mesmo risco ao SL e mesmos custos por operação. Custos de saída são calculados no novo preço-alvo. Sem proteção no zero.
- Gate financeiro do novo TP informado separadamente; o resumo principal preserva as28entradas para isolar o efeito do alvo, sem redimensionar a posição.
- Abertas4h não são vitórias nem entram na soma encerrada. Stops primeiro em ambiguidade. Fills/funding/livro mantêm hipóteses anteriores.
- Marcação das abertas informada separadamente, ao fechamento de4h com custos hipotéticos de saída nos dois modelos. Não conta aberta como TP e não é execução observada.
- Mesmo histórico já explorado, sem validação fora da amostra. Sinais sobrepostos: somaR não representa dinheiro ou ROI de uma carteira.
- Aumento fixado antes do teste; não houve busca de outros multiplicadores após resultados. Produção não alterada.

A alteração foi somente experimental e não foi aplicada aos sinais de produção.
