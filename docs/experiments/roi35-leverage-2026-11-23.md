# Pesquisa: ROI líquido >=35% da margem, como percentual de Futures MEXC

Data de pré-registro: 23/11/2026. Esta nova análise foi motivada pela meta explicitada pelo usuário: **lucro de 35% mostrado pela MEXC por posição**, isto é ROI em relação à **margem inicial aplicada à posição**, NÃO 35% de saldo total e NÃO alavancagem multiplicada pelo ROI já apresentado.

## Como o indicador será medido

Documentação oficial: [PNL/ROI e margem MEXC](https://www.mexc.com/pt-BR/learn/article/pnl-calculations-explained/1), [guia oficial de realized PNL e taxas](https://www.mexc.com/support/article/mexc-futures-calculation-guide-312060306409668608).

- ROI indicativo de posição aberta: `unrealized_pnl / initial_margin × 100`, dependendo de preço justo (fair price) e alavancagem atual. É **não realizado**.
- Para comparar objetivo de operação encerrada neste backtest: `net_realized_pnl_usdt / initial_modeled_margin_usdt × 100`, com fee e slippage hipotéticos já deduzidos no P&L. Funding continua zero hipotético, NÃO igual a ROI de tela quando a posição ainda está aberta.
- ROI líquido **projetado no TP ANTES da decisão**: `finance.evaluate.gain_usdt / finance.evaluate.margin_usdt × 100`. Gate experimental exige **>=35%**, junto de RR projetado >=1,5.
- Resultados vencedores reais podem ter ROI <35% por saída por tempo, execução diferente de TP estimado ou outros efeitos. **Não é garantia de ganhar 35% em toda entrada.**
- Alterar alavancagem **mantendo quantidade de contratos** altera margem requerida e %ROI, mas NÃO multiplica o lucro monetário do preço. A margem/risco de liquidação muda; por isso todas as propostas são **reavaliadas** pelo validador financeiro de produção com os limites originais.

## Cenários congelados antes de consultar o resultado

Usar os **mesmos cinco artefatos históricos já verificados no PR #16** e 24 símbolos congelados, cenário de custo-base `slippage = 0,02% por ponta`, spread sintético de 0,02%, taker hipotético 0,06% por ponta, funding zero, banca paper inicial **1 USDT**, risco por operação <=10% da banca atual e stop/TP técnico inalterados. 26/10 a 22/11/2026, cinco janelas contíguas sem reset.

Seis carteiras independentes:

| Alavancagem fixa | Sem exigência de ROI no TP | TP com ROI líquido projetado >=35% |
|---|---|---|
| 10x | RR >=1,5 | RR >=1,5 e ROI >=35% |
| 15x | RR >=1,5 | RR >=1,5 e ROI >=35% |
| 20x | RR >=1,5 | RR >=1,5 e ROI >=35% |

**Não testar 30x**, porque o scanner atual limita alavancagem a 20x. Não alterar stop/TP para fazer 35% parecer alcançável. Nenhuma seleção é feita usando desfecho futuro; 35% é apenas um filtro ex-ante da razão `gain_usdt/margin` calculada na cotação hipotética da abertura M1 seguinte.

O validador financeiro reavalia cada candidato técnico com `minimum_leverage=maximum_leverage=10/15/20`, conforme cenário, exigindo `finance.evaluate == VIAVEL_SIMULADO`, validando `margin_usdt + costs_usdt <= saldo atual`, tamanho mínimo, passo, custo/reserva, buffer de liquidação, taxa de risco, tiers e disponibilidade. Uma posição por vez, saldo paper composto entre as semanas, nunca aumentar contratos apenas para inflar ROI.

## Métricas que devem determinar conclusão

- Número de operações escolhidas, ganhos/perdas, proporção de **operações vencedoras** que realmente fecharam com ROI líquido >=35%.
- Mediana de ROI realizado positivo e negativo por margem; quantos stops e custo sobre margem.
- **Saldo final em USDT**, comparação ao saldo inicial de 1 USDT, máximo drawdown percentual pico-a-vale, sequência de perdas e bloqueios de contrato/alavancagem/liquidação.
- Comparar com resultado original **reproduzido exatamente** em código: 27 operações RR1,5 com alavancagem dinâmica >=10x e <=20x, saldo final de `0.9408652174548 USDT` com custo-base.
- Aumentar ROI percentual reduzindo margem não demonstra P&L monetário maior e pode intensificar o prejuízo percentual sobre a margem. Não selecionar melhor alavancagem a posteriori como estratégia comprovada.

## Limites cruciais

**Este experimento é exploratório e contaminado por pesquisas anteriores sobre estes mesmos períodos, não validação out-of-sample.** O catálogo dos contratos e os tiers são do momento do snapshot, e o universo não é um top50 historicamente contemporâneo. Não há fills, spreads dinâmicos, livros, funding real ou taxas pessoais documentados para aquelas datas. A posição aberta na MEXC exibe ROI não realizado baseado em fair price; o benchmark de pesquisa aqui utiliza ROI líquido fechado sobre margem inicial do modelo.

**NADA em produção:** sem merge, sem `main`, sem alterar `scan.yml`, `engine.py`, cronjob.org, Telegram, alavancagem operacional, saldo, ativos reais ou posição. Resultado de 35% *projetado* não equivale a recomendação de operação.
