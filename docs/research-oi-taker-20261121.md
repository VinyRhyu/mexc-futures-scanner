# Pesquisa OI + agressão vs rompimentos M1 — 21/11/2026

**Tipo:** retrospectivo exploratório, sem ordens e sem mudança da branch principal.

Fonte dos gatilhos: [coorte congelada MEXC](https://github.com/VinyRhyu/mexc-futures-scanner/actions/runs/42890505005), sinais de 25/10 a 07/11/2026.
Fonte auxiliar: OKX Rubik, open interest por contrato e volume agressor de compra/venda, período 1H. Usa apenas observações com timestamp até sinal menos uma hora. São **corretoras diferentes**.

O teste da Binance foi bloqueado por HTTP 451; a OKX retornou dados completos em 23/24 ativos, pareando 57/57 entradas M1 confirmadas.

## Resultado congelado M1 confirmado — operações independentes

| Regra | Operações | Encerradas | Acerto | Soma de R |
|---|---:|---:|---:|---:|
| Sem filtro | 57 | 51 | 35,29% | +14,311 |
| Agressão alinhada | 32 | 29 | 20,69% | -7,960 |
| OI USD crescente | 25 | 24 | 25,00% | -2,107 |
| OI USD crescente e agressão alinhada | 15 | 14 | 7,14% | -10,690 |
| Veto da condição conjunta, OI USD | 42 | 37 | 45,95% | +25,001 |
| OI contratos crescente e agressão alinhada | 15 | 15 | 6,67% | -11,690 |
| Veto da condição conjunta, OI contratos | 42 | 36 | 47,22% | +26,001 |

**Nota:** soma de R representa operações isoladas e simultâneas. Não é ROI de uma carteira. Operações abertas após 4 horas não entram no R encerrado.

## Teste de estresse: uma única posição por vez

Sinais do mesmo ativo/direção/minuto foram deduplicados (pior resultado e saída mais tardia). A execução usa o primeiro sinal disponível em ordem cronológica, desempate alfabético por ativo. Só permite abrir outra posição após a saída anterior; operações ainda abertas bloqueiam 4 horas.

| Versão | Operações sequenciais | Encerradas | Acerto | Soma R | Máximo drawdown |
|---|---:|---:|---:|---:|---:|
| Sem filtro | 22 | 21 | 23,81% | **-3,339** | 10 R |
| Veto OI USD + agressão | 19 | 18 | 22,22% | **-3,649** | 10 R |
| Veto OI contratos + agressão | 16 | 15 | 26,67% | **-0,649** | 9 R |

A condição **OI crescente + agressão alinhada** foi especialmente ruim nesta amostra. Entretanto, **usar a condição como veto não tornou positiva a carteira de uma posição**; portanto não há filtro aprovado.

### Limitações importantes
- Coorte conhecida e previamente analisada; risco de sobreajuste e ausência de validação prospectiva.
- Dados auxiliares OKX, fills hipotéticos MEXC; divergência entre corretoras pode importar.
- Amostra pequena, com operações correlacionadas e sobrepostas.
- Custos estimados da simulação congelada, não custos de ordens reais.
- Critério de priorização por horário e ordem alfabética é teste de estresse, não estratégia de ranking.
- OI em USD contém efeito da mudança de preço; OI em contratos foi testado como sensibilidade.

**Decisão:** manter scanner operacional intacto. Próximo teste distinto deve priorizar sinais simultâneos com critérios fixos e verificar resultados futuros.

- [Execução e artefatos](https://github.com/VinyRhyu/mexc-futures-scanner/actions/runs/44919105159)
- [Código de pesquisa](../scripts/research_okx.py)
