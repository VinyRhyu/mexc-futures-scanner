# Diagnóstico ex-ante de qualidade de rompimentos M1 — universo completo com 1 USDT

Protocolo congelado em 23/11/2026, antes de reexecutar o estudo agregado. **Pesquisa retrospectiva; não há autorização de mudança operacional.** A avaliação anterior das 12 operações ([PR #14](https://github.com/VinyRhyu/mexc-futures-scanner/pull/14)) sugeriu diferenças em volume e extensão do preço, mas inclui contraexemplos e não valida nenhum corte.

## Pergunta e universo

**Pergunta:** quais características observáveis antes da entrada diferenciam perdas e ganhos e, numa carteira de uma posição por vez, alguma regra predefinida preserva os alvos lucrativos melhor que o critério RR líquido >=1,5 isolado?

- Reusar **exatamente** o snapshot de 24 símbolos de 23/11/2026, SHA256 `edf08de9b2c1027c7631069a9b86baa73febd799c56fc8c2edf2274bc82601a1`, sem reordenar ativos ou excluir vencedores/perdedores por símbolo.
- Sinal M1 confirmado e liquidez **histórica** de 24 horas anterior ao sinal >=5 milhões USDT, conforme produção.
- Usar banca paper **1 USDT**, slippage de **0,02%, 0,05% e 0,10% por ponta**, spread sintético total de 0,02%, taker hipotético 0,06% por ponta e critérios financeiros idênticos aos do PR #13.
- A coorte anterior tinha aproximadamente **276 planos financeiramente viáveis sob 1 USDT e slippage 0,02%**, somando cinco blocos. Esta é a contagem de **planos**, não eventos independentes ou operações de carteira. A presente auditoria computará os totais corrigidos depois de deduplicar por `(symbol, side, signal_at)`.
- Exigir 24/24 símbolos com M1/M15/H1 contínuos em cada bloco e OHLC M1/M15 coerente. Histórico incompleto **invalida o bloco**, não gera falso zero.
- Os planos de mesmo ativo, direção e minuto que passaram no validador são deduplicados usando sempre o menor `plan_id` *antes* de analisar o resultado. Eventos únicos podem sobrepor-se, portanto não são operações independentes.
- Reconstituir carteiras simuladas de **uma posição simultânea**, com slot liberado no desfecho do trade anterior, para BASE, RR >=1,5 e cada hipótese exploratória separadamente. Nunca computar melhoria simplesmente apagando stops da carteira BASE.

## Blocos fixados antes do novo backtest

| Grupo | UTC inicial | UTC final exclusivo | Duração |
|---|---|---|---|
| Diagnóstico (D1) | 26/10 00:00 | 31/10 00:00 | 5 dias |
| Diagnóstico (D2) | 31/10 00:00 | 07/11 00:00 | 7 dias |
| Diagnóstico (D3) | 07/11 00:00 | 14/11 00:00 | 7 dias |
| Comparação (C1) | 14/11 00:00 | 15/11 20:00 | 44h |
| Comparação (C2) | 15/11 20:00 | 22/11 20:00 | 7 dias |

**Aviso crítico:** estes cinco períodos já influenciaram estudos anteriores do scanner, inclusive RR1,5 e filtro A, e por isso **C1/C2 NÃO são verdadeiros holdouts cegos para o desenvolvimento do projeto**. O nome `check` identifica apenas uma comparação temporal descritiva, **não validação independente**. Uma regra nova só poderá ser recomendada para produção após uma amostra independente futura, taxas verificadas e execução viável.

## Variáveis anteriores ao resultado (mesma implementação auditada no PR #14)

Todas as features usam apenas M1 fechado na confirmação e candles anteriores; M15 e H1 somente **fechados** no momento do sinal. O RR projetado usa uma cotação sintética na abertura seguinte, antes de qualquer desfecho:

1. `M1_volume_vs_prev20`: volume M1 atual / média dos 20 M1 anteriores.
2. `M1_body_fraction_of_range` e posição do fechamento orientada à direção.
3. Amplitude M1 / ATR(14) M15.
4. Deslocamentos direcionais M1 1h e 4h / ATR(14) M15.
5. Deslocamento direcional 2h dos últimos M15 fechados / ATR(14) M15.
6. Alinhamento com tendência H1 causualmente conhecida, incluindo estado indeterminado.
7. Relação `net_rr` **projetada na abertura hipotética** do candle seguinte.

Para classificação exploratória, os bins foram **especificados antes de ler o presente resultado agregado**:
- Volume M1: `<1`, `1–<2`, `2–<4`, `>=4` vezes a média.
- 4h direcional: `<0`, `0–<2`, `2–<4`, `>=4` ATR.
- 2h direcional: `<0`, `0–<1,5`, `1,5–<3`, `>=3` ATR.
- Corpo M1: `<0,3`, `0,3–<0,6`, `>=0,6` da amplitude.
- Range M1 / ATR: `<0,1`, `0,1–<0,25`, `>=0,25`.

## Comparações exploratórias predefinidas

Aplicar cada regra **antes da entrada e antes de olhar o TP/SL realizado**, a 1 USDT paper, recomputando a carteira. Objetivo: observar trade-offs de vitórias descartadas e stops evitados, **não escolher o melhor cutoff destes cinco períodos**.

- `BASE`: todas as entradas financeiramente viáveis, mínimo RR original >=1.
- `RR15`: RR líquido projetado >=1,5.
- `RR15_VOL2`: RR >=1,5 e volume relativo M1 >=2 vezes.
- `RR15_EXT2H`: RR >=1,5 e deslocamento direcional M15 nas 2h anteriores <=1,5 ATR.
- `RR15_VOL2_EXT2H`: união das duas exigências anteriores.

Os valores 2× e 1,5 ATR **já foram motivados pelos 12 casos anteriores**; são hipóteses exploratórias enviesadas pelo estudo anterior, nunca escolhas independentes. Outros limiares não serão procurados nesta amostra.

Métricas: número de sinais, planos com fill sintético, eventos deduplicados, quantidade por grupo/volume/H1/moeda, baseline sequencial, RR15 sequencial, soma e média líquida R, quantidade de vitórias, máximo drawdown, vitórias BASE perdidas, stops evitados, substituições por slot liberado, sensibilidade a custo. Todos os valores são simulações **sem execução observada, livro histórico ou funding/fees pessoais verificadas**.

## Critérios de conclusão

1. A análise descritiva pode indicar padrões úteis, mas **não deve afirmar causa, probabilidade de lucro real nem aprovar filtro**.
2. É preciso que um critério candidato melhore retorno líquido em diversos períodos, preserve alvos relevantes e não dependa apenas de um ativo/regime — **e então** testá-lo em *nova amostra realmente independente*.
3. Uma estratégia com fewer trades e R menos negativo **não** se torna lucrativa. A expectativa deve superar custos e apresentar incerteza compatível com amostra e dependência temporal.
4. Falha de dados, vazamento temporal, ausência de cobertura ou discrepâncias com os resultados anteriores implica marcar o bloco **INCONCLUSIVO**.
5. Não alterar `main`, `scan.yml`, cronjob.org, Telegram, `scanner-state`, alavancagem, saldo ou regras de trading.
