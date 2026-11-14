# Levantamento: quebra de estrutura M5, reteste e reação — 14/11/2026

Resultado: esta primeira tradução objetiva do padrão não melhorou a seleção.
Não foi promovida ao bot. O método exato do grupo não pode ser reproduzido
pelos prints: período do gráfico e regra de três ondas não foram informados.

## Protocolo fixado antes de executar os resultados

- Mesmos 26 ativos da amostra anterior, mas procurando padrões na série completa,
  sem restringir a pesquisa aos 61 gatilhos do scanner de consolidação.
- Dados M1 com seis horas anteriores para aquecer ATR e pivôs M5. Sinais de
  14/11 00:00 até 17:15:04 BRT; preços até 17:17 BRT.
- Pivôs M5 com dois vizinhos à esquerda e dois à direita. Cada pivô só fica
  disponível depois do fechamento dos dois vizinhos direitos, antes do candle
  de rompimento. Último pivô com até duas horas desde sua confirmação.
- Rompimento por fechamento além do pivô +0,10 ATR14, usando ATR do candle M5
  anterior. Cada pivô/lado gera no máximo um rompimento. Não se exige tendência
  oposta anterior: pode detectar continuação ou reversão local.
- Reteste em candle M5 posterior ao rompimento, em até seis candles/30 minutos,
  tocando faixa de +/-0,20 ATR e fechando novamente no lado do rompimento.
  Fechamento além da borda contrária cancela a preparação. Um plano pendente
  por lado/ativo; preparações existentes não são substituídas por novos rompimentos.
- Stop além do extremo dos candles de espera após o rompimento, incluindo a
  reação, com buffer de 0,10 ATR. Alvo é o extremo do impulso entre o rompimento
  e o candle ANTERIOR à reação. Tudo fica definido antes da entrada.
- Faixa de entrada: fechamento da reação +/-0,25 ATR, sujeita ao estreitamento
  financeiro. Entrada na abertura M1 seguinte ou com atraso de 60s; validade
  para nova entrada de 120s. Toque em TP/SL durante a espera cancela entrada.
- Mesmos custos e regras financeiras da comparação anterior: saldo referencial
  US$1, risco até 10%, RR líquido mínimo 1:1, piso 10x/teto 20x, taxa de 0,06%
  por lado, spread sintético de 0,02%, slippage de 0,02% ou dois ticks,
  funding zero, parâmetros públicos dos contratos coletados no mesmo dia.
- Sem RSI, TOTAL3, retração de 50%, regra de três ondas ou filtro H1.

## Resultado no período completo

| Modelo / atraso | Padrões candidatos | Entradas | TP | SL | Soma R independente |
| --- | ---: | ---: | ---: | ---: | ---: |
| Scanner anterior, imediato | 61 | 12 | 2 | 10 | -7,70R |
| Estrutura + reteste, imediato | 264 | 2 | 0 | 2 | -2,00R |
| Scanner anterior, +60s | 61 | 8 | 1 | 7 | -5,86R |
| Estrutura + reteste, +60s | 264 | 1 | 0 | 1 | -1,00R |

Todas as entradas aceitas tiveram desfecho no recorte disponível. A menor perda
total do novo modelo decorre de operar muito menos; o R médio por entrada
aceita foi -1R nos dois atrasos. Não demonstra melhora na seleção.

## Comparação com quatro horas completas disponíveis

Para evitar favorecer operações recentes ainda abertas, também foram comparados
somente sinais até 13:17 BRT, com quatro horas de acompanhamento potencial:

| Modelo / atraso | Entradas | TP | SL | Soma R independente |
| --- | ---: | ---: | ---: | ---: |
| Scanner anterior, imediato | 8 | 2 | 6 | -3,70R |
| Estrutura + reteste, imediato | 1 | 0 | 1 | -1,00R |
| Scanner anterior, +60s | 5 | 1 | 4 | -2,86R |
| Estrutura + reteste, +60s | 0 | 0 | 0 | 0R |

## Diagnóstico do alvo e dos bloqueios

Dos 264 padrões no cenário imediato:

- 214 foram bloqueados por retorno/risco: 60 sem geometria válida mesmo no
  melhor preço da faixa; 52 com ganho até o TP insuficiente para os custos;
  102 com ganho líquido positivo, mas inferior à perda planejada.
- 44 foram bloqueados pelo limite relativo de custos, 3 por preço fora da
  faixa e 1 por lote mínimo/risco. Os outros 2 foram aceitos e atingiram SL.
- Distância mediana do TP à referência da reação: 0,163% do preço, próxima
  da soma aproximada de taxas e slippage de 0,16% antes do piso de dois ticks.
- Em 63 padrões, o alvo local já estava no lado errado do fechamento da reação.
  A avaliação financeira impediu a entrada. Esse diagnóstico mede a referência
  da reação; não equivale aos 60 casos de geometria inválida no melhor preço
  possível da faixa de entrada.

Entradas imediatas: HYPE LONG 12:25, stop no candle 12:39-12:40;
INJ LONG 14:55, stop no candle 15:04-15:05. Com 60s, apenas INJ foi aceito.

Nesta formulação, o alvo local frequentemente ficou perto demais depois da
reação. Isso não prova que o padrão discricionário do grupo não funcione; mostra
que este alvo e este período M5, com os custos mantidos, não sustentaram uma
vantagem no dia auditado. Não houve ajuste posterior de TP ou busca de períodos
até obter resultado positivo.

## Integridade e limites

- 26.962 candles M1 coincidiram exatamente com a coleta usada nos testes anteriores.
- 52 verificações de prefixo temporal passaram: incluir candles futuros não
  muda os padrões e níveis que já deveriam estar definidos às 07h e 12h.
- Cinco testes verificaram separação entre rompimento e reteste, alvo conhecido
  antes da reação, invalidação, prazo e simetria SHORT/LONG.
- Um único dia já examinado: resultado exploratório, sem validação fora da amostra.
- Livro/spread sintéticos e funding zero: preenchimentos históricos não comprovados.
- Atraso zero é idealizado. Resultados são planos independentes, podem se
  sobrepor e não representam execução de uma carteira.
- Main e Telegram permaneceram inalterados.

## Fontes e reprodução

Coleta M1 com aquecimento: execução 43650715883, artefato
structure-retest-source-2026-11-14. Parâmetros de contrato: execução 43639547648.
M1 anterior: execução 43636700606. Baseline congelada:
config/audit-day-confirmed-2026-11-14.json. Protocolo:
config/audit-structure-retest-2026-11-14.json.

```sh
python -m unittest tests.test_structure_retest_day -q
python -m scripts.audit_structure_retest_day --protocol config/audit-structure-retest-2026-11-14.json --source /pasta/m1-com-aquecimento --contracts /pasta/contracts.json --baseline config/audit-day-confirmed-2026-11-14.json --old-minute /pasta/m1-anterior --config config/default.toml --output /tmp/retest-results.json
```
