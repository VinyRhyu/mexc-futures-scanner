# Teste isolado: sustentação de50%do volume no segundo M1

Formações de25/10a07/11/2026, Brasília. [Execução](https://github.com/VinyRhyu/mexc-futures-scanner/actions/runs/42908548312) · [Todos os casos](https://github.com/VinyRhyu/mexc-futures-scanner/actions/runs/42908548312/artifacts/13805857830).

Regra fixada antes desta execução: volume bruto do segundo candle M1 pelo menos metade do volume bruto do primeiro. Igualdade aceita; primeiro volume zero rejeitado. Foram lidos os volumes exatos da coleta original, com checksums validados, conhecidos antes da entrada.

É uma filtragem da referência de dois fechamentos M1. Não foi combinada com proteção no zero, filtro do terço ou outras alterações. TP, SL, faixa, horário, quantidade e custos das entradas aceitas ficaram idênticos.

## Resultado

| Medida | Dois fechamentos M1 | Com sustentação de volume |
| --- | ---: | ---: |
| Entradas únicas | 57 | 28 |
| TP | 18 | 14 |
| SL | 33 | 11 |
| Abertas após4h | 6 | 3 |
| Acerto nas encerradas | 35,3% (18/51) | 56,0% (14/25) |
| Erro nas encerradas | 64,7% | 44,0% |
| Soma R encerradas | +14,31 | +25,42 |

Descartou22stops,4alvos e3abertas. Preservou14/18alvos e11/33stops. A soma deR não é valor em dólares ou ROI de uma carteira; existem operações simultâneas e relacionadas.

## Semanas e direção

| Grupo | Encerradas aceitas | TP | SL | Acerto | R |
| --- | ---: | ---: | ---: | ---: | ---: |
| 25–31/10 | 20 | 11 | 9 | 55,0% | +19,35 |
| 01–07/11 | 5 | 3 | 2 | 60,0% | +6,07 |
| LONG | 18 | 11 | 7 | 61,1% | +21,35 |
| SHORT | 7 | 3 | 4 | 42,9% | +4,07 |

As duas semanas pertencem ao mesmo histórico usado para investigar volume e escolher a hipótese. Não são validação fora da amostra. A segunda semana contém apenas5operações encerradas e o subconjunto SHORT apenas7.

As28entradas representam25combinações distintas de ativo, direção e minuto; nem essas25combinações são necessariamente independentes, pois diferentes moedas participaram do mesmo movimento.

## Interpretação

O resultado sustenta continuar investigando esta regra como candidata experimental. Não demonstra que a taxa futura de acerto será56%, que volume cause as perdas, nem que uma carteira conseguiria executar todas as entradas. Não houve busca de outros percentuais após o resultado e não foi alterada a produção.

## Casos

| ID | Ativo | Direção | Resultado original | Volume segundo/primeiro | Aceita |
| --- | --- | --- | --- | ---: | --- |
| 749eceac357a4859ad79 | BTC_USDT | LONG | STOP | 41.9% | Não |
| cd175928b6cbe3745d66 | BTC_USDT | LONG | STOP | 41.9% | Não |
| 8c0cdce1a4c4af727983 | ZEC_USDT | SHORT | STOP | 30.8% | Não |
| 20c721a880786a40efe8 | SOL_USDT | LONG | STOP | 8.2% | Não |
| edd05b668945b8509344 | XRP_USDT | LONG | STOP | 24.7% | Não |
| 3563d5fc5fd4360c5509 | LINK_USDT | LONG | ALVO | 92.4% | Sim |
| 575703333e48defb373e | LINK_USDT | LONG | ALVO | 38.3% | Não |
| 5eec1b10716029478f6f | LINK_USDT | LONG | ABERTO | 41.5% | Não |
| 97e0b716bbc50721c0ed | TAO_USDT | LONG | STOP | 18.4% | Não |
| 27813bbd6ab936066d7d | TAO_USDT | SHORT | ALVO | 43.6% | Não |
| e15d246b130b51d85c5f | SUI_USDT | LONG | ALVO | 111.8% | Sim |
| e0e152f661760088d57e | SUI_USDT | LONG | STOP | 276.3% | Sim |
| d05a1148311a7e40b6a4 | HYPE_USDT | LONG | STOP | 383.2% | Sim |
| c5dc4f2f23e98d884ffd | HYPE_USDT | LONG | STOP | 383.2% | Sim |
| 7332d02cdaa14acb74e5 | HYPE_USDT | SHORT | STOP | 101.1% | Sim |
| 502dbf28cb8661c4de3b | HYPE_USDT | LONG | STOP | 54.2% | Sim |
| ff91850bf372a0993a82 | HYPE_USDT | LONG | STOP | 54.2% | Sim |
| db5a091d3a5700f4620f | HYPE_USDT | SHORT | STOP | 34.1% | Não |
| e6034a4c47f0f5e2320e | HYPE_USDT | SHORT | ALVO | 55.2% | Sim |
| c95ae9bc74f148b75e15 | HYPE_USDT | SHORT | ALVO | 55.2% | Sim |
| a099b184ee9138c07605 | NEAR_USDT | LONG | STOP | 22.5% | Não |
| 860be863ea3d656ed68b | NEAR_USDT | SHORT | STOP | 5.6% | Não |
| 0dfe0655f44a137054e0 | NEAR_USDT | SHORT | STOP | 14.3% | Não |
| 23fc09306e576e1d7509 | ARB_USDT | LONG | ALVO | 288.6% | Sim |
| 7d9c94bedc0f067d2385 | ARB_USDT | LONG | ALVO | 72.8% | Sim |
| b19ebad5d77fd9f0641c | ARB_USDT | SHORT | STOP | 175.9% | Sim |
| cc39ee066675d01522ce | AVAX_USDT | LONG | ALVO | 255.8% | Sim |
| d869e0d560520c488df0 | AVAX_USDT | LONG | ALVO | 233.1% | Sim |
| 58927fcd0bdb97ef12db | AVAX_USDT | LONG | ABERTO | 3104.2% | Sim |
| bb39799f82912fd4de59 | WLD_USDT | LONG | ALVO | 890.2% | Sim |
| 50fd3bdb48f13d642761 | WLD_USDT | LONG | STOP | 32.1% | Não |
| 3193ae6d486d7bce2146 | ENA_USDT | LONG | STOP | 27.0% | Não |
| 702ceed2c04a6c3a03a2 | ENA_USDT | SHORT | STOP | 18.1% | Não |
| 7aaa2d6afb5a5cba9c76 | ENA_USDT | LONG | STOP | 30.7% | Não |
| 60b2adc9f6d34c64f478 | ENA_USDT | LONG | STOP | 30.7% | Não |
| 5583cb6a9b06d839064c | ENA_USDT | LONG | STOP | 16.8% | Não |
| f2a2e83512dab8e162bf | ENA_USDT | SHORT | STOP | 121.8% | Sim |
| 092c5ccff0b2b13c6f23 | ENA_USDT | SHORT | ALVO | 203.2% | Sim |
| 3f40f57a1445865c42d5 | ENA_USDT | SHORT | ABERTO | 44.7% | Não |
| b7564dfb69f31b7e5998 | ENA_USDT | LONG | STOP | 45.5% | Não |
| 3a2869d9c347b97c58b3 | ENA_USDT | LONG | STOP | 45.5% | Não |
| b705a49ee8fb51611c62 | XLM_USDT | LONG | ALVO | 63.9% | Sim |
| 4bc695584ee61e6bdd24 | XLM_USDT | LONG | ALVO | 79.6% | Sim |
| 50aeec03c60e5b431e3d | INJ_USDT | LONG | ALVO | 1282.9% | Sim |
| fea502a2643da9e92228 | INJ_USDT | LONG | STOP | 42.8% | Não |
| 2bbdd2bca208e00cbe53 | INJ_USDT | LONG | STOP | 2.7% | Não |
| 69e7ba838770785ee257 | INJ_USDT | LONG | STOP | 2.7% | Não |
| 166b339ecc45c281c498 | ONDO_USDT | LONG | STOP | 279.1% | Sim |
| 1c35fded736d1fce7503 | AAVE_USDT | LONG | ALVO | 25.6% | Não |
| 4cc95118dbc0dbf7435b | AAVE_USDT | LONG | ALVO | 25.6% | Não |
| a53d422b16f0556e5a94 | AAVE_USDT | LONG | STOP | 45.9% | Não |
| 4eea637c0610f0b94466 | ONE_USDT | LONG | STOP | 51.8% | Sim |
| 3fe60c8c8c234f353599 | ONE_USDT | SHORT | STOP | 53.3% | Sim |
| 1abbf84c632eff679950 | DOT_USDT | LONG | ALVO | 55.2% | Sim |
| 32b507cb79b6dc84d90e | DOT_USDT | LONG | ABERTO | 4.8% | Não |
| 68eeb7b106aa1747bd56 | DOT_USDT | LONG | ABERTO | 79.2% | Sim |
| 219272d094a9e632288a | BNB_USDT | SHORT | ABERTO | 164.9% | Sim |

## Limites

- Único filtro adicional: volume do segundo candle M1 pelo menos50% do primeiro. Igualdade aceita; primeiro volume zero rejeitado.
- Limite fixado antes desta execução, após diagnóstico anterior no mesmo histórico. Não houve busca de outros limites após o resultado.
- Volumes brutos reconstruídos da coleta original com checksum validado. Ambos já fechados antes da entrada.
- Mesma referência de57operações de25/10–07/11/2026, sem limitar posições simultâneas ou simular carteira.
- Preserva TP, SL, horário de entrada, quantidade e custos da referência. Não combina com proteção no zero nem filtro do terço.
- Acerto mede TP entre encerradas; abertas após4h excluídas da taxa e somaR. R não é dinheiro nem ROI de carteira.
- Sinais podem compartilhar moeda, minuto e movimento; a amostra não contém57eventos independentes.
- Análise no mesmo histórico já explorado, sem validação fora da amostra. Melhora retrospectiva não garante desempenho futuro.
