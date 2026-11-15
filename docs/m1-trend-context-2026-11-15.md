# Rompimento M1 com volume: resultados por estrutura de 1h e 2h

**Resultado central: exigir alinhamento com a estrutura de 1h e 2h não melhorou esta amostra.** O grupo alinhado teve 2 TPs e 8 stops. Isso não prova que operar contra a tendência seja superior; os grupos direcionais são pequenos, os sinais podem se repetir no mesmo movimento e o resultado contra a estrutura ficou concentrado na segunda semana.

## Fonte e reconstrução

Período: **25/10/2026 00h a 08/11/2026 00h, Brasília**, final exclusivo. Coleta de 31 ativos com candles M1, M15 e H1, preservada no [run 42879077420](https://github.com/VinyRhyu/mexc-futures-scanner/actions/runs/42879077420). Esta é a amostra histórica disponível do modelo M1, não os sete dias do teste de momentum diário.

Foi executado o gerador de produção `m1_volume50_v1`, sem modificar a formação, os dois fechamentos M1, a sustentação de volume de pelo menos 50%, os níveis de TP/SL ou a faixa. Primeiro se reconstruíram as confirmações; depois se classificou o contexto conhecido no momento do segundo fechamento.

Para a avaliação principal, cada confirmação foi avaliada com o arquivo atual `config/default.toml`, em modo paper: RR líquido mínimo 1:1 e alavancagem de 10x a 20x. Usa saldo de referência de US$ 1 por oportunidade independente conforme essa configuração; não há evolução de carteira ou simulação dos US$ 100 do teste diário. O limite planejado por entrada segue o validador do bot, e não o limite conjunto de 2% dos experimentos de momentum.

A compatibilidade foi verificada também com a configuração arquivada da coleta, que tinha RR mínimo 2:1 e piso de alavancagem 1x. As 28 entradas da validação anterior foram reproduzidas com os mesmos desfechos e os mesmos retornos R encerrados. Portanto, o percentual antigo de 56% não é diretamente comparável ao percentual da avaliação principal atual: os critérios financeiros mudaram.

## Critério de tendência, sem adicionar espera

Usa a função de estrutura do próprio bot sobre os últimos 240 candles H1 completos conhecidos no instante da confirmação. H2 é agregado desses candles H1 fechados. A estrutura é ALTA quando os dois últimos topos e os dois últimos fundos confirmados são ascendentes; BAIXA quando ambos são descendentes; caso contrário é INDEFINIDA ou DESCONHECIDA. Cada pivô só passa a ser conhecido após os dois candles seguintes fecharem.

- **A favor:** ambos os tempos apontam ALTA para LONG ou BAIXA para SHORT.
- **Contra:** ambos apontam a direção oposta à operação.
- **Divergentes:** um tempo está a favor e o outro contra.
- **Sem direção clara:** pelo menos um tempo não tem estrutura definida. Isso não prova lateralização nem ausência de tendência real.

Nenhum novo candle é aguardado para classificar o sinal. Não foi criada regra de bloqueio na produção.

## Resultado principal, após remover duplicatas de entrada exata

Foram reconstruídas **1.552 confirmações por formação**, ou **1.435 confirmações** após deduplicar ativo, lado, minuto de sinal, stop e alvo. Destas, 1.312 foram bloqueadas pelo validador financeiro e **123 tiveram entrada hipotética**. Essas 123 correspondem a 102 combinações distintas de ativo/lado/minuto; alvos ou stops diferentes no mesmo minuto continuam sendo operações correlacionadas.

| Contexto | Entradas | TP | SL | Abertas após 4h | TP entre encerradas | Soma R encerradas |
|---|---:|---:|---:|---:|---:|---:|
| Todas | 123 | 49 | 71 | 3 | 40.83% | +16.283R |
| A favor de 1h e 2h | 10 | 2 | 8 | 0 | 20.00% | -4.202R |
| Contra 1h e 2h | 12 | 6 | 4 | 2 | 60.00% | +6.102R |
| 1h e 2h divergentes | 5 | 2 | 3 | 0 | 40.00% | -0.374R |
| Estrutura indefinida em algum tempo | 96 | 39 | 56 | 1 | 41.05% | +14.758R |

Acerto significa TP dividido por TP+SL; as três operações ainda abertas após quatro horas não entram no denominador. R é a perda planejada normalizada de cada posição. A soma de R é descritiva de sinais independentes e não representa dinheiro realizado, ROI de carteira ou retorno de US$ 100. Não há capital, margem ou restrição de posição única compartilhados entre as operações.

Exigir alinhamento total deixaria apenas 10 das 123 entradas: preservaria dois TPs e oito stops, descartando 47 dos 49 TPs da amostra. Os dez sinais alinhados ocorreram em dez combinações distintas de ativo/lado/minuto. Já as 12 entradas contra a estrutura ocorreram em dez combinações distintas, das quais duas continuaram abertas. O tamanho dos grupos não sustenta preferir automaticamente operações contra a tendência.

## Divisão por semana

| Semana BRT | Contexto | Entradas | TP | SL | Abertas | Soma R encerradas |
|---|---|---:|---:|---:|---:|---:|
| 25–31/10 | A favor de 1h e 2h | 4 | 1 | 3 | 0 | -1.930R |
| 25–31/10 | Contra 1h e 2h | 1 | 0 | 1 | 0 | -1.000R |
| 25–31/10 | 1h e 2h divergentes | 1 | 0 | 1 | 0 | -1.000R |
| 25–31/10 | Estrutura indefinida em algum tempo | 60 | 27 | 32 | 1 | +18.906R |
| 01–07/11 | A favor de 1h e 2h | 6 | 1 | 5 | 0 | -2.272R |
| 01–07/11 | Contra 1h e 2h | 11 | 6 | 3 | 2 | +7.102R |
| 01–07/11 | 1h e 2h divergentes | 4 | 2 | 2 | 0 | +0.626R |
| 01–07/11 | Estrutura indefinida em algum tempo | 36 | 12 | 24 | 0 | -4.148R |

O grupo alinhado foi negativo nas duas semanas. O grupo contra a estrutura teve apenas uma entrada na primeira semana, encerrada em stop; a melhora ficou na segunda. Não há estabilidade demonstrada para uma política de operar contra a estrutura.

## Cada tempo separado

| Tempo | Contexto | Entradas | TP | SL | Abertas | Acerto encerradas | Soma R |
|---|---|---:|---:|---:|---:|---:|---:|
| H1 | A favor | 22 | 5 | 17 | 0 | 22.73% | -7.470R |
| H1 | Contra | 33 | 10 | 21 | 2 | 32.26% | -5.371R |
| H1 | Sem estrutura definida | 68 | 34 | 33 | 1 | 50.75% | +29.124R |
| H2 | A favor | 27 | 10 | 16 | 1 | 38.46% | -0.603R |
| H2 | Contra | 39 | 20 | 17 | 2 | 54.05% | +24.443R |
| H2 | Sem estrutura definida | 57 | 19 | 38 | 0 | 33.33% | -7.556R |

Essas divisões são diagnóstico. Não foram usadas para selecionar um filtro vencedor e não constituem validação independente de uma nova estratégia.

## Compatibilidade com as 28 entradas da validação antiga

| Contexto | Entradas | TP | SL | Abertas | Acerto encerradas |
|---|---:|---:|---:|---:|---:|
| A favor de 1h e 2h | 4 | 1 | 3 | 0 | 25.00% |
| Contra 1h e 2h | 2 | 0 | 0 | 2 | — |
| 1h e 2h divergentes | 0 | 0 | 0 | 0 | — |
| Estrutura indefinida em algum tempo | 22 | 13 | 8 | 1 | 61.90% |

A referência antiga totaliza 14 TPs, 11 stops e três abertas, com 56% de TP entre as 25 encerradas. O baixo número de casos alinhados também aparece nessa referência, mas a comparação principal deste relatório usa os critérios financeiros atuais.

## Custos, dados e limites

- Entrada hipotética na abertura M1 imediatamente após a confirmação; livro sintético com spread de 0,02%, taxa de 0,06% por execução e slippage configurado ou dois ticks. Os níveis são congelados antes da entrada e não dependem da tendência classificada.
- Funding zero, conforme a metodologia do replay M1 existente; não foi substituído pelo funding histórico usado no outro experimento diário. Os resultados não reproduzem custos reais da conta.
- Quatro horas de candles M1 após cada entrada para verificar TP/SL. Stop tem prioridade se ambos forem tocados no mesmo minuto; não houve ambiguidade nas 123 entradas principais.
- Não existe preço Fair M1 nem livro histórico nessa captura. A folga da liquidação é verificada pelo validador financeiro na entrada, mas não há reconstrução de liquidações efetivas. Stops usam a trajetória Last M1 da metodologia original.
- A entrada imediata supõe disponibilidade da execução. Não reproduz filas do GitHub Actions, frequência de coleta, atraso do Telegram, mensagens efetivamente entregues ou o que o usuário executou.
- Universo de 31 ativos da captura e especificações de contratos congeladas: não é seleção histórica integral de todos os ativos disponíveis. Sinais sobrepostos e moedas correlacionadas limitam a interpretação estatística.
- Todos os arquivos-fonte tiveram checksum validado. O ZIP recuperado corresponde ao SHA-256 publicado no artefato. As consistências M1/M15 da coleta original foram verificadas no manifesto; o conteúdo bruto é o mesmo.
- Duas verificações unitárias passaram: classificação simétrica dos grupos e impossibilidade de candles H1 futuros alterarem o contexto. Houve 1.552 verificações de prefixo causal na reconstrução, além da reprodução das 28 operações antigas.
- Sem alteração de regras de entrada, parâmetros de produção, Telegram ou ordens reais. O teste não demonstra que análise de tendência seja inútil; mostra que esta definição estrutural não justificou um bloqueio obrigatório nessa amostra.

Protocolo: `config/audit-m1-trend-context-2026-11-15.json`. Resultados, bloqueios, avaliações de contexto, configurações, hashes e registros completos estão no JSON adjacente.

```sh
python -m unittest tests.test_m1_trend_context -q
python -m scripts.audit_m1_trend_context --source SOURCE_DIR --protocol config/audit-m1-trend-context-2026-11-15.json --reference docs/experiments/volume-retention-50.json --output results.json
```
