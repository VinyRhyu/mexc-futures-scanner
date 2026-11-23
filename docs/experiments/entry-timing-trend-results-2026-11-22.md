# Resultado do experimento A/B — comparação retrospectiva em duas semanas

Data: 22/11/2026 (execuções GitHub Actions iniciadas em 23/11 UTC).

**Fonte:** ações de coleta e arquivos JSON/CSV do [workflow de comparação](https://github.com/VinyRhyu/mexc-futures-scanner/actions/runs/45101536269). Nessa primeira execução, os dois jobs terminaram com erro **exclusivamente após os artefatos serem gerados**: variável de resumo sobrescrita (`KeyError: 'trades'`). Os resultados numéricos abaixo foram extraídos do `result.json` de cada job, que contém as 12 coletas concluídas e nenhuma exclusão. Correção de relatório isolada no commit `0d44cf8`, com reexecução em [45101668911](https://github.com/VinyRhyu/mexc-futures-scanner/actions/runs/45101668911) para verificar conclusão integral. **Não usar status de CI como aprovado até verificar a nova execução.**

O arquivo de pré-registro em `docs/experiments/entry-timing-trend-2026-11-22.md` foi criado ANTES de olhar as saídas e mantém os filtros fixos em A = extensão direcional 4h >= 2 ATR M15; B = H1 causal de pivôs na direção estritamente oposta. Não houve otimização de parâmetros após olhar os resultados.

## Comparação da carteira sequencial, todos os 12 ativos

| Intervalo UTC | Regra | Operações | Resultados líquidos positivos | Resultado líquido (R) | Max drawdown realizado (R) |
| --- | --- | ---: | ---: | ---: | ---: |
| 15–22/11 (semana inspecionada) | BASE | 14 | 3 | −8,4719 | 8,4719 |
| 15–22/11 | A | 9 | 3 | −3,4719 | 4,0000 |
| 15–22/11 | B | 9 | 1 | −6,8930 | 6,8930 |
| 15–22/11 | A+B | 4 | 1 | −1,8930 | 2,0000 |
| 07–14/11 (contraste anterior) | BASE | 12 | 2 | −8,4830 | 8,6680 |
| 07–14/11 | A | 8 | 2 | −4,4830 | 5,0000 |
| 07–14/11 | B | 9 | 1 | −6,6680 | 6,6680 |
| 07–14/11 | A+B | 7 | 1 | −4,6680 | 4,6680 |

A eliminou respectivamente cinco e quatro operações do BASE que atingiram STOP, sem excluir operações positivas da carteira original. Não surgiram operações substitutas nessas duas carteiras globais de A. **Todos os saldos em R continuam negativos.**

B eliminou operações positivas: DOT LONG (20/11 18h37 BRT, +1,274R) e TRB LONG de encerramento temporal (+0,147R), na semana inspecionada; ONDO LONG, encerrado após 4h com +0,185R, na anterior. A+B exibe menor perda na amostra semanal inspecionada principalmente por negociar muito menos; não é prova de melhor qualidade.

## Recorte com giro 24h histórico >=5M USDT, mas sem restrição do top 50

| Intervalo | Regra | Operações | Resultado líquido (R) |
| --- | --- | ---: | ---: |
| 15–22/11 | BASE | 11 | −6,619 |
| 15–22/11 | A | 8 | −3,619 |
| 15–22/11 | B | 7 | −4,893 |
| 15–22/11 | A+B | 4 | −1,893 |
| 07–14/11 | BASE | 11 | −7,483 |
| 07–14/11 | A | 5 | −1,483 |
| 07–14/11 | B | 7 | −4,668 |
| 07–14/11 | A+B | 4 | −1,668 |

**Não confundir** `core_only` com universo realmente selecionado pelo scanner: além de exigir giro >=5M, a produção exige estar entre os **50 elegíveis de maior giro** no momento do sinal e outras condições de cotação/mercado. Este teste só usa os 12 ativos da amostra, com classificação histórica por giro M1.

## Checagem dos oito exemplos discutidos, semana 15–22/11

| # | Moeda / lado | Resultado BASE | A barra? | B barra? | Indicador do A (extensão 4h/ATR) | Estrutura H1 |
| --- | --- | --- | --- | --- | ---: | --- |
| 1 | AVAX SHORT | STOP | **sim** | não | 2,18 | INDEFINIDA |
| 2 | AVAX LONG | STOP | não | não | 0,86 | INDEFINIDA |
| 3 | ARB LONG | ALVO +1,107 R | não | não | 1,42 | INDEFINIDA |
| 4 | ARB LONG | STOP | não | **sim** | −1,39 | BAIXA |
| 5 | UNI LONG | STOP | não | não | −2,60 | INDEFINIDA |
| 6 | AVAX SHORT | STOP | **sim** | não | 2,53 | BAIXA |
| 7 | TRB SHORT | STOP | **sim** | não | 3,51 | BAIXA |
| 8 | UNI LONG | STOP | não | **sim** | 0,37 | BAIXA |

Os comentários sobre possíveis outras entradas (ex.: AVAX às 10h30, UNI SHORT às 11h) são hipóteses de comparação e **não** foram testados como ordens alternativas. A análise atual somente veta/confirma entradas do modelo existente, **não inverte direção nem antecipa os gatilhos**.

## Interpretação e decisão

- Em ambos os intervalos retrospectivos, A reduziu as perdas e manteve os trades vencedores que já existiam no BASE; **prioridade para prospectivo em observação**, não para promoção automática.
- B demonstrou efeito colateral significativo (bloqueio de operações vencedoras), portanto **não recomendar incorporação direta**.
- Os períodos não são um verdadeiro teste independente: o modelo e a escolha da hipótese vieram de análise de históricos anteriores e dos oito casos visuais; há dependência entre trades, viés de sobrevivência do universo e pressupostos de execução e custos.
- Continuar em branch `research/entry-timing-trend-20261122`, PR rascunho, com `main`, cronjob.org e alertas intactos. Um teste prospectivo shadow mode, com sinais e vetos registrados sem alterar alertas, permitiria observar efetividade sem abrir operações.
