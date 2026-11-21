# Pesquisa de prioridade M1 — 21/11/2026

Estado: experimento histórico **somente leitura**, sem alterações no scanner principal e sem ordens.

## Dados e procedimento

- Histórico congelado de 25/10 a 07/11/2026, extraído dos runs [42879077420](https://github.com/VinyRhyu/mexc-futures-scanner/actions/runs/42879077420) e [42890505005](https://github.com/VinyRhyu/mexc-futures-scanner/actions/runs/42890505005).
- 57 registros M1 confirmados, consolidados em **49 oportunidades distintas** (mesmo ativo, direção e minuto; pior R/saída mais tardia quando havia planos duplicados).
- 43 minutos com oportunidades; 5 com mais de um ativo. Uma posição por vez, preenchimento e saída históricos congelados.
- Rank fixado antes da comparação: primeira oportunidade/desempate alfabético, maior R:R projetado, maior volume relativo M1, melhor fechamento direcional, menor extensão ATR.
- Somente sinais presentes no **mesmo minuto** são comparados; não é válido atribuir preenchimento histórico a um sinal atrasado de outro minuto.

## Resultados

| Política | Operações | Encerradas | Vencedoras | Soma R líquido | DD máximo (R) |
|---|---:|---:|---:|---:|---:|
| Controle cronológico/alfabético | 22 | 21 | 5 | -3,339 | 10 |
| Maior risco-retorno projetado | 22 | 21 | 4 | -6,649 | 10 |
| Maior volume relativo M1 | 22 | 21 | 5 | -3,339 | 10 |
| Melhor fechamento direcional | 22 | 21 | 5 | -3,339 | 10 |
| Menor extensão em ATR | 22 | 21 | 5 | -3,339 | 10 |

**Apenas um empate ocorreu quando havia capital livre:** 30/10/2026 às 04:33 UTC (DOT LONG vs INJ LONG). Priorização por R:R escolheu INJ e piorou o resultado; outros critérios permaneceram com DOT.

### Veredito

Nenhuma política aprovada. O gargalo da carteira histórica é a **qualidade absoluta dos sinais e o capital comprometido durante as operações**, não o desempate no mesmo minuto.

Limites: série previamente explorada, sem validação prospectiva; resultado R de operações simuladas sob premissas antigas de custos e fill; uma operação ainda aberta no corte não teve resultado final contabilizado; deduplicação pessimista, sem replay de preço/ordens para sinais atrasados.

**Próxima investigação:** congelar critérios e avaliar candidatos futuros como uma coorte prospectiva, inclusive recusas e oportunidades não executadas, com carteira de uma posição e marcação a mercado.
