# V3 — hipóteses congeladas antes do teste histórico de rejeição/reteste

Data de registro: 2026-11-20. Escopo: pesquisa sobre SHORT em MEXC Futures. **Este é um experimento diferente de A–E (v2).** Não altera produção, não envia Telegram, não executa ordens, não torna a v2 aprovada.

## Por que mudar a entrada

Em 42 dias, baseline H1/M5 teve 271 seleções, 37 TPs (+40,727R), 63 SLs (-63R), 171 saídas por tempo (-0,781R), retorno de -21,156% com risco simulado de 1% por entrada. As variantes v2 (H4, BTC, H4+BTC, volume) foram negativas. Filtrar melhor **o mesmo tipo de rompimento** não demonstrou vantagem.

## Hipóteses **fixadas antes de avaliar os 42 dias anteriores**

O período de 2026-08-28 11:00 UTC a 2026-10-09 11:00 UTC é o teste retrospectivo menos contaminado disponível: ainda histórico, não prospectivo. Usar 10 ativos fixos: TAO, SOL, AVAX, ENA, DOT, ZEC, HYPE, AAVE, BTC, ETH. Dividir em duas metades cronológicas de 21 dias. **Não mudar regras nem escolher ativos/tempos depois do resultado.**

Versão **F — sweep-rejection** (falso rompimento no M5): somente com H1 fechado e preço H1 abaixo EMA20 H1. M5 atual rompe a máxima dos 24 M5 anteriores em pelo menos 0,10 ATR14 M5; fecha de volta abaixo da máxima anterior e abaixo da abertura; pavio superior é >=40% da amplitude; amplitude total entre 0,8 e 3 ATR14; volume financeiro >=1,5x mediana dos 12 M5 precedentes. Entrada hipotética no open M5 seguinte. SL na máxima do candle de sweep +0,1 ATR; TP 1,8x distância ao SL. Exigir RR líquido ex ante >=1,2. Timeout 120 minutos. É **hipótese**, não sinal validado.

Versão **G — break/retest** (perda e recuperação frustrada do suporte): H1 fechado abaixo EMA20; M5 de rompimento vermelho fecha abaixo da menor mínima dos doze M5 anteriores, com corpo >=0,6 ATR14, volume >=1,5x mediana dos 12 M5 anteriores; nos 3 M5 seguintes, primeiro reteste que tem high >= 99,9% do suporte rompido, close < suporte e close < open; sem aceitar se fechamento estiver >1,2 ATR abaixo suporte. Entrada no M5 seguinte à rejeição; SL maior high desde o rompimento até o reteste +0,1 ATR do rompimento; TP 1,8R. Exigir RR líquido ex ante >=1,2. Timeout 120 minutos. Se não houver reteste em três candles, não opera.

Custos hipotéticos iguais à baseline: taker 0,06% e slippage 0,02% por lado; mesmo "next open" (preenchimento hipotético, não fill real). Se SL e TP tocam no mesmo candle, classificar AMBIGUOUS e penalizar -1R no cálculo. Uma posição por vez na carteira, desempate pelo volume financeiro relativo do instante conhecido. Sem reentrada em mesma moeda antes de encerrar operação.

**Não modificar stop ou alvo após o envio.** Sem taxa de acerto artificial na escolha do ativo. Sem otimização automática de números. Rejeitar informações H1 ainda abertas e qualquer dado que dependa de candles futuros.

## Critérios para considerar candidato a paper prolongado

- Resultado composto líquido positivo em **cada uma** das metades de 21 dias e no total.
- Pelo menos 30 operações selecionadas em 42 dias e <=3 operações por dia.
- Drawdown <=10% com risco hipotético de 1% por trade.
- Melhor que a baseline H1/M5 **na mesma amostra**, não apenas a baseline da janela anterior.
- Se alguma hipótese passar, exige ainda forward test/paper; resultado histórico nunca prova previsibilidade.

Se ambas perderem, rejeitar os novos gatilhos e concentrar trabalho em qualidade da coleta, regime de mercado, custo/execução, classificação de falsos positivos ou outra família de sinais.

## Execução

Arquivo scripts/audit_confluence_v3.py. Execução pela CI isolada da PR. A rotina deve imprimir métricas por período e cada uma das duas variantes. A produção na branch main permanece intacta.
