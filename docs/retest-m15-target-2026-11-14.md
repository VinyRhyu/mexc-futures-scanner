# Estrutura/reteste M5: troca exclusiva do alvo para M15 — 14/11/2026

Resultado: não promover ao bot. A troca do TP aprovou mais entradas,
mas todas atingiram o SL neste recorte. Main e Telegram não foram alterados.

## Regra e comparação

Mesmos 264 padrões nos mesmos 26 ativos, horários candidatos, preços M1,
SLs M5, faixas técnicas, custos e limites financeiros. Somente o TP mudou.
A faixa financeiramente admissível e a quantidade podem mudar como consequência
da reavaliação do novo TP. Não são mantidas apenas as duas entradas antigas:
todos os 264 candidatos passam novamente pelo mesmo validador.

Novo TP: pivô confirmado M15 mais próximo adiante da referência da reação,
com um tick de antecipação. Topo acima para LONG; fundo abaixo para SHORT.
Pivôs de dois candles de cada lado, disponíveis quando o segundo vizinho
à direita fechou há pelo menos 10s. Idade máxima de seis horas. Um fechamento
M15 posterior além do nível invalida o pivô. O alvo é congelado no gatilho
original e igual nos atrasos de 0/60s. Não se pula nível para forçar RR;
sem alvo válido, não há entrada nem fallback. Protocolo fixado antes do teste:
config/audit-retest-m15-target-2026-11-14.json.

Sinais até 17:15:04 BRT, preços até 17:17 BRT. Saldo referencial US$1,
risco até 10%, RR líquido mínimo 1:1, alavancagem 10x-20x, taxa 0,06% por lado,
spread sintético 0,02%, slippage 0,02% ou dois ticks, funding zero. Janela de
abertura de 120s e até quatro horas de acompanhamento após a reação.

## Resultado completo

| Alvo / atraso | Entradas | TP | SL | Soma R independente |
| --- | ---: | ---: | ---: | ---: |
| Local M5, imediato | 2 | 0 | 2 | -2R |
| Estrutural M15, imediato | 10 | 0 | 10 | -10R |
| Local M5, +60s | 1 | 0 | 1 | -1R |
| Estrutural M15, +60s | 6 | 0 | 6 | -6R |

Não houve posições abertas/censuradas nem TP e SL no mesmo minuto entre as
entradas aceitas. Todos os stops ocorreram antes do limite de acompanhamento.
Atraso zero é idealizado; soma de R de planos sobrepostos não é ROI de carteira.

## Corte com quatro horas completas disponíveis

Somente sinais até 13:17 BRT, para ambos os modelos:

| Alvo / atraso | Entradas | TP | SL | Soma R |
| --- | ---: | ---: | ---: | ---: |
| Local M5, imediato | 1 | 0 | 1 | -1R |
| Estrutural M15, imediato | 7 | 0 | 7 | -7R |
| Local M5, +60s | 0 | 0 | 0 | 0R |
| Estrutural M15, +60s | 4 | 0 | 4 | -4R |

## Diagnóstico

181 dos 264 padrões possuíam alvo M15 elegível; 83 ficaram sem alvo.
Dos 181 alvos, 157 ficaram mais distantes que o alvo local e 24 mais próximos
ou iguais. A regra não exigiu aumentar o alvo. A distância mediana à referência
foi 0,725%, contra 0,163% no TP local; as medianas usam os alvos disponíveis
em cada política, não uma amostra idêntica de alvos.

No imediato, 8 casos bloqueados tornaram-se viáveis, além dos 2 anteriores.
Com 60s, 5 casos adicionais tornaram-se viáveis, além do 1 anterior. Dois desses
casos eram cancelados por toque no antigo TP antes da entrada: a troca do alvo
também altera essa condição. Todos os aprovados atingiram SL.

Bloqueios no imediato: 82 RR insuficiente, 83 custo elevado, 4 preço fora da
faixa, 2 lote/risco e 83 sem alvo. Outros 10 foram aceitos.

Projetar ganho maior não melhorou a seleção nesta amostra. A causa de cada
stop (ruído, invalidação mal posicionada ou direção) não é isolada neste teste.

## Verificação e limites

Os 264 padrões originais foram reconstruídos exatamente. Passaram 264
checagens por prefixo histórico para a seleção do alvo e quatro testes de
causalidade, confirmação do pivô, nível mais próximo e simetria SHORT.

Amostra exploratória de um dia já estudado, sem validação fora da amostra.
Livro/spread sintéticos, funding zero e parâmetros públicos de contrato do
mesmo dia; não comprovam execução. Nenhuma busca adicional de parâmetros foi
feita depois dos resultados. Nenhum filtro RSI, H1 ou TOTAL3 foi adicionado.

Resumo e entradas aceitas: docs/retest-m15-target-2026-11-14.json.
M1: execução 43650715883. Contratos: execução 43639547648.
O teste anterior e seus dados são documentados em docs/structure-retest-2026-11-14.md.

```sh
python -m unittest tests.test_retest_m15_target -q
python -m scripts.audit_retest_m15_target --original /pasta/structure-retest-results.json --source /pasta/m1-com-aquecimento --contracts /pasta/contracts.json --config config/default.toml --output /tmp/m15-target-results.json
```
