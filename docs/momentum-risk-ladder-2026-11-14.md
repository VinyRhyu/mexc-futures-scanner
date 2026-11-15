# Sete dias: stop compatível com 10x e aumento do risco

**US$ 100 iniciais; margem isolada 10x; 06/11/2026 22h → 13/11/2026 22h, Brasília.** Mesmos sete ciclos completos e mesma coleta da análise anterior. Estratégia de momentum diário; não representa o scanner intradiário em produção.

## Resultado

| Cenário | Saldo final US$ | Retorno líquido | Operações | Positivas / negativas | Acerto | Maior recuo H1 | Liquidações |
|---|---:|---:|---:|---:|---:|---:|---:|
| Original, risco 2% | 100.1289 | +0.1289% | 31 | 20 / 11 | 64.52% | 0.3712% | 2 |
| Stop limitado, risco 2% | 100.6691 | +0.6691% | 35 | 24 / 11 | 68.57% | 0.9535% | 0 |
| Stop limitado, risco 5% | 101.4249 | +1.4249% | 45 | 27 / 18 | 60.00% | 2.4000% | 0 |
| Stop limitado, risco 10% | 102.9385 | +2.9385% | 45 | 27 / 18 | 60.00% | 5.2632% | 0 |

Primeiro alteramos apenas a regra do stop e recalculamos o tamanho das posições com o mesmo limite de risco de 2%. Depois mantivemos essa nova regra e aumentamos somente o limite conjunto para 5% e 10%. Não foi adicionado TP. Entradas, ranking, atraso de execução, saída por prazo, fontes, custos, funding e modelo de liquidação permaneceram os mesmos. O tamanho é recalculado a cada ciclo; o resultado não foi simplesmente multiplicado.

## Por que muitos acertos renderam tão pouco?

No original, os 20 resultados positivos somaram **US$ 0,689283**; os 11 negativos somaram **−US$ 0,560425**. Sobraram **US$ 0,128858**. O ganho médio foi de US$ 0,034464 por acerto, enquanto a perda média foi de US$ 0,050948 por erro. As duas liquidações estão incluídas nas perdas. A taxa de acerto sozinha não informa a rentabilidade.

A exposição média original era US$ 6,2166 para uma conta de US$ 100; a margem média era apenas US$ 0,6217. A regra de perda planejada de 2%, combinada com stops diários amplos e arredondamento de lotes, restringia fortemente a exposição. Com margem isolada 10x, os 31 stops originais estavam além da liquidação estimada.

## O que mudou no stop

A nova regra, fixada antes desta execução, mantém o stop original de 2 ATR quando ele é mais próximo. Quando o stop é distante demais, limita a distância adversa a **distância estimada da liquidação ÷ 1,6**, medida a partir do preço de entrada executado. Assim, supera a exigência de folga de 1,5. Todos os stops das operações executadas nesta semana precisaram desse limite.

Esse limite usa a estimativa do nível de manutenção no lote mínimo antes de dimensionar a posição. O teste verifica que o tamanho final permaneceu na mesma faixa de manutenção; em caso de mudança da faixa, interromperia a simulação para recalcular. Todos os cenários concluíram sem esse problema.

**Este é um novo critério de saída.** Aproximar o stop para caber na alavancagem pode encerrar operações antes da invalidação da estrutura diária. O resultado desta semana não prova que esse stop é adequado para outros períodos.

## Exposição, risco e custos

| Cenário | Exposição média US$ | Margem média US$ | Risco planejado efetivo médio | Taxas US$ | Spread/slippage US$ | Funding líquido US$ | Stops / prazo |
|---|---:|---:|---:|---:|---:|---:|---:|
| Original, risco 2% | 6.2166 | 0.6217 | 1.13% | 0.05013 | 0.03771 | +0.00170 | 0 / 29 |
| Stop limitado, risco 2% | 21.6152 | 2.1615 | 1.33% | 0.17943 | 0.13552 | +0.01008 | 6 / 29 |
| Stop limitado, risco 5% | 68.3009 | 6.8301 | 4.20% | 0.56691 | 0.40340 | +0.02308 | 8 / 37 |
| Stop limitado, risco 10% | 142.9020 | 14.2902 | 8.70% | 1.18624 | 0.84445 | +0.05479 | 8 / 37 |

