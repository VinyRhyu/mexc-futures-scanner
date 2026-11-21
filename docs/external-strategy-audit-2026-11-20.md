# Auditoria de repositórios externos — 20/11/2026

Status: pesquisa isolada. Sem ordens, Telegram ou alterações em main.
Baseline F falso rompimento: retorno histórico ~-5,11% nos 126 dias testados; não é estratégia aprovada.

## Opções verificadas

1. **TDZNBEER/crypto-backtest-lab** (MIT): strategy_trend_pullback.py implementa LONG e SHORT seguindo inclinação e EMA de tendência, após retorno pela EMA rápida. Defaults EMA20, trendLen100, stop 1,5 ATR, TP 2R. Também oferece run_walkforward.py e run_regime.py. https://github.com/TDZNBEER/crypto-backtest-lab

2. **Pasha0313/Algo_Trading** (MIT): Strategy.py tem estratégia EMA+ADX LONG/SHORT; Strategy_Selector.py fornece seleção com holdout. O repositório declara backtest MEXC via ccxt; não implica suporte a execução real de futuros MEXC. https://github.com/Pasha0313/Algo_Trading

**ALERTA de bug real**: na implementação Donchian de Pasha, Upper_Band = High.rolling(n).max() inclui o próprio candle, mas o sinal pede Close > Upper_Band; é matematicamente impossível em candles OHLC válidos. A condição SHORT Close < Lower_Band também é impossível. Não copiar estratégias sem auditoria causal.

3. **SinanGokmen/crypto-quant-lab** (MIT): triple-barrier, meta-labeling, purged K-fold, Monte Carlo e forward/paper. Documenta resultados majoritariamente negativos fora da amostra. Evitar ML com apenas dezenas de trades F. https://github.com/SinanGokmen/crypto-quant-lab

4. **gistrec/trade-lab** (MIT): TSMOM e regime de mercado, walk-forward, proteção contra otimização excessiva. Seu TSMOM publicado é long-only, com horizonte distinto de SHORT M5. https://github.com/gistrec/trade-lab

5. **ccxt/ccxt** (MIT): normalização e coleta de dados entre exchanges, com validação explícita de contratos MEXC Futures e limites de API. https://github.com/ccxt/ccxt

6. **nautechsystems/nautilus_trader** (LGPLv3): execução event-driven com ticks, order book e replay, útil depois de provar edge básico. Não é estratégia pronta. https://github.com/nautechsystems/nautilus_trader

## Proposta de próximo teste — ainda NÃO executado

Comparar A = F_sweep_rejection (SHORT) contra B = Trend Pullback EMA20/EMA100 1,5ATR/2R (LONG e SHORT) e C = EMA+ADX de Pasha (LONG e SHORT), parâmetros originais auditados e congelados.

Manter dados MEXC, 10 ativos fixos, candles fechados, entrada hipotética no próximo open, 1 posição simultânea por carteira, custos em duplicidade como estresse, max drawdown, SL/TP, timeouts, expectativa em R por direção/regime e três janelas cronológicas de 42 dias.

Critério de avanço: ROI líquido positivo em todas as janelas, >=50 operações em 126 dias, média <=2 trades/dia, DD <=10% a 1% de risco/trade, e obrigatoriamente paper prospectivo. Sem tuning para forçar lucro.

Coleta: a última varredura em 59/60 perps líquidos íntegros sinalizou nenhum novo falso rompimento às 11h35 BRT; a tentativa sem controle de taxa teve 921 erros de API 510. Priorizar lotes, cache, integridade de série, volume >=2M USDT/dia e filtro financeiro ex ante.

Nota: nenhuma estratégia externa foi portada ou validada financeiramente por este documento.