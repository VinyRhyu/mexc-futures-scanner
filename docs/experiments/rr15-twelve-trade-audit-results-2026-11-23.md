# Resultado: auditoria das 12 operações RR líquido projetado >=1,5

Data: 23/11/2026. [PR #14](https://github.com/VinyRhyu/mexc-futures-scanner/pull/14) em rascunho. Execução GitHub Actions [#45181469206](https://github.com/VinyRhyu/mexc-futures-scanner/actions/runs/45181469206): **dois jobs SUCCESS**, todos os 24 símbolos com histórico completo em cada período, testes de causalidade e invariantes de resultado aprovados. Relatórios completos `rr15_1usdt_selected_ledger.csv` e `rr15_1usdt_summary.json` estão nos dois artifacts do workflow.

## Resultado reproduzido, na ordem real dos sinais

Os horários a seguir são de **Brasília (UTC-3)**. Entrada é estimativa do fill sintético na próxima abertura M1; TP e SL são níveis técnicos; `R` é resultado normalizado líquido por trade simulado, não lucro realizado com dinheiro.

| # | Entrada BRT | Moeda / lado | Entrada estimada | TP | SL | Saída | Min. até saída | Resultado |
|---:|---|---|---:|---:|---:|---|---:|---:|
| 1 | 29/10 21:11 | INJ SHORT | 7,245275 | 7,060 | 7,330 | TP | 9 | **+1,830 R** |
| 2 | 29/10 23:24 | LINK LONG | 10,670200 | 11,036 | 10,576 | TP | 143 | **+3,214 R** |
| 3 | 30/10 01:48 | ONDO LONG | 0,392439 | 0,4043 | 0,3891 | SL | 175 | −1 R |
| 4 | 30/10 06:34 | ARB SHORT | 0,161412 | 0,15775 | 0,16245 | SL | 51 | −1 R |
| 5 | 14/11 02:58 | HYPE LONG | 69,423822 | 71,332 | 68,900 | SL | 204 | −1 R |
| 6 | 14/11 13:47 | HYPE SHORT | 65,595317 | 63,230 | 66,102 | SL | 6 | −1 R |
| 7 | 14/11 14:08 | QNT SHORT | 149,875027 | 145,830 | 151,180 | SL | 17 | −1 R |
| 8 | 14/11 22:37 | SOL SHORT | 68,033194 | 66,040 | 68,750 | SL | 29 | −1 R |
| 9 | 14/11 23:14 | AAVE LONG | 101,060311 | 105,040 | 100,210 | TP | 121 | **+3,869 R** |
| 10 | 15/11 02:15 | INJ LONG | 7,099710 | 7,268 | 7,017 | SL | 40 | −1 R |
| 11 | 15/11 07:11 | ONDO LONG | 0,310231 | 0,3199 | 0,3081 | SL | 15 | −1 R |
| 12 | 15/11 16:47 | HYPE LONG | 67,304187 | 68,263 | 66,980 | SL | 97 | −1 R |

**Reconciliação com o PR #13:** 26–31/10 = 4 posições, 2 vencedoras, +3,0441878 R. 14–15/11 = 8 posições, 1 vencedora, −3,1305408 R. **Total: 12 trades / 3 vencedores / −0,086353 R.** As três vitórias somam +8,91365 R; os nove stops somam −9 R.

Somatório financeiro de cada trade em uma **conta paper fixa de 1 USDT**, sem composição, com sizing diferente por operação: aproximadamente **+0,0300 USDT estimados**, o que não contradiz −0,0864 R, pois riscos reais em USDT por trade variam. Isso **não** significa evolução real positiva da banca; sem execução real, o custo-modelo e o livro histórico são apenas pressupostos.

## Comparação EX-ANTE de indicadores: 3 vencedoras vs 9 stops

| Métrica calculada ANTES da entrada | Vencedoras: mediana | Stops: mediana |
|---|---:|---:|
| Volume do M1 confirmado / média dos últimos 20 M1 | **3,32×** | 1,73× |
| Corpo do M1 / amplitude total | 0,455 | 0,500 |
| Fechamento na extremidade favorável do M1 | 0,545 | 0,522 |
| Amplitude do M1 / ATR M15 | 0,170 | 0,201 |
| Deslocamento direcional em 1h / ATR M15 | 0,96 | 1,14 |
| Deslocamento direcional em 4h / ATR M15 | 2,30 | **3,51** |
| Deslocamento direcional M15 de 2h / ATR | −0,23 | **1,84** |
| RR líquido projetado | 2,17 | 2,12 |
| Minutos até TP ou SL (desfecho ex-post) | 121 | 40 |

**É diagnóstico, não prova de causalidade nem validação de filtro.** A amostra é minúscula (3 acertos) e por construção selecionada pelo RR mínimo.

### Hipóteses e contraexemplos

**1. Volume:** o LONG AAVE vencedor apresentou **6,03×** o volume médio de 20 M1; o SHORT INJ vencedor, **3,32×**. Isso sugere investigar participação do mercado e sustentação do rompimento. Porém o LONG LINK também venceu com **0,86×**, e o HYPE LONG perdeu com **3,60×**. Portanto, um veto por volume abaixo de 3× teria descartado um alvo vencedor e também não eliminaria todos os stops. **Não aprovar esse corte.**

**2. Movimento já estendido:** stops exibiram mediana 4h de **3,51 ATR**, vs **2,30 ATR** das vencedoras. Contudo, o antigo filtro A (corte 2 ATR) barraria **9 das 12** operações, inclusive **2 das 3 vencedoras** (SHORT INJ e LONG AAVE). A melhoria retrospectiva aparente do A não o torna uma regra operacional segura.

**3. Regimes de H1 e contra-tendência:** o LONG AAVE vencedor ocorreu com estrutura H1 classificada como **BAIXA**, assim como um LONG HYPE que parou. Portanto, o contexto H1 é relevante para diagnóstico, mas **inverter direção ou bloquear toda contra-tendência H1** não é justificado por esses casos.

**4. Concentração por ativo:** HYPE teve **3 stops** e ONDO **2 stops**, juntos **5 dos 9 stops**. INJ apresentou um SHORT vencedor e um LONG perdedor. Isso motiva investigar a estabilidade por ativo/regime, mas não **excluir HYPE e ONDO com base em seus resultados**, pois isso seria seleção posterior.

**5. Falhas rápidas:** 4 stops foram atingidos em **até 29 minutos** (HYPE SHORT 6m, QNT SHORT 17m, SOL SHORT 29m, ONDO LONG 15m); outro INJ LONG em 40m. Ganhos INJ SHORT em 9m, LINK LONG em 143m, AAVE LONG em 121m. **Tempo de saída só é conhecido depois da entrada** e não pode servir como filtro causal.

## Decisão e próximo teste científico

Não implantar corte de volume, movimento, direção H1, exclusão de símbolos ou RR1,5 na produção. Próximo experimento deve comparar **qualidade do rompimento** em uma amostra muito maior de candidatos (não apenas os 12 selecionados), separada cronologicamente e com o mesmo RR, TP/SL e custos congelados. Possíveis features exploratórias: volume M1 relativo, tendência M15/H1, extensão de preço em 1h/4h e volatilidade do candle. Limiares e combinações precisam ser especificados **antes** de consultar o holdout; custos adversos e cobertura do universo histórico continuam necessários.

O scanner `main`, `scan.yml`, cronjob.org, alertas, filtro de giro 5M e carteira paper de produção não foram alterados.
