# Experimento A/B — momento da entrada e direção H1

Data da especificação: 22/11/2026. **As regras abaixo ficam congeladas antes de consultar seus resultados.** Execução puramente experimental, sem ordens, Telegram, alteração de `main` ou modificação dos sinais.

## Dados e comparação

- **12 ativos fixos** da auditoria anterior: ORCA, S, NEO, FLOKI, TRB, SAND, ONDO, ARB, TIA, DOT, AVAX e UNI.
- **Semana revisada visualmente:** sinais de 15/11/2026 20:00 a 22/11/2026 20:00 UTC; equivale a 15/11 17h até 22/11 17h BRT. Os oito casos iniciais foram vistos antes da criação do teste: **não é validação fora da amostra**.
- **Contraste anterior:** 07/11/2026 00:00 até 14/11/2026 00:00 UTC. Este período faz parte de estudos anteriores do modelo e também é retrospectivo; não chamá-lo de holdout independente.
- **BASE**: manter as mesmas confirmações M1, TP, SL, faixa de entrada e custos usados no replay anterior; a carteira de uma posição é recomputada sobre todas as entradas financeiramente viáveis.
- **A (entrada tardia)**: bloquear um sinal se o deslocamento de fechamento, na direção da posição, entre o candle M1 de agora e o candle de exatas quatro horas antes for **>= 2,0 × ATR(14) do último M15 fechado**. Apenas dados até o fechamento do M1 confirmador. A janela de quatro horas exige 240 candles contínuos; sem essa cobertura, abortar a amostra daquele ativo.
- **B (direção H1)**: bloquear somente LONG se a estrutura causal de pivôs H1 conhecidos naquele fechamento for `BAIXA`, ou SHORT se a estrutura for `ALTA`. Estados `DESCONHECIDA` e `INDEFINIDA` são **permitidos**: não inventar uma tendência oposta. Pivôs H1 exigem duas velas futuras para confirmação e só ficam disponíveis após essas duas velas terem *fechado*, conforme função `structure` existente.
- **A+B**: união conservadora dos dois filtros. Não mudar stop, target, confirmação, custos, parâmetros financeiros, ativos e janela após ver resultados.
- Para cada um de BASE, A, B, A+B, **reconstruir a carteira inteira**, não apenas excluir operações perdedoras da carteira baseline: sinais previamente sobrepostos podem passar a ser escolhidos.
- Além das 12 moedas, avaliar a mesma regra apenas sobre os sinais com **giro histórico de 24 horas >= 5M USDT** (grupo `core_only`), porque a produção não autoriza baixo giro.
- Medidas: operações selecionadas, vitórias líquidas, R líquido total e médio, drawdown acumulado em R, novos sinais escolhidos após liberar um slot, exemplos do baseline preservados/perdidos, interseção A/B. Comparação de win rates isolada não basta.
- Não testar 20 limiares e escolher o melhor no mesmo histórico. **2 ATR em 4h** foi fixado por hipótese de extensão e não foi otimizado empiricamente para esse conjunto.
- Um resultado promissor precisará de coleta prospectiva independente e modelagem de profundidade, funding, spread e slippage variável; OHLC e fills atuais são hipóteses de simulação, não dinheiro ganho.

## Riscos de interpretação

A regra A é uma aproximação de *extensão*, não demonstra automaticamente que uma operação estava atrasada. A regra B representa **pivôs H1 confirmados**, não toda a complexidade da direção intradiária. Concentração e dependência entre sinais permanecem possíveis; ativos selecionados por snapshot atual implicam viés de sobrevivência. Resultado em R é escala normalizada e não ROI da banca. Critérios adversos não deverão ser promovidos para produção.

## Reprodução

Executar `python -m unittest tests.test_research_entry_context -v` e a execução MEXC pública com `LIQUIDITY_FIXED_WEEK=1` e os intervalos de cada uma das duas semanas. O workflow `.github/workflows/research-entry-context.yml` executará os dois blocos como jobs separados e publicará `result.json`, relatório e CSV de entradas BASE/A/B/A+B. O grupo `core_only` é analisado com base no giro histórico do sinal.

