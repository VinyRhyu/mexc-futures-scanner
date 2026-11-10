# Carteira cronológica: 50 USDT

Formações de 25/10 a 07/11/2026, Brasília, usando a coleta congelada e a regra de dois fechamentos M1. [Execução](https://github.com/VinyRhyu/mexc-futures-scanner/actions/runs/42892334331) · [Resultado completo](https://github.com/VinyRhyu/mexc-futures-scanner/actions/runs/42892334331/artifacts/13797849011).

| Medida | Resultado |
| --- | ---: |
| Saldo inicial | US$ 50,00 |
| Saldo final | US$ 45,87 |
| Resultado líquido | -US$ 4,13 (-8,25%) |
| Operações | 16 |
| Alvos | 4 |
| Stops | 11 |
| Encerramento por tempo com lucro | 1 |
| Maior drawdown de saldo realizado | 36,87% |

Uma posição por vez; risco até10% do saldo atualizado; lotes, margem, alavancagem e custos recalculados; encerramento após4h se não atingir TP/SL. Todas as confirmações elegíveis são reavaliadas, inclusive as bloqueadas na simulação independente de1USDT. Ordem cronológica e desempate por símbolo/ID, sem escolher pelo resultado futuro.

O saldo chegou a US$68,31 e terminou em US$45,87. A posição encerrada por tempo rendeu aproximadamente US$2,75. O drawdown informado mede saldo realizado, não oscilação intraposição.

O resultado não reproduziu os +US$71,56 da conversão simbólica anterior. Aquela soma ignorava disponibilidade simultânea de capital e não recalculava a exposição com o saldo. Este cenário inclui esses limites, mas ainda idealiza execuções, livro, funding e latência.

## Limites

- Uma posição por vez; ordem cronológica. Empates resolvidos por símbolo e ID, sem usar resultados futuros.
- Risco até10% do saldo atualizado, sem aportes; lotes, margem, alavancagem até20x e custos recalculados para cada entrada.
- Inclui confirmações antes bloqueadas financeiramente com1USDT: reavalia todas com o saldo disponível.
- TP/SL/faixa congelados no primeiro gatilho. Entrada após segundo fechamento M1; nenhuma regra nova de sinal.
- Posições ainda abertas após4h são encerradas no último fechamento conhecido, com custos de saída.
- Drawdown mede saldos realizados; não inclui oscilação intraposição ou margem de manutenção em tempo real.
- Mesmo histórico usado para escolher a regra: análise exploratória sem validação fora da amostra.
- Funding zero, livro infinito e fills hipotéticos; taxas0,06% por lado, spread0,02%, slippage configurado ou2ticks.
- Contratos e universo congelados da coleta; preço LAST não reproduz necessariamente gatilho FAIR. Monitoramento M1 e latência idealizados.

A estratégia continua sem validação fora da amostra e não deve ser considerada validada para uso com dinheiro por este teste. A produção não foi alterada.

## Operações

| Entrada UTC | Ativo | Direção | Saída | Resultado USDT | Saldo |
| --- | --- | --- | --- | ---: | ---: |
| 2026-10-27T16:19:00+00:00 | ENA_USDT | LONG | STOP | -4.6557 | 45.3443 |
| 2026-10-29T05:29:00+00:00 | ONE_USDT | LONG | STOP | -3.9945 | 41.3498 |
| 2026-10-29T20:34:00+00:00 | HYPE_USDT | SHORT | STOP | -3.5726 | 37.7772 |
| 2026-10-30T02:17:00+00:00 | LINK_USDT | LONG | ALVO | 9.1344 | 46.9116 |
| 2026-10-30T04:33:00+00:00 | DOT_USDT | LONG | ALVO | 9.8672 | 56.7787 |
| 2026-10-30T07:44:00+00:00 | TAO_USDT | SHORT | ALVO | 11.5327 | 68.3114 |
| 2026-10-30T10:55:00+00:00 | WLD_USDT | LONG | STOP | -6.3948 | 61.9166 |
| 2026-10-30T15:08:00+00:00 | XRP_USDT | LONG | STOP | -5.4774 | 56.4392 |
| 2026-10-30T18:48:00+00:00 | ENA_USDT | SHORT | STOP | -4.2482 | 52.1911 |
| 2026-10-30T22:41:00+00:00 | AAVE_USDT | LONG | STOP | -4.6207 | 47.5703 |
| 2026-11-02T15:36:00+00:00 | ENA_USDT | SHORT | STOP | -3.4681 | 44.1022 |
| 2026-11-02T15:52:00+00:00 | ENA_USDT | SHORT | ALVO | 11.9230 | 56.0252 |
| 2026-11-02T18:30:00+00:00 | NEAR_USDT | SHORT | STOP | -4.5241 | 51.5011 |
| 2026-11-03T03:23:00+00:00 | HYPE_USDT | SHORT | STOP | -4.1010 | 47.4001 |
| 2026-11-05T19:18:00+00:00 | ENA_USDT | LONG | STOP | -4.2763 | 43.1238 |
| 2026-11-06T00:33:00+00:00 | DOT_USDT | LONG | ENCERRAMENTO_4H | 2.7490 | 45.8728 |
