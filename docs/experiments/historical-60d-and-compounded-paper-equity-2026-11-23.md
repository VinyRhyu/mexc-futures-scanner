# Pesquisa: 60 dias de histórico e evolução de banca paper de 1 USDT

**Pré-registro: 23/11/2026. Apenas pesquisa, nada em produção.** Base: `research/breakout-quality-all-events-20261123`. A hipótese de RR líquido projetado >= **1,5** foi congelada na pesquisa anterior, não otimizada aqui.

## Parte 1: disponibilidade real de 60 dias históricos

A MEXC documenta GET público de candles de Futures M1 com limite de **2.000 candles por consulta**, não garantia de retenção de dados completos por 60 dias. **Não inferir disponibilidade de 60 dias** do limite de paginação.

Piloto com 3 símbolos selecionados antes do teste — BTC, ETH, SOL — e **7 pontos temporais predefinidos** de 24/09 a 22/11, cada amostra com 240 candles Min1 exatos e sem lacunas. Se **todas** as âncoras passarem, fazer uma varredura BTC Min1 de 24/09 00h a 23/11 00h UTC, **86.400 candles** em lotes inferiores a 2.000, exigindo cobertura integral. Se qualquer amostra falhar, registrar a lacuna, não trocar símbolos/datas, não interpolar.

Este piloto NÃO reconstitui o top50 da data histórica. A seleção de 24 símbolos foi fotografada em 23/11 e contém viés temporal/sobrevivência. Para backtest independente em todo o universo precisamos também de snapshots de **todos os tickers e contratos** em cada data; fontes Spot ou de outra corretora não substituem MEXC Futures M1. Não aprovar nova estratégia sem dados históricos independentes.

## Parte 2: curva financeira com saldo REALMENTE mutável (papel)

Congelar os 24 contratos/símbolos já utilizados, hash `edf08de9b2c1027c7631069a9b86baa73febd799c56fc8c2edf2274bc82601a1`. Reexecutar **cinco blocos contínuos** com M1/M15/H1, mesmo mínimo histórico >=5M USDT, uma posição por vez. Exigir todos os 24 símbolos completos, sem preenchimento de candles faltantes.

Período total UTC: **26/10 00:00 a 22/11 20:00 (fim exclusivo)**, subdividido nos blocos anteriores (26–31/10, 31/10–07/11, 07–14/11, 14–15/11 20h, 15/11 20h–22/11 20h). Esses períodos já foram utilizados no desenvolvimento: **não são holdout independente**.

Ao contrário da soma de R ou dos USDT de operações fictícias com capital inicial sempre =1, este novo modelo:

1. Começa com **1,000000 USDT paper** e **não reinicia o capital entre os cinco blocos**. Mantém uma única posição global até o resultado de TP/SL ou quatro horas. A saída de uma posição pode atravessar limites de bloco, sem abrir outra posição antes dela.
2. Registra **todas as propostas tecnicamente confirmadas** com giro >=5M, inclusive as financeiramente bloqueadas quando a banca era 1 USDT. Para cada proposta, guarda o plano técnico e o contrato público, a abertura do M1 seguinte e o desfecho conservador dos 240 M1 posteriores — estes dados futuros **não participam das decisões de entrada**.
3. Em cada novo sinal quando a carteira está livre, recalcula **finance.evaluate** e o livro sintético do modelo, usando o **saldo paper atual**, taxa e slippage congelados, tamanho mínimo/passo de contratos, margem isolada, alavancagem máxima, custos máximos e buffer de liquidação. Um trade que deixou de caber na banca **não é executado**; se o capital cresceu, uma nova proposta pode tornar-se elegível (não extrapolar uma quantidade estática).
4. Deduplica propostas por `symbol + side + signal_at` usando o menor `plan_id` **entre propostas financeiramente viáveis**, antes de consultar o resultado do trade. Escolhe deterministicamente dentre símbolos concorrentes com uma posição por vez. O filtro RR >=1,5 é aplicado após o plano representativo, conforme experimento original.
5. Usa a evolução da banca: saldo após operação = saldo antes + P&L em USDT estimado com quantidade efetivamente escolhida para **aquele saldo**. A redução da banca reduz a capacidade de abrir novas entradas e pode gerar períodos sem operações. Nenhuma recomposição/aporte automático.
6. Executa seis carteiras separadas: **BASE vs RR >=1,5** sob slippage 0,02%, 0,05% e 0,10% por ponta. Não acrescenta volume, ATR ou filtro A. Mede net USDT, % sobre banca inicial, contagem de trades, ganhos/stop, sequência de perdas, drawdown em USDT e motivos de veto, além de R por operação.

## Limitações e critérios de promoção

- Os preços de entrada e saída são de OHLC M1 e **book sintético**, não preços executáveis garantidos. O spread de 0,02%, taker de 0,06% por ponta e funding zero **são hipóteses não verificadas na conta real**.
- As especificações e tiers de margem dos contratos refletem o catálogo atual, não versões historicamente documentadas.
- Contabilizar saldo paper de 1 USDT não demonstra que uma conta real pode executar todos os contratos mínimos com mesma precisão/lote/funding. O algoritmo reavalia restrições atuais, mas continua sendo simulação.
- A representação do desfecho usa OHLC, assume **SL antes de TP se ambos forem tocados na mesma vela** e saída pessimista se abrir com gap além do SL. O desfecho não pode influenciar elegibilidade, mesmo se armazenado no JSON.
- Precisa de amostra independente temporal e de universo historicamente correto para estimar expectativa futura. **Um retorno paper positivo nestes períodos NÃO é motivo para ativar RR1,5.**
- O resultado deve ser auditável em CSV por trade (saldo antes/depois, contratos, margem, alavancagem, risco, fee+slippage modelados, outcome) e JSON por cenário. Dados de entrada dos cinco blocos e amostras históricas devem ficar como artifacts dos Actions, evitando duplicidade de coleta.

**NÃO alterar** `main`, `scan.yml`, Telegram, `scanner-state`, cronjob.org, `engine.py` ou ordens. Jobs exclusivamente sob `pull_request` e `workflow_dispatch`, sem schedule automático.
