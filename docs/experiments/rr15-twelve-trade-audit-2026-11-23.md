# Auditoria de 12 entradas selecionadas por RR líquido >=1,5

Data: 23/11/2026. Pesquisa a partir do PR #13, em branch independente, sem mudanças de scanner, `main`, Telegram, cronjob.org, ordens ou carteira.

## Objetivo

Reconstruir exatamente as **12 operações hipoteticamente selecionadas** no teste complementar de 1 USDT, sem o filtro A:

- 26/10/2026 00:00 a 31/10/2026 00:00 UTC: 4 operações, +3,0442 R;
- 14/11/2026 00:00 a 15/11/2026 20:00 UTC: 8 operações, −3,1305 R;
- conjunto: 12 operações, **3 com R > 0**, total −0,0864 R.

Preços de entrada são estimativas na abertura da vela M1 seguinte; TP/SL são os níveis técnicos originais; saída pelo primeiro toque M1 (SL tem precedência se SL e TP no mesmo candle) ou tempo de 4h. Sem fills reais, histórico de livro, funding real ou spreads personalizados.

## Seleção cronológica — sem olhar resultado

1. Mesmo universo de 24 símbolos congelados no snapshot 23/11, SHA256 `edf08de9b2c1027c7631069a9b86baa73febd799c56fc8c2edf2274bc82601a1`. Há viés de sobrevivência; não equivale ao top50 real no momento histórico.
2. Exigir giro histórico de 24h dos 1440 candles M1 anteriores >=5 milhões USDT, com 24/24 símbolos completos.
3. Executar avaliador financeiro original com saldo paper de 1 USDT, taker assumido 0,06% por ponta, spread total sintético 0,02%, slippage base 0,02% por ponta e profundidade sintética; RR líquido estimado >=1,5 na cotação simulada na abertura M1 seguinte.
4. Deduplicar planos com o mesmo ativo + direção + minuto: escolher deterministicamente o menor `plan_id` **entre propostas financeiramente viáveis**, sem consultar TP/SL realizados.
5. Refazer carteira global de uma posição por vez, ordenando por entrada. **Só depois** consultar os desfechos e classificar vencedoras vs perdedoras. Exports devem conter 4 e 8 registros respectivamente, ou falhar.

## Informações estritamente conhecidas antes da entrada

Medir no candle de confirmação M1 e velas anteriores, nunca no candle seguinte ou após TP/SL:
- volume M1 / volume médio dos 20 M1 anteriores;
- corpo / amplitude total do candle M1;
- localização do fechamento dentro do range M1, orientada a LONG/SHORT;
- amplitude M1 / ATR(14) da última vela M15 **fechada**;
- deslocamento de preço na direção da operação nos últimos 60 M1 / ATR M15;
- deslocamento nos últimos 240 M1 / ATR M15 (hipótese A anterior);
- deslocamento na direção da operação entre o M15 fechado agora e 2h antes / ATR M15;
- estado H1 com pivôs conhecidos no instante (não usar pivôs posteriormente confirmados);
- RR líquido projetado, stop e alvo, preço de entrada estimado, giro de 24h, risco da entrada até stop;
- número de minutos até desfecho e R líquido só para **diagnóstico ex-post**, nunca para decidir um filtro.

**Importante:** a comparação das medianas de 3 vencedoras vs 9 perdedoras é meramente exploratória. Não escolher novo limiar nas mesmas 12 operações e depois chamá-lo de estatisticamente validado. Um limiar candidato precisa ser formalizado e validado em outra amostra, com custo adverso.

## Regressões obrigatórias

Provar com teste que adulterar candle posterior não modifica features de confirmação; M15 ainda aberto é recusado; deduplicação não consulta desfecho; RR mínimo usa cotação anterior à saída; resultados da carteira original reproduzem o PR #13. Se as saídas não coincidirem, interromper e auditar o motivo, não publicar diagnóstico.