Margem e exposição são as somas iniciais de todas as posições de cada ciclo, depois calculadas em média nos sete ciclos. O risco é da carteira diária inteira, não de cada operação. O teto planejado inclui custos de stop; lotes mínimos e slots vazios deixam parte do orçamento sem uso. Gaps, diferenças Last/Fair e liquidação podem ultrapassar uma perda planejada.

Em 5% e 10%, houve 27 acertos e 18 erros: aumentar o risco não melhorou a taxa de acerto. Em 10%, os ganhos somaram US$ 15,254229 e as perdas US$ 12,315753; sobraram US$ 2,938476 após os custos considerados. A maior queda da curva H1 foi 5,2632%, maior que o ganho final de 2,9385%.

Os lotes mínimos explicam parte da mudança do número de operações: 18 descartes no original, 14 no stop limitado a 2%, e quatro nos cenários de 5% e 10%. O ranking de candidatos permaneceu igual; o conjunto efetivamente negociável dependeu do tamanho.

## Resultado por ciclo

| Ciclo BRT | Original 2% US$ | Stop limitado 2% US$ | Stop limitado 5% US$ | Stop limitado 10% US$ |
|---|---:|---:|---:|---:|
| 06/11 22:00 → 07/11 22:00 | +0.066118 | +0.387882 | +0.988472 | +2.054279 |
| 07/11 22:00 → 08/11 22:00 | +0.080513 | +0.132943 | +0.165085 | +0.568269 |
| 08/11 22:00 → 09/11 22:00 | -0.013300 | -0.039542 | -0.262968 | -0.557050 |
| 09/11 22:00 → 10/11 22:00 | -0.147822 | -0.252766 | -0.248759 | -0.577980 |
| 10/11 22:00 → 11/11 22:00 | -0.031610 | -0.115757 | -0.853217 | -1.690175 |
| 11/11 22:00 → 12/11 22:00 | +0.192039 | +0.715639 | +1.921155 | +3.899497 |
| 12/11 22:00 → 13/11 22:00 | -0.017080 | -0.159325 | -0.284868 | -0.758364 |

## Verificações e limites

- A reprodução do original foi idêntica em todos os campos: resumo, operações, dias, curva H1, descartes e sete verificações causais.
- Sete testes direcionados passaram: os quatro anteriores e três novos para stops LONG/SHORT antes da liquidação, manutenção de stop já próximo e efeito do aumento de risco nas quantidades.
- Os três cenários corrigidos tiveram zero violações da folga de 1,5 e zero liquidações simuladas. Isso não garante ausência de liquidação real ou futura.
- Sem otimização de parâmetros depois de observar estes resultados. Os níveis 2%, 5%, 10% e a folga 1,6 foram registrados no protocolo antes da execução.
- A semana foi reutilizada após conhecer o teste anterior. É uma comparação exploratória, sem validação independente. Universo atual com viés de sobrevivência; especificações atuais de contratos, lotes e manutenção aplicadas retrospectivamente.
- Preços H1 não permitem reconstruir execução intrahora nem o maior drawdown intrahora. Funding e preços são históricos; fills e liquidação são estimados.
- Taxa de negociação de 0,06% por execução; spread total 0,02%; slippage por execução igual ao maior entre 0,02% do preço e dois ticks. Spread/slippage já incorporados nos fills.
- Nenhuma alteração em produção, no Telegram ou em ordens reais. Níveis de risco maiores são cenários de teste, sem aprovação de uso real.

Fonte: [coleta 43655552665](https://github.com/VinyRhyu/mexc-futures-scanner/actions/runs/43655552665). Protocolo em `config/audit-momentum-risk-ladder-2026-11-14.json`; operações, curva H1 e hashes dos arquivos-fonte no JSON adjacente. Código em `scripts/audit_momentum_risk_ladder.py`.

```sh
python -m unittest tests.test_momentum_week10x tests.test_momentum_risk_ladder -q
python -m scripts.audit_momentum_risk_ladder --source SOURCE_DIR --protocol config/audit-momentum-risk-ladder-2026-11-14.json --baseline PREVIOUS_RESULTS_JSON --output results.json
```
