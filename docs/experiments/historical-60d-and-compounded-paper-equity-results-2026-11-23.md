# Resultado — cobertura MEXC de 60 dias e banca paper composta de 1 USDT

Data: 23/11/2026. Pesquisa isolada em [PR #16](https://github.com/VinyRhyu/mexc-futures-scanner/pull/16), **rascunho / sem merge**. Evidência completa [GitHub Actions #45280197755](https://github.com/VinyRhyu/mexc-futures-scanner/actions/runs/45280197755): **7 jobs SUCCESS**, incluindo 1 piloto de cobertura, 5 reconstruções históricas M1/M15/H1 com 24/24 moedas e 1 simulação de seis carteiras. Arquivos auditáveis nos artifacts: `history_60d_probe.json`, `equity_candidates_*.json`, `equity_report.json` e `compounded_1usdt_paper_ledger.csv`.

## 1. Conclusão da cobertura: NÃO há 60 dias M1 completos na API pública testada

Piloto 60 dias UTC (24/09/2026 00h a 23/11/2026 00h), BTC/ETH/SOL e sete âncoras temporais (240 M1 contínuos exigidos por âncora). Em 21 consultas de amostra, **9 completas** e **12 incompletas**:

| Data UTC | BTC M1 | ETH M1 | SOL M1 |
|---|---|---|---|
| 24/09 | 0/240 | 0/240 | 0/240 |
| 01/10 | 0/240 | 0/240 | 0/240 |
| 11/10 | 0/240 | 0/240 | 0/240 |
| 21/10 | 0/240 | 0/240 | 0/240 |
| 31/10 | 240/240 | 240/240 | 240/240 |
| 10/11 | 240/240 | 240/240 | 240/240 |
| 22/11 | 240/240 | 240/240 | 240/240 |

Não tentar preencher, mover datas ou dizer que limite por requisição de 2.000 candles garante retenção histórica de 60 dias. A MEXC não expõe snapshots históricos completos de todos os tickers top50 por meio do endpoint atual; portanto não é possível reconstituir fielmente o universo real de cada dia a partir desse snapshot.

**Próximo requisito de dados**: fonte arquivada de Futures MEXC com M1, turnover, histórico do ranking do universo, livro/quotes e contratos/tabelas históricas. Até lá, não há holdout independente de 60 dias.

## 2. Resultado REAL do novo modelo de banca paper de 1 USDT

Reexecutamos as 24 moedas em **cinco blocos históricos contíguos** de 26/10 00h a 22/11 20h UTC, recomputamos o custo/lot/margem/alavancagem em **cada entrada com o saldo já atualizado**, e mantivemos **uma única posição por vez**. O histórico inclui planos antes bloqueados pela banca fixa; não simplesmente reaproveitamos as 29 operações RR1,5 anteriores. Não há resets de saldo nos limites dos blocos, nem reposição de capital.

| Slippage por execução | Estratégia | Trades (positivas) | Capital inicial | Capital final | Retorno paper líquido | Maior DD realizado (USDT) | Max sequência perdas |
|---|---|---:|---:|---:|---:|---:|---:|
| 0,02% | BASE | 81 (18) | 1,0000 | **0,0467** | **−95,33%** | 0,9537 | 8 |
| 0,02% | RR projetado >=1,5 | 27 (9) | 1,0000 | **0,9409** | **−5,91%** | 0,5639 | 5 |
| 0,05% | BASE | 52 (16) | 1,0000 | **0,3760** | **−62,40%** | 0,7016 | 9 |
| 0,05% | RR projetado >=1,5 | 15 (8) | 1,0000 | **1,6883** | **+68,83%** | 0,2610 | 3 |
| 0,10% | BASE | 20 (5) | 1,0000 | **0,5907** | **−40,93%** | 0,6414 | 6 |
| 0,10% | RR projetado >=1,5 | 9 (4) | 1,0000 | **1,1805** | **+18,05%** | 0,1817 | 2 |

**Max drawdown relativo ao próprio pico realizado** calculado do CSV, em vez de dividir o DD por 1 USDT inicial:

| Cenário | DD pico-a-vale |
|---|---:|
| BASE 0,02% | **95,37%** |
| RR1,5 0,02% | **38,75%** |
| BASE 0,05% | **68,07%** |
| RR1,5 0,05% | **19,50%** |
| BASE 0,10% | **53,45%** |
| RR1,5 0,10% | **13,34%** |

O cenário de referência permanece **slippage 0,02% por ponta**: a carteira RR1,5 perdeu **0,0591 USDT (−5,91%)**, e a BASE perdeu **0,9533 USDT (−95,33%)**. A RR1,5 mitigou fortemente o dano, mas **NÃO gerou lucro líquido no cenário-base**.

No cenário de 0,05% e 0,10%, os lucros aparentes têm respectivamente apenas **15 e 9 trades RR1,5**. O aumento dos custos altera o conjunto de entradas que passa nos filtros; logo, **não** interpretar a maior lucratividade como ganho causado pelo slippage ou prova de robustez. Subconjuntos menores e cronologias diferentes não são pares equivalentes.

### Auditoria contábil e de execução

Validamos programaticamente, em cada uma das seis carteiras, que:

- `1 USDT + soma(net_usdt de operações)` == `ending_usdt` **exatamente em Decimal**.
- `balance_after` de uma operação == `balance_before` da seguinte, sem crédito externo ou reset temporal.
- Cada `exit_at` é anterior ou igual ao `signal_at` da operação seguinte: **zero operações sobrepostas**.
- O avaliador financeiro foi invocado novamente com o saldo atual, impondo lote mínimo, custo reservado, margem + custos <= saldo, alavancagem e orçamento de risco de até 10% por entrada.
- Todas as 5 fontes têm 24/24 moedas e todos os candlesticks exigidos, sem imputação, usando snapshot congelado e critério de giro passado >=5 milhões USDT.

No cenário RR1,5 a 0,02%, o patrimônio inicialmente subiu a aproximadamente **1,4551 USDT** e depois caiu para aproximadamente **0,8912 USDT** no pior vale; o drawdown realizado foi **38,75%** do pico. Encerrou em **0,9409 USDT**. Essa sequência mostra por que +5,32 R no estudo de carteiras reiniciadas por bloco **não** corresponde a crescimento do saldo em USDT da conta paper encadeada.

O cenário BASE de 0,02% ficou perto de inviabilidade: saldo final **0,0467 USDT**, e houve 310 bloqueios de plano pelo motivo `LOTE_MINIMO_OU_META_EXCEDE_RISCO` no replay dinâmico, embora a contagem seja de avaliações de propostas, não trades independentes.

## Decisão de engenharia

**Não promover RR1,5 nem filtros A/volume/ATR ao scanner de produção.** Há redução enorme da perda simulada, mas o retorno de referência segue negativo, o drawdown continua elevado e a execução é sustentada por **spread/fees/funding/livro históricos não verificados**.

A próxima atividade prioritária é conseguir dados históricamente contemporâneos da MEXC Futures (ou começar um arquivo read-only separado de preços/ranking/livro/fees daqui para frente) e depois travar uma avaliação verdadeiramente fora da amostra. Evitar otimizar RR ou volume usando os mesmos cinco períodos.

**Nenhuma ordem real**, nenhum merge em `main`, nenhuma mudança em `scan.yml`, `engine.py`, `scanner-state`, Telegram, cronjob.org, limites de risco ou carteira paper operacional. Dados e código permanecem apenas no PR #16.

## Limitações adicionais

Esta simulação revalida o **finance.evaluate** da configuração atual a cada abertura de M1 com saldo mutável, e reconstitui P&L usando saída OHLC conservadora. Porém a profundidade do livro é artificial e ilimitada; ticker, lotes, margem, alavancagem/tier e fees são do catálogo atual, **não necessariamente daqueles dias históricos**. `FUNDING = 0` é hipótese. O período e as moedas foram usados em pesquisas anteriores. O valor `1 USDT` é paper, não saldo de uma conta operada. O fato de a carteira encadeada fechar com +68,83% em cenário de 0,05% **não prova lucratividade real ou futura**.
