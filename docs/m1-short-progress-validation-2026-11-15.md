# Nova semana M1: regra de progressão apenas para SHORT

**A hipótese foi rejeitada na amostra nova disponível.** Nos mesmos 29 ativos completos, a regra retirou operações lucrativas e piorou o resultado. A referência sem filtro também foi negativa nesse período, dentro da janela de observação de quatro horas. A validação integral dos 31 ativos não pôde ser concluída.

## Regra e sequência, antes dos resultados novos

O diagnóstico anterior de 25/10 a 07/11 mostrou que exigir progressão do segundo M1 para os dois lados reduzia o retorno total. Ao separar por direção, os SHORTs rejeitados tinham resultado negativo e os LONGs rejeitados tinham resultado positivo. Essa diferença motivou uma hipótese posterior, congelada antes da coleta seguinte:

- LONG permanece exatamente igual.
- SHORT só passa se o segundo M1 fecha no máximo no fechamento do primeiro M1. Igualdade aceita.
- Mesmos dois candles e regra de volume de pelo menos 50%; sem terceiro candle, sem novo horário, sem mudança de stop, alvo, quantidade ou saída.

A hipótese não foi definida a partir dos resultados desta semana. O universo de 31 símbolos, as datas e os critérios de avaliação foram registrados no commit de protocolo antes da primeira coleta. O resultado antigo que motivou essa escolha é exploratório; não foi apresentado como prova da regra específica.

## Período e problema de integridade

**08/11/2026 00h a 15/11/2026 00h, Brasília**, final exclusivo; formações de 08 a 14/11, com até cinco horas adicionais de dados para terminar a observação. É um período posterior e sem sobreposição com a captura M1 anterior. Trata-se de teste histórico, não prospectivo.

A primeira captura trouxe 29 símbolos completos. DASH_USDT e XMR_USDT não constavam no catálogo consultado. Foi tentada uma segunda coleta usando suas especificações preservadas no histórico anterior; os endpoints públicos continuaram retornando zero candles M15 para o intervalo. As duas execuções pararam no critério de 31 símbolos antes de calcular performance.

Antes de examinar resultados, foi registrada uma análise parcial: comparar apenas os mesmos 29 símbolos completos nos dois cenários, excluindo unicamente DASH/XMR por indisponibilidade de dados, sem selecionar por lucro ou perda. O critério original de completude permaneceu não atendido. Uma análise parcial não pode ser promovida como validação completa.

