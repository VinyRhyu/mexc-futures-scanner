# Rastreamento das 57 oportunidades

Auditoria sem alterar sinais, carteira, risco, TP, SL ou dados. O resultado foi idêntico com e sem instrumentação e reproduziu integralmente a carteira anterior: US$50,00 → US$45,87, com16operações.

[Execução](https://github.com/VinyRhyu/mexc-futures-scanner/actions/runs/42894708894) · [Todos os registros](https://github.com/VinyRhyu/mexc-futures-scanner/actions/runs/42894708894/artifacts/13799822421).

## Destino das oportunidades originais

| Destino | Total | Alvos no teste isolado | Stops no teste isolado | Abertas no teste isolado |
| --- | ---: | ---: | ---: | ---: |
| Executadas na carteira | 15 | 4 | 10 | 1 |
| Outra posição já estava aberta | 31 | 12 | 14 | 5 |
| Bloqueadas por custo relativo elevado | 11 | 2 | 9 | 0 |
| Total | 57 | 18 | 33 | 6 |

A carteira abriu ainda uma oportunidade de HYPE fora das57 originalmente viáveis com1USDT: a reavaliação com o saldo corrente permitiu a operação, que terminou em stop de aproximadamente US$3,57. Isso explica15oportunidades comuns e16operações na carteira.

Nenhuma das57foi removida por duplicata ou diretamente por falta de margem. Os11bloqueios financeiros foram todos CUSTO_RELATIVO_ELEVADO. O diagnóstico não estabelece que esse limite deva ser relaxado; nove desses casos foram stops no ensaio independente.

## Concentração do resultado

Os12alvos que ficaram de fora por posição aberta ocorreram enquanto a carteira mantinha um LONG de LINK. Eles se concentraram entre29/10às23h24 e30/10às00h35, Brasília. O próprio LINK executado atingiu o alvo.

O resultado isolado acumula várias participações no mesmo movimento: diferentes moedas e também múltiplas formações da mesma moeda, com níveis ligeiramente diferentes. A deduplicação anterior removia apenas execuções exatamente iguais; os ensaios não eram oportunidades independentes em termos de mercado.

A restrição de uma posição também impediu14entradas que seriam stops e5que permaneciam abertas após4h. Portanto, não se pode somar somente os12alvos perdidos para projetar uma carteira melhor.

## Conclusão limitada a este passo

O rastreamento foi validado e não modificou o resultado. A diferença não decorreu de coleta recente ou regra de confirmação diferente: disponibilidade simultânea de capital, filtro de custos e reavaliação dos lotes mudaram quais operações foram executadas.

O próximo experimento pode estudar distribuição de capital entre posições, preservando limites de margem e risco total. Não foi executado neste passo. Tampouco houve alteração da estratégia de produção.

## Mapa individual

Horários em Brasília. Os resultados da coluna original são retrospectivos e não foram usados para selecionar operações.

| ID | Horário BRT | Ativo | Direção | Resultado isolado | Destino | Motivo/posição ocupante |
| --- | --- | --- | --- | --- | --- | --- |
| 8c0cdce1a4c4af727983 | 2026-10-25 06:15 | ZEC_USDT | SHORT | STOP | BLOQUEADA_FINANCEIRO | CUSTO_RELATIVO_ELEVADO |
| 3193ae6d486d7bce2146 | 2026-10-27 13:19 | ENA_USDT | LONG | STOP | EXECUTADA | — |
| 4eea637c0610f0b94466 | 2026-10-29 02:29 | ONE_USDT | LONG | STOP | EXECUTADA | — |
| 575703333e48defb373e | 2026-10-29 23:17 | LINK_USDT | LONG | ALVO | EXECUTADA | — |
| 3563d5fc5fd4360c5509 | 2026-10-29 23:24 | LINK_USDT | LONG | ALVO | POSICAO_EM_ABERTO | LINK_USDT |
| d869e0d560520c488df0 | 2026-10-29 23:26 | AVAX_USDT | LONG | ALVO | POSICAO_EM_ABERTO | LINK_USDT |
| b705a49ee8fb51611c62 | 2026-10-29 23:27 | XLM_USDT | LONG | ALVO | POSICAO_EM_ABERTO | LINK_USDT |
| cc39ee066675d01522ce | 2026-10-29 23:28 | AVAX_USDT | LONG | ALVO | POSICAO_EM_ABERTO | LINK_USDT |
| 1c35fded736d1fce7503 | 2026-10-30 00:04 | AAVE_USDT | LONG | ALVO | POSICAO_EM_ABERTO | LINK_USDT |
| 4cc95118dbc0dbf7435b | 2026-10-30 00:04 | AAVE_USDT | LONG | ALVO | POSICAO_EM_ABERTO | LINK_USDT |
| 23fc09306e576e1d7509 | 2026-10-30 00:25 | ARB_USDT | LONG | ALVO | POSICAO_EM_ABERTO | LINK_USDT |
| e15d246b130b51d85c5f | 2026-10-30 00:26 | SUI_USDT | LONG | ALVO | POSICAO_EM_ABERTO | LINK_USDT |
| 4bc695584ee61e6bdd24 | 2026-10-30 00:27 | XLM_USDT | LONG | ALVO | POSICAO_EM_ABERTO | LINK_USDT |
| 7d9c94bedc0f067d2385 | 2026-10-30 00:34 | ARB_USDT | LONG | ALVO | POSICAO_EM_ABERTO | LINK_USDT |
| 50aeec03c60e5b431e3d | 2026-10-30 00:34 | INJ_USDT | LONG | ALVO | POSICAO_EM_ABERTO | LINK_USDT |
| bb39799f82912fd4de59 | 2026-10-30 00:35 | WLD_USDT | LONG | ALVO | POSICAO_EM_ABERTO | LINK_USDT |
| 1abbf84c632eff679950 | 2026-10-30 01:33 | DOT_USDT | LONG | ALVO | EXECUTADA | — |
| fea502a2643da9e92228 | 2026-10-30 01:33 | INJ_USDT | LONG | STOP | POSICAO_EM_ABERTO | DOT_USDT |
| 5eec1b10716029478f6f | 2026-10-30 01:48 | LINK_USDT | LONG | ABERTO | POSICAO_EM_ABERTO | DOT_USDT |
| 166b339ecc45c281c498 | 2026-10-30 01:48 | ONDO_USDT | LONG | STOP | POSICAO_EM_ABERTO | DOT_USDT |
| 97e0b716bbc50721c0ed | 2026-10-30 01:48 | TAO_USDT | LONG | STOP | POSICAO_EM_ABERTO | DOT_USDT |
| a099b184ee9138c07605 | 2026-10-30 01:49 | NEAR_USDT | LONG | STOP | POSICAO_EM_ABERTO | DOT_USDT |
| e0e152f661760088d57e | 2026-10-30 01:49 | SUI_USDT | LONG | STOP | POSICAO_EM_ABERTO | DOT_USDT |
| 749eceac357a4859ad79 | 2026-10-30 02:08 | BTC_USDT | LONG | STOP | POSICAO_EM_ABERTO | DOT_USDT |
| cd175928b6cbe3745d66 | 2026-10-30 02:08 | BTC_USDT | LONG | STOP | POSICAO_EM_ABERTO | DOT_USDT |
| c5dc4f2f23e98d884ffd | 2026-10-30 02:08 | HYPE_USDT | LONG | STOP | POSICAO_EM_ABERTO | DOT_USDT |
| d05a1148311a7e40b6a4 | 2026-10-30 02:08 | HYPE_USDT | LONG | STOP | POSICAO_EM_ABERTO | DOT_USDT |
| 20c721a880786a40efe8 | 2026-10-30 02:09 | SOL_USDT | LONG | STOP | POSICAO_EM_ABERTO | DOT_USDT |
| 27813bbd6ab936066d7d | 2026-10-30 04:44 | TAO_USDT | SHORT | ALVO | EXECUTADA | — |
| 219272d094a9e632288a | 2026-10-30 05:50 | BNB_USDT | SHORT | ABERTO | POSICAO_EM_ABERTO | TAO_USDT |
| b19ebad5d77fd9f0641c | 2026-10-30 06:34 | ARB_USDT | SHORT | STOP | POSICAO_EM_ABERTO | TAO_USDT |
| 50fd3bdb48f13d642761 | 2026-10-30 07:55 | WLD_USDT | LONG | STOP | EXECUTADA | — |
| edd05b668945b8509344 | 2026-10-30 12:08 | XRP_USDT | LONG | STOP | EXECUTADA | — |
| 702ceed2c04a6c3a03a2 | 2026-10-30 15:48 | ENA_USDT | SHORT | STOP | EXECUTADA | — |
| a53d422b16f0556e5a94 | 2026-10-30 19:41 | AAVE_USDT | LONG | STOP | EXECUTADA | — |
| 7332d02cdaa14acb74e5 | 2026-10-31 03:13 | HYPE_USDT | SHORT | STOP | BLOQUEADA_FINANCEIRO | CUSTO_RELATIVO_ELEVADO |
| 2bbdd2bca208e00cbe53 | 2026-10-31 03:49 | INJ_USDT | LONG | STOP | BLOQUEADA_FINANCEIRO | CUSTO_RELATIVO_ELEVADO |
| 69e7ba838770785ee257 | 2026-10-31 03:49 | INJ_USDT | LONG | STOP | BLOQUEADA_FINANCEIRO | CUSTO_RELATIVO_ELEVADO |
| 502dbf28cb8661c4de3b | 2026-10-31 08:44 | HYPE_USDT | LONG | STOP | BLOQUEADA_FINANCEIRO | CUSTO_RELATIVO_ELEVADO |
| ff91850bf372a0993a82 | 2026-10-31 08:44 | HYPE_USDT | LONG | STOP | BLOQUEADA_FINANCEIRO | CUSTO_RELATIVO_ELEVADO |
| 60b2adc9f6d34c64f478 | 2026-11-01 18:44 | ENA_USDT | LONG | STOP | BLOQUEADA_FINANCEIRO | CUSTO_RELATIVO_ELEVADO |
| 7aaa2d6afb5a5cba9c76 | 2026-11-01 18:44 | ENA_USDT | LONG | STOP | BLOQUEADA_FINANCEIRO | CUSTO_RELATIVO_ELEVADO |
| 5583cb6a9b06d839064c | 2026-11-01 20:15 | ENA_USDT | LONG | STOP | BLOQUEADA_FINANCEIRO | CUSTO_RELATIVO_ELEVADO |
| f2a2e83512dab8e162bf | 2026-11-02 12:36 | ENA_USDT | SHORT | STOP | EXECUTADA | — |
| 092c5ccff0b2b13c6f23 | 2026-11-02 12:52 | ENA_USDT | SHORT | ALVO | EXECUTADA | — |
| 3f40f57a1445865c42d5 | 2026-11-02 13:24 | ENA_USDT | SHORT | ABERTO | POSICAO_EM_ABERTO | ENA_USDT |
| 860be863ea3d656ed68b | 2026-11-02 15:30 | NEAR_USDT | SHORT | STOP | EXECUTADA | — |
| 0dfe0655f44a137054e0 | 2026-11-02 15:35 | NEAR_USDT | SHORT | STOP | POSICAO_EM_ABERTO | NEAR_USDT |
| db5a091d3a5700f4620f | 2026-11-03 00:23 | HYPE_USDT | SHORT | STOP | EXECUTADA | — |
| 3fe60c8c8c234f353599 | 2026-11-03 00:36 | ONE_USDT | SHORT | STOP | POSICAO_EM_ABERTO | HYPE_USDT |
| c95ae9bc74f148b75e15 | 2026-11-05 07:47 | HYPE_USDT | SHORT | ALVO | BLOQUEADA_FINANCEIRO | CUSTO_RELATIVO_ELEVADO |
| e6034a4c47f0f5e2320e | 2026-11-05 07:47 | HYPE_USDT | SHORT | ALVO | BLOQUEADA_FINANCEIRO | CUSTO_RELATIVO_ELEVADO |
| 3a2869d9c347b97c58b3 | 2026-11-05 16:18 | ENA_USDT | LONG | STOP | EXECUTADA | — |
| b7564dfb69f31b7e5998 | 2026-11-05 16:18 | ENA_USDT | LONG | STOP | POSICAO_EM_ABERTO | ENA_USDT |
| 68eeb7b106aa1747bd56 | 2026-11-05 21:33 | DOT_USDT | LONG | ABERTO | EXECUTADA | — |
| 32b507cb79b6dc84d90e | 2026-11-05 21:34 | DOT_USDT | LONG | ABERTO | POSICAO_EM_ABERTO | DOT_USDT |
| 58927fcd0bdb97ef12db | 2026-11-05 21:35 | AVAX_USDT | LONG | ABERTO | POSICAO_EM_ABERTO | DOT_USDT |
