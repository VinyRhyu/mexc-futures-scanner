# BRK-T: rompimento de compressão e continuidade (LONG e SHORT)

Pré-registro 20/11/2026, antes do replay deste modelo. Pesquisa isolada, não altera main, Telegram ou ordens. Baseline F congelada; SMC-R é referência secundária reprovada. Não ajustar parâmetros após visualizar resultados.

## Regras causais fechadas

M5 para gatilho e H1 para direção, apenas candles FECHADOS. Para candle de sinal i:
- Contexto: EMA20 H1 e EMA50 H1 calculadas exclusivamente com fechamentos H1 disponíveis no momento; LONG exige close H1 > EMA20 > EMA50, SHORT exige close H1 < EMA20 < EMA50.
- Compressão: candles M5 de i-12 até i-1 devem ter amplitude total (max high - min low) <= 3.0 vezes ATR14 M5 calculado até i-1. O ATR14 usa apenas candles anteriores a i.
- Breakout: close[i] acima do high da compressão (LONG) ou abaixo do low (SHORT), por >=0,10 ATR14; corpo do candle na direção >=0,60 ATR14; quote volume do candle >=1,5 vezes mediana dos 12 anteriores; candle range <=3 ATR14.
- Entrada: abertura do M5 seguinte; stop no extremo oposto da faixa comprimida +/-0,1 ATR14, alvo 1,8R bruto; rejeitar RR líquido <1,2 após taxas.
- Saída: TP, SL ou TIME em 24 candles M5 (2h), com prioridade conservadora SL se ambos tocarem a mesma vela; saída por TIME a mercado.
- Custos: taker 0,06% e slippage 0,02% POR LADO, hipotéticos. Risco 1% saldo por trade. Uma posição por ativo e no máximo uma posição global; empate de sinais pela maior razão de quote volume conhecido, seguido do símbolo.
- Testar LONG e SHORT separadamente, e também uma carteira combinada (não somar carteiras separadas como se independentes). Não excluir moedas perdedoras retrospectivamente.

## Histórico pré-fixado

Contratos TAO, SOL, AVAX, ENA, DOT, ZEC, HYPE, AAVE, BTC, ETH; quatro blocos T, U, V, W de 42 dias, idênticos ao teste SMC-R:
- T 2026-06-05T11:00Z a 2026-07-17T11:00Z
- U 2026-07-17T11:00Z a 2026-08-28T11:00Z
- V 2026-08-28T11:00Z a 2026-10-09T11:00Z
- W 2026-10-09T11:00Z a 2026-11-20T11:00Z

A mesma janela já foi usada em pesquisa anterior, logo NÃO é teste prospectivo independente. Reportar erros de cobertura; não preencher candles faltantes; não selecionar períodos favoráveis.

## Aprovação

Só considerar candidato para PAPER prospectivo se retorno líquido positivo nos quatro blocos, >=40 operações selecionadas, <=3 operações/dia, DD contínuo <=10% com 1% risco, retorno superior a F, robustez a custos dobrados e sem falhas de causalidade. Nunca integrar diretamente ao Telegram após backtest. Se falhar, registrar o resultado e não tunar para encaixar no passado.
