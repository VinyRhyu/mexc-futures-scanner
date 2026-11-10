# Teste único: fechamento no terço favorável

Hipótese fixada antes do teste: segundo candle M1 no terço superior da amplitude para LONG e no inferior para SHORT. Igualdade no limite aceita; amplitude zero rejeitada. Mantidos horário de entrada, TP, SL, faixa, custos e todos os demais critérios. Nenhum candle adicional.

[Execução](https://github.com/VinyRhyu/mexc-futures-scanner/actions/runs/42900746777) · [Resultados e registros](https://github.com/VinyRhyu/mexc-futures-scanner/actions/runs/42900746777/artifacts/13803695090).

## Coleta congelada: 25/10–07/11/2026

| Modelo | Entradas únicas | Alvos | Stops | Abertas após4h | Acerto nas encerradas | R encerradas |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Dois fechamentos M1 | 57 | 18 | 33 | 6 | 35,3% | +14,31 |
| Com filtro do terço | 19 | 5 | 12 | 2 | 29,4% | +1,89 |

O filtro removeu21stops,13alvos e4posições abertas. Eliminou proporcionalmente mais acertos (13/18) que stops (21/33), reduzindo a taxa de acerto e o resultado líquido. O ajuste não deve substituir a referência experimental com estes resultados.

LONG: acerto36,8% →33,3%, R13,16 →3,16. SHORT: acerto30,8% →20,0%, R1,15 →-1,27.

## Checagem em outras datas: não concluída

Foi tentada coleta do período11–24/10/2026, com o mesmo universo de31criptos e regras de contratos congeladas. Nenhum histórico completo de1minuto pôde ser validado: em todos os31casos a coleta retornou histórico insuficiente,1559/1800candles em uma requisição.

Não houve avaliação válida desse período. Os zeros do campo new_period_result do JSON representam ausência de dados completos, não ausência de oportunidades nem resultado de uma estratégia.

Não foram usados históricos incompletos para medir acertos. Não foi feita busca de outro limiar após observar os resultados.

## Limites

- Única mudança: fechamento do segundo candle M1 no terço superior para LONG ou inferior para SHORT; igualdade aceita, amplitude zero rejeitada.
- Sem candle adicional, sem alterar horário de entrada, TP, SL, faixa, custos ou critérios financeiros. O filtro apenas remove operações.
- Coleta congelada anterior validada por checksum. Período11–24/10 não foi usado neste experimento para definir ou ajustar o filtro.
- Mesmo universo e contratos da coleta anterior, com viés de seleção/sobrevivência. Referência1USDT e hipóteses de custos e preenchimentos anteriores.
- SomaR de ensaios possivelmente sobrepostos não representa carteira. Abertas após4h não entram no resultado encerrado.
- Comparação em novo período é histórica e limitada; não garante desempenho futuro. Nenhum limiar foi escolhido após observar os resultados.
- Se houver erros no período novo, os dois métodos usam somente os mesmos símbolos completos e as exclusões ficam explícitas.

São ensaios independentes que podem se sobrepor, não simulação de carteira. A soma em R não é dinheiro realizado. Abertas após4h não entram na soma encerrada. A rotina de produção não foi alterada.
