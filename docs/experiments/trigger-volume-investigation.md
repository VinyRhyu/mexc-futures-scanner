# Volume relativo no gatilho: investigação descritiva

Coleta congelada de25/10a07/11/2026. Todas as57operações têm dados válidos de volume. Elas representam49combinações distintas de ativo, direção e minuto; portanto, não são57observações independentes.

[Execução](https://github.com/VinyRhyu/mexc-futures-scanner/actions/runs/42906417587) · [Dados e todos os casos](https://github.com/VinyRhyu/mexc-futures-scanner/actions/runs/42906417587/artifacts/13805830712).

## Métrica fixada antes da investigação

Volume médio dos dois candles M1 de gatilho dividido pela média de volume dos20candles M1 anteriores ao primeiro. Os dois candles de gatilho ficam fora da média histórica. A medida já está disponível no fechamento da confirmação, antes da entrada. Foram fixadas três faixas: menor1x, de1xatémenos2x e2xoumais. Nenhuma regra de seleção foi aplicada ou otimizada.

## Resultado por volume relativo

| RVOL dos dois candles | Operações | Alvos | Stops | Abertas4h | Acerto encerradas | R encerradas |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Menor1x | 19 | 7 | 10 | 2 | 41,2% | +9,22 |
| De1xatémenos2x | 18 | 6 | 10 | 2 | 37,5% | +4,77 |
| 2xoumais | 20 | 5 | 13 | 2 | 27,8% | +0,32 |
| Referência completa | 57 | 18 | 33 | 6 | 35,3% | +14,31 |

A hipótese de que falta de volume explicaria os stops não é sustentada neste recorte. Exigir volume muito alto selecionaria um grupo com acerto menor, não maior. Isso não demonstra que volume alto cause perdas.

Mediana RVOL conjunto:1,28x nos18alvos e1,89x nos33stops. Os intervalos se sobrepõem bastante: valores de volume não separam perfeitamente os grupos.

## Primeiro e segundo candle

| Grupo | Mediana RVOL primeiro candle | Mediana RVOL segundo candle |
| --- | ---: | ---: |
| Alvos | 1,03x | 1,02x |
| Stops | 2,66x | 1,05x |

Como diagnóstico derivado após a investigação, a mediana da razão individual volume do segundo/primeiro foi76,2% nosalvos e41,9% nosstops. Isso levanta a hipótese de que um pico seguido de queda de atividade seja diferente de volume sustentado. Não identifica quem comprou/vendeu nem prova exaustão do movimento; não é um filtro validado.

## Heterogeneidade

O grupo menor1x teve7alvos e7stops em25–31/10, mas0alvos e3stops em01–07/11. Entre LONGs teve7alvos/8stops/1aberta; entre SHORTs,0alvos/2stops/1aberta. Logo, escolher simplesmente o grupo de menor volume após olhar a tabela seria precipitado.

O volume conjunto mediano dos stops excedeu o dos alvos nas duas semanas, mas as amostras são pequenas e concentradas em movimentos de mercado já conhecidos. A diferença foi mais clara nos LONGs; não há separação uniforme nos SHORTs.

## Conclusão deste passo

Não há suporte para adicionar uma exigência genérica de volume alto. A sustentação do volume entre primeiro e segundo candle é apenas uma hipótese para investigação futura, com regra fixada antes de novo teste e checagem independente. Não foi implementado filtro novo, proteção de saída ou mudança de produção.

## Casos individuais

| ID | Ativo | Direção | Resultado | RVOL conjunto | RVOL primeiro | RVOL segundo |
| --- | --- | --- | --- | ---: | ---: | ---: |
| 749eceac357a4859ad79 | BTC_USDT | LONG | STOP | 1.891 | 2.664 | 1.117 |
| cd175928b6cbe3745d66 | BTC_USDT | LONG | STOP | 1.891 | 2.664 | 1.117 |
| 8c0cdce1a4c4af727983 | ZEC_USDT | SHORT | STOP | 3.655 | 5.587 | 1.723 |
| 20c721a880786a40efe8 | SOL_USDT | LONG | STOP | 0.604 | 1.116 | 0.092 |
| edd05b668945b8509344 | XRP_USDT | LONG | STOP | 4.718 | 7.565 | 1.871 |
| 3563d5fc5fd4360c5509 | LINK_USDT | LONG | ALVO | 0.912 | 0.948 | 0.876 |
| 575703333e48defb373e | LINK_USDT | LONG | ALVO | 2.155 | 3.116 | 1.195 |
| 5eec1b10716029478f6f | LINK_USDT | LONG | ABERTO | 0.832 | 1.176 | 0.488 |
| 97e0b716bbc50721c0ed | TAO_USDT | LONG | STOP | 2.096 | 3.541 | 0.652 |
| 27813bbd6ab936066d7d | TAO_USDT | SHORT | ALVO | 3.973 | 5.535 | 2.412 |
| e15d246b130b51d85c5f | SUI_USDT | LONG | ALVO | 0.871 | 0.822 | 0.919 |
| e0e152f661760088d57e | SUI_USDT | LONG | STOP | 1.458 | 0.775 | 2.142 |
| d05a1148311a7e40b6a4 | HYPE_USDT | LONG | STOP | 0.768 | 0.318 | 1.218 |
| c5dc4f2f23e98d884ffd | HYPE_USDT | LONG | STOP | 0.768 | 0.318 | 1.218 |
| 7332d02cdaa14acb74e5 | HYPE_USDT | SHORT | STOP | 3.114 | 3.097 | 3.131 |
| 502dbf28cb8661c4de3b | HYPE_USDT | LONG | STOP | 9.363 | 12.144 | 6.582 |
| ff91850bf372a0993a82 | HYPE_USDT | LONG | STOP | 9.363 | 12.144 | 6.582 |
| db5a091d3a5700f4620f | HYPE_USDT | SHORT | STOP | 3.445 | 5.136 | 1.754 |
| e6034a4c47f0f5e2320e | HYPE_USDT | SHORT | ALVO | 1.308 | 1.686 | 0.930 |
| c95ae9bc74f148b75e15 | HYPE_USDT | SHORT | ALVO | 1.308 | 1.686 | 0.930 |
| a099b184ee9138c07605 | NEAR_USDT | LONG | STOP | 2.869 | 4.684 | 1.055 |
| 860be863ea3d656ed68b | NEAR_USDT | SHORT | STOP | 4.506 | 8.534 | 0.479 |
| 0dfe0655f44a137054e0 | NEAR_USDT | SHORT | STOP | 1.526 | 2.670 | 0.382 |
| 23fc09306e576e1d7509 | ARB_USDT | LONG | ALVO | 1.253 | 0.645 | 1.861 |
| 7d9c94bedc0f067d2385 | ARB_USDT | LONG | ALVO | 1.120 | 1.296 | 0.944 |
| b19ebad5d77fd9f0641c | ARB_USDT | SHORT | STOP | 1.664 | 1.206 | 2.122 |
| cc39ee066675d01522ce | AVAX_USDT | LONG | ALVO | 1.964 | 1.104 | 2.824 |
| d869e0d560520c488df0 | AVAX_USDT | LONG | ALVO | 2.885 | 1.732 | 4.038 |
| 58927fcd0bdb97ef12db | AVAX_USDT | LONG | ABERTO | 1.747 | 0.109 | 3.384 |
| bb39799f82912fd4de59 | WLD_USDT | LONG | ALVO | 2.003 | 0.405 | 3.602 |
| 50fd3bdb48f13d642761 | WLD_USDT | LONG | STOP | 1.707 | 2.584 | 0.829 |
| 3193ae6d486d7bce2146 | ENA_USDT | LONG | STOP | 3.407 | 5.366 | 1.448 |
| 702ceed2c04a6c3a03a2 | ENA_USDT | SHORT | STOP | 0.963 | 1.631 | 0.296 |
| 7aaa2d6afb5a5cba9c76 | ENA_USDT | LONG | STOP | 0.452 | 0.692 | 0.213 |
| 60b2adc9f6d34c64f478 | ENA_USDT | LONG | STOP | 0.452 | 0.692 | 0.213 |
| 5583cb6a9b06d839064c | ENA_USDT | LONG | STOP | 2.309 | 3.953 | 0.665 |
| f2a2e83512dab8e162bf | ENA_USDT | SHORT | STOP | 1.564 | 1.410 | 1.718 |
| 092c5ccff0b2b13c6f23 | ENA_USDT | SHORT | ALVO | 2.395 | 1.580 | 3.211 |
| 3f40f57a1445865c42d5 | ENA_USDT | SHORT | ABERTO | 4.032 | 5.574 | 2.490 |
| b7564dfb69f31b7e5998 | ENA_USDT | LONG | STOP | 1.978 | 2.719 | 1.237 |
| 3a2869d9c347b97c58b3 | ENA_USDT | LONG | STOP | 1.978 | 2.719 | 1.237 |
| b705a49ee8fb51611c62 | XLM_USDT | LONG | ALVO | 0.608 | 0.742 | 0.474 |
| 4bc695584ee61e6bdd24 | XLM_USDT | LONG | ALVO | 0.580 | 0.646 | 0.514 |
| 50aeec03c60e5b431e3d | INJ_USDT | LONG | ALVO | 0.589 | 0.085 | 1.093 |
| fea502a2643da9e92228 | INJ_USDT | LONG | STOP | 0.296 | 0.414 | 0.177 |
| 2bbdd2bca208e00cbe53 | INJ_USDT | LONG | STOP | 12.253 | 23.863 | 0.642 |
| 69e7ba838770785ee257 | INJ_USDT | LONG | STOP | 12.253 | 23.863 | 0.642 |
| 166b339ecc45c281c498 | ONDO_USDT | LONG | STOP | 0.711 | 0.375 | 1.047 |
| 1c35fded736d1fce7503 | AAVE_USDT | LONG | ALVO | 0.375 | 0.597 | 0.153 |
| 4cc95118dbc0dbf7435b | AAVE_USDT | LONG | ALVO | 0.375 | 0.597 | 0.153 |
| a53d422b16f0556e5a94 | AAVE_USDT | LONG | STOP | 1.027 | 1.408 | 0.647 |
| 4eea637c0610f0b94466 | ONE_USDT | LONG | STOP | 0.844 | 1.112 | 0.576 |
| 3fe60c8c8c234f353599 | ONE_USDT | SHORT | STOP | 0.912 | 1.189 | 0.634 |
| 1abbf84c632eff679950 | DOT_USDT | LONG | ALVO | 1.633 | 2.103 | 1.162 |
| 32b507cb79b6dc84d90e | DOT_USDT | LONG | ABERTO | 1.230 | 2.348 | 0.112 |
| 68eeb7b106aa1747bd56 | DOT_USDT | LONG | ABERTO | 2.781 | 3.105 | 2.457 |
| 219272d094a9e632288a | BNB_USDT | SHORT | ABERTO | 0.365 | 0.275 | 0.454 |

## Limites

- Métrica principal pré-definida: média do volume dos dois candles M1 de gatilho dividida pela média dos20minutos anteriores ao primeiro candle.
- Os dois volumes e a média histórica já são conhecidos antes da entrada. Não usa volume de candles posteriores nem o candle15m ainda aberto.
- Volumes são normalizados dentro de cada contrato. Dados OHLCV medem atividade, não agressão compradora/vendedora nem causa do movimento.
- Faixas fixadas antes do resultado: menor1x, de1x até menos2x e2xoumais. Não houve busca de melhor limiar ou alteração dos sinais.
- Grupo de57operações já explorado, incluindo sinais próximos e mesmo movimento de mercado. Associação retrospectiva não é previsão ou validação causal.
- Acerto considera apenas TP entre encerradas; abertas após4h ficam separadas. ResultadoR inclui os custos hipotéticos anteriores e não é carteira.
- Resumo por semana e direção mostra heterogeneidade; subgrupos pequenos não sustentam estimativa confiável de desempenho futuro.