Fontes: [primeira captura 43715498746](https://github.com/VinyRhyu/mexc-futures-scanner/actions/runs/43715498746) e [tentativa de recuperação 43715796546](https://github.com/VinyRhyu/mexc-futures-scanner/actions/runs/43715796546). O ZIP da segunda captura foi validado pelo SHA-256 publicado.

## Comparação parcial nos mesmos 29 ativos

Foram reconstruídas 712 confirmações por formação. Após os critérios financeiros atuais, houve 108 entradas por formação, ou 107 após deduplicar ativo/lado/minuto/stop/alvo. Essas 107 entradas correspondem a 96 combinações distintas de ativo/lado/minuto, portanto não são eventos independentes.

| Resultado | Referência sem filtro | Filtro só para SHORT |
|---|---:|---:|
| Entradas | 107 | 95 |
| TP | 25 | 19 |
| SL | 65 | 60 |
| Ainda abertas após 4h | 17 | 16 |
| TP entre encerradas | 27,78% | 24,05% |
| Soma R encerrada | −23,555R | −27,313R |
| Soma R incluindo marcação das abertas em 4h | −19,932R | −24,625R |
| Fator de lucro das encerradas | 0,638 | 0,545 |

O filtro removeu 12 operações: seis TPs, cinco stops e uma ainda aberta. Essas operações removidas somavam +3,758R encerrados e +4,692R incluindo a marcação da aberta. Assim, a piora não foi apenas redução do número de entradas: retirou um grupo que, nesta semana, tinha resultado positivo.

As 17 abertas do controle ficam fora do percentual de acerto. A marcação em 4h é uma saída hipotética no último fechamento com os mesmos custos; não é realização demonstrada. Manter a observação por mais tempo poderia mudar o desfecho dessas posições, mas não foi feito neste teste e não altera os 65 stops já observados.

## Por direção

| Direção / cenário | Entradas | TP | SL | Abertas | R com marcação |
|---|---:|---:|---:|---:|---:|
| LONG / Referência | 67 | 13 | 39 | 15 | -13.063R |
| LONG / Filtro | 67 | 13 | 39 | 15 | -13.063R |
| SHORT / Referência | 40 | 12 | 26 | 2 | -6.869R |
| SHORT / Filtro | 28 | 6 | 21 | 1 | -11.562R |

As operações LONG ficaram idênticas, conforme a regra. Nos SHORTs, a taxa de TP entre encerradas passou de 31,58% para 22,22%. A hipótese que parecia útil no histórico anterior não se confirmou neste período.

## Decisão

O critério congelado exigia resultado marcado positivo e superior ao controle, fator de lucro maior, pelo menos 20 operações mantidas e pelo menos 10 SHORTs mantidos, além de fonte completa para validação integral. Havia quantidade de operações, mas os critérios de desempenho falharam; a completude também permaneceu pendente. **Não promover o filtro.**

Os resultados não demonstram vantagem consistente da referência nesta amostra e horizonte. Isso exige reavaliar a própria hipótese de rompimento M1 e sua aplicabilidade, com novos períodos e execução realista, antes de continuar refinando regras no mesmo histórico. Não é evidência para aumentar risco ou afirmar que toda estratégia de rompimento seja negativa.

## Método, custos e verificações

- Gerador `m1_volume50_v1` de produção, critérios paper do arquivo atual: RR mínimo 1:1, piso 10x e teto 20x. Referência de saldo 1 USDT por oportunidade independente para os filtros financeiros. Não é carteira de US$ 100 nem a simulação diária com risco conjunto 2%.
- Entrada hipotética na abertura imediatamente seguinte à confirmação; stop/alvo congelados. R usa o risco inicial de cada operação. Somar R de operações sobrepostas não produz ROI de carteira.
- Modelo de custos preservado: entrada ajustada por meio spread de 0,01%, taxa 0,06% por execução e slippage configurado ou dois ticks. Funding zero, livro sintético e especificações atuais de contratos aplicadas retrospectivamente.
- Sem trajetória Fair M1 ou livro histórico para reproduzir liquidação; sem atraso de GitHub, coleta, Telegram ou execução manual. Resultados de pesquisa, não operações reais.
- Candles M1/M15 consistentes para os 29 ativos e todos os arquivos-fonte validados por checksum. Os 20 minutos anteriores aos gatilhos são usados apenas para características conhecidas antes da entrada.
- Seis testes direcionados passaram: cálculo causal e simétrico das características; referência de volume sem os gatilhos; bloqueio de fonte parcial sem a opção explícita de análise parcial; rejeição de símbolos adicionais ausentes e de período incorreto.
- Foram verificadas 108 reconstruções de contexto por prefixo temporal; os resultados do replay foram reconciliados antes da aplicação do filtro. Só a condição de SHORT decide quais referências são mantidas.
- Protocolos, falhas de coleta, alterações de integridade antes dos resultados e dados da comparação estão preservados no JSON adjacente.
- Não houve alteração no bot em produção, no Telegram ou em ordens reais.

```sh
python -m unittest tests.test_m1_trigger_features tests.test_m1_progress_source_guards -q
python -m scripts.audit_m1_short_progress_validation --source SOURCE_DIR --protocol config/audit-m1-short-progress-new-week-2026-11-15.json --allow-known-partial --output results.json
```
