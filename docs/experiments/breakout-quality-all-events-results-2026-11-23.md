# Resultado — qualidade dos rompimentos em todos os eventos viáveis com 1 USDT

Data: 23/11/2026. [PR #15](https://github.com/VinyRhyu/mexc-futures-scanner/pull/15), **rascunho, sem merge**. Execução validada: [GitHub Actions #45270402755](https://github.com/VinyRhyu/mexc-futures-scanner/actions/runs/45270402755) — **cinco jobs SUCCESS**. Os cinco relatórios de qualidade, carteiras e CSVs detalhados estão nos artifacts da execução.

Todos os cinco blocos exigiram **24/24 símbolos** com M1/M15/H1 contínuos e OHLC M1/M15 consistentes. Houve uma interrupção transitória de streaming HTTP em uma execução anterior; o cliente de pesquisa passou a repetir **somente** GET truncado por até 3 tentativas, e a rodada completa passou sem interpolar nem substituir candles. O cliente em `main` não foi modificado.

## Universo e denominações (a contagem de 276 não representa 276 trades)

| Período UTC, fim exclusivo | Planos M1 com giro >=5M | Planos de 1USDT financeiramente viáveis | Eventos únicos viáveis | Duplicados |
|---|---:|---:|---:|---:|
| 26–31/10 | 388 | 44 | 37 | 7 |
| 31/10–07/11 | 639 | 49 | 35 | 14 |
| 07–14/11 | 592 | 58 | 53 | 5 |
| 14/11 00h–15/11 20h | 191 | 52 | 42 | 10 |
| 15/11 20h–22/11 20h | 613 | 73 | 57 | 16 |
| **TOTAL** | **2.423** | **276** | **224** | **52** |

**224 eventos únicos não são 224 operações independentes**, pois muitos se sobrepõem temporalmente. A carteira de uma posição por vez teria realizado somente 110 operações no modelo BASE. Cada proposta duplicada foi eliminada por `plan_id` antes de usar seu resultado.

## Comparações de carteiras 1 USDT, slippage base de 0,02% por ponta

**Regra A permanece DESATIVADA:** estes são somente BASE, RR mínimo e regras exploratórias sobre volume/estiramento 2h, fixados ANTES de reexecutar todos os 224 eventos (mas motivados pelos 12 trades anteriores).

| Período | BASE | RR >=1,5 | RR1,5 + volume >=2× | RR1,5 + extensão 2h <=1,5 ATR | Ambos os critérios |
|---|---:|---:|---:|---:|---:|
| 26–31/10 | −3,996 | +3,044 | +3,734 | +1,214 | +1,904 |
| 31/10–07/11 | −7,149 | +2,284 | +1,701 | −0,299 | +1,701 |
| 07–14/11 | −1,684 | +5,549 | −0,815 | +3,677 | −1,000 |
| 14–15/11 | −2,871 | −3,131 | +0,869 | +1,869 | +2,869 |
| 15–22/11 | −3,982 | −2,430 | −3,000 | −2,774 | −1,000 |
| **Total R líquido descritivo, carteiras reiniciadas por bloco** | **−19,681 R** | **+5,317 R** | **+2,489 R** | **+3,688 R** | **+4,475 R** |
| **Total operações** | **110** | **29** | **13** | **16** | **7** |
| **Operações líquidas positivas** | **36** | **11** | **5** | **6** | **3** |

**Conclusão:** nos cinco blocos, **nenhum corte adicional por volume >=2× ou extensão 2h <=1,5 ATR superou o RR >=1,5 isolado no resultado agregado**. Mesmo o RR1,5 foi negativo nos dois intervalos finais (−3,131 R e −2,430 R). Portanto não há evidência de melhoria robusta e **nenhum filtro novo deve ser implantado**.

A versão mais restritiva com dois cortes teve somente **7 trades** no total e pareceu favorável no bloco de 14–15/11. Não extrapolar esse resultado: houve diminuição acentuada de frequência e os cinco períodos já foram utilizados em outras pesquisas.

## O que os 224 eventos revelam (descritivo, não filtro causal validado)

| Característica antes da entrada | 77 eventos com R positivo | 147 eventos com R <=0 |
|---|---:|---:|
| Mediana volume M1 / últimos 20 M1 | **1,34×** | **1,91×** |
| Mediana deslocamento direcional 4h / ATR M15 | **0,85 ATR** | **1,57 ATR** |
| Mediana deslocamento direcional 2h M15 / ATR | 0,94 ATR | 0,99 ATR |
| Mediana corpo M1 / amplitude | 0,283 | 0,278 |
| Mediana amplitude M1 / ATR M15 | 0,188 | 0,181 |

O contraste de volume é **oposto** ao observado nos 12 trades de RR1,5 estudados anteriormente (3 ganhadores tinham mediana de volume 3,32×, nove stops 1,73×). Portanto, **não afirmar que volume alto aumenta chance de acerto**; um veto volume >=2× teria eliminado vencedores e, no agregado, reduziu o R do portfólio.

Um movimento anterior grande de 4h aparece mais frequentemente em desfechos negativos, mas o filtro A anterior também excluiu vencedores. Não é uma prova a favor de qualquer cutoff retrospectivo.

**O resultado de todos os 224 eventos não pode ser somado e interpretado como carteira**, porque eventos simultâneos compartilham exposição, preço e regime. O cálculo do resultado financeiro deve sempre usar uma seleção sequencial independente, como na tabela acima.

## Sensibilidade financeira com a banca paper de 1 USDT

Repetimos o mesmo conjunto de cinco janelas a três hipóteses de slippage **por ponta**. Ao mudar custos, a própria elegibilidade muda, então as carteiras deixam de conter as mesmas operações; comparar apenas R total é enganoso.

| Slippage por ponta | BASE operações / R | RR1,5 operações / R | RR1,5+volume >=2× operações / R |
|---|---:|---:|---:|
| 0,02% | 110 / −19,681 | 29 / +5,317 | 13 / +2,489 |
| 0,05% | 55 / −7,049 | 15 / +5,789 | 8 / +1,491 |
| 0,10% | 22 / −5,797 | **8 / +2,990** | **5 / +2,589** |

**Não interpretar resultados positivos no stress como demonstração de resiliência**, especialmente quando restam só 5–8 entradas. Fills, spreads, funding, livro histórico e regras pessoais da corretora não foram observados.

## Decisão e próximo método

1. **RR1,5 continua hipótese exploratória**, não estratégia validada. A melhora retrospectiva é relevante, mas os blocos já influenciaram outros estudos e os dois finais foram negativos.
2. **Descartar por enquanto os vetos adicionais de volume e extensão 2h**, porque não demonstraram ganho agregado acima de RR1,5 e reduziram a frequência/descartaram vencedores.
3. **Não ajustar limiar de volume nem ATR vendo esses mesmos 224 eventos.** Próximo teste deve ser uma janela que não tenha sido usada para desenvolver a nova hipótese, com coorte de símbolos historicamente elegíveis, quotes/livro/fees conhecidos quando disponíveis e custos conservadores. Se a API da MEXC não preservar dados suficientes, exigir um arquivo de dados adequado, sem interpolação ou seleção dos símbolos por resultado.
4. O scanner atual, `mode=paper`, banca 1 USDT, mínimo de giro 5M, Telegram, cronjob.org, `scan.yml`, `engine.py` e `scanner-state` seguem sem alterações.

**Limites:** a seleção das 24 moedas é um snapshot de 23/11/2026, não um ranking top50 contemporâneo aos eventos de outubro/novembro. O livro é sintético e de profundidade infinita, a taxa taker 0,06% por ponta é hipótese, spread total fixo de 0,02% e funding sintético. Ganhos em R normalizado de carteiras reiniciadas em cada bloco não são ROI, saldo composto ou lucro real da conta.
