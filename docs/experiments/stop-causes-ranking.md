# Investigação dos 33 stops e ranking de contrafactuais

[Execução](https://github.com/VinyRhyu/mexc-futures-scanner/actions/runs/42903408245) · [Todos os casos](https://github.com/VinyRhyu/mexc-futures-scanner/actions/runs/42903408245/artifacts/13803198692).

Os57sinais originais foram reconstruídos com resultado idêntico:33stops,18alvos,6abertas. Referência de comparação: +14,31R encerradas. Cada hipótese foi aplicada isoladamente a todos os57, com custos. Esta é uma auditoria retrospectiva e não valida uma regra nova.

## O caminho antes e depois dos stops

- 25/33 não fecharam em+0,5R líquido antes do minuto do stop; somente8atingiram esse avanço em fechamento.
- 5/33 fecharam em+1R líquido antes do stop. Por pavios de minutos anteriores,6tocaram+1R.
- Nenhum stop ocorreu nos primeiros5minutos. Tempo mediano até stop:32minutos, faixa7–190minutos.
- 7/33 atingiram o TP original após o stop, ainda dentro da janela original de4h.
- Os33voltaram a fechar dentro da consolidação antes do stop. Essa característica é influenciada pela própria geometria do SL e não demonstra uma causa externa.

As medidas de avanço excluem o candle em que ocorre o stop, porque a ordem dos extremos dentro dele é desconhecida. Esses indicadores descrevem continuidade e devolução do movimento; não identificam causas como liquidações, notícias ou agressão de ordens.

## Ranking por stops convertidos em alvo no caminho do preço

| Ajuste isolado | Stops→alvo | R encerradas nos57 | Compatibilidade com regras atuais |
| --- | ---: | ---: | --- |
| SL além do extremo dos8candles15m anteriores, com buffer0,1ATR | 7 | +10,15 | 0/57passam RR mínimo2 |
| TP líquido de1R | 6 | +1,17 | 0/57liberadas; altera o alvo e o RR |
| TP líquido de1,5R | 1 | -1,91 | 0/57liberadas; altera o alvo e o RR |
| Proteção no zero líquido depois de fechamento+1R | 0 | +17,05 | 57/57passam; evita perdas, não transforma em TP |
| Entrada após recuo0,25da distância ao SL, em até15min | 0 | -1,00 | Uma entrada viável, que terminou em stop |

As três primeiras linhas são contrafactuais de preço, não operações liberadas. Alvo menor não significa ter previsto corretamente o TP original. No SL estrutural, o aumento da distância exige reduzir a posição para comparar em unidades iguais de risco e elimina o RR2:1. O resultado bruto ainda teve24abertas,25alvos e8stops; não se pode contabilizar essas24abertas como sucessos.

O recuo conservou a faixa original:29casos ficaram fora dela e27não ofereceram o recuo previsto. Não foi criada uma faixa nova retrospectivamente.

## Ajuste mais útil entre os avaliados sob as regras atuais

A proteção após fechamento conhecido de+1R manteve o TP original e o risco inicial. O stop estimado de zero líquido só vale a partir do minuto seguinte, com custos; gaps podem produzir perda.

| Resultado | Referência | Proteção após+1R |
| --- | ---: | ---: |
| TP original | 18 | 17 |
| Stop original | 33 | 28 |
| Saída próxima do zero líquido | 0 | 7 |
| Abertas após4h | 6 | 5 |
| R encerradas | +14,31 | +17,05 |

As7proteções eram5stops,1alvo e1posição aberta na referência. Portanto, cinco perdas foram evitadas ao custo de perder um alvo. As proteções nesta amostra tiveram resultado líquido pequeno positivo por arredondamento ao tick; não devem ser classificadas como TP nem vitória de previsão.

Esta é a candidata mais útil para um próximo teste isolado de gestão da saída, não prova de melhora da previsão. Foi observada no mesmo histórico já explorado, sem validação independente, e não foi aplicada em produção.

## Stops individuais

| ID | Ativo | Direção | Minutos até SL | Melhor fechamento antes SL, R | TP original depois SL em4h |
| --- | --- | --- | ---: | ---: | --- |
| 749eceac357a4859ad79 | BTC_USDT | LONG | 155 | 0.330 | Não |
| cd175928b6cbe3745d66 | BTC_USDT | LONG | 155 | 0.337 | Não |
| 8c0cdce1a4c4af727983 | ZEC_USDT | SHORT | 7 | 0.339 | Não |
| 20c721a880786a40efe8 | SOL_USDT | LONG | 156 | 0.885 | Não |
| edd05b668945b8509344 | XRP_USDT | LONG | 27 | 1.019 | Não |
| 97e0b716bbc50721c0ed | TAO_USDT | LONG | 71 | 0.379 | Não |
| e0e152f661760088d57e | SUI_USDT | LONG | 173 | 1.163 | Não |
| d05a1148311a7e40b6a4 | HYPE_USDT | LONG | 50 | 0.328 | Não |
| c5dc4f2f23e98d884ffd | HYPE_USDT | LONG | 50 | 0.334 | Não |
| 7332d02cdaa14acb74e5 | HYPE_USDT | SHORT | 32 | 0.000 | Sim |
| 502dbf28cb8661c4de3b | HYPE_USDT | LONG | 13 | 0.431 | Não |
| ff91850bf372a0993a82 | HYPE_USDT | LONG | 13 | 0.438 | Não |
| db5a091d3a5700f4620f | HYPE_USDT | SHORT | 32 | 0.148 | Não |
| a099b184ee9138c07605 | NEAR_USDT | LONG | 73 | 1.106 | Sim |
| 860be863ea3d656ed68b | NEAR_USDT | SHORT | 96 | 1.401 | Não |
| 0dfe0655f44a137054e0 | NEAR_USDT | SHORT | 89 | 1.087 | Não |
| b19ebad5d77fd9f0641c | ARB_USDT | SHORT | 51 | 0.000 | Não |
| 50fd3bdb48f13d642761 | WLD_USDT | LONG | 68 | 0.437 | Não |
| 3193ae6d486d7bce2146 | ENA_USDT | LONG | 29 | 0.000 | Não |
| 702ceed2c04a6c3a03a2 | ENA_USDT | SHORT | 9 | 0.276 | Não |
| 7aaa2d6afb5a5cba9c76 | ENA_USDT | LONG | 22 | 0.000 | Sim |
| 60b2adc9f6d34c64f478 | ENA_USDT | LONG | 22 | 0.000 | Sim |
| 5583cb6a9b06d839064c | ENA_USDT | LONG | 13 | 0.000 | Sim |
| f2a2e83512dab8e162bf | ENA_USDT | SHORT | 10 | 0.000 | Sim |
| b7564dfb69f31b7e5998 | ENA_USDT | LONG | 11 | 0.000 | Não |
| 3a2869d9c347b97c58b3 | ENA_USDT | LONG | 10 | 0.000 | Não |
| fea502a2643da9e92228 | INJ_USDT | LONG | 190 | 0.792 | Não |
| 2bbdd2bca208e00cbe53 | INJ_USDT | LONG | 8 | 0.000 | Não |
| 69e7ba838770785ee257 | INJ_USDT | LONG | 8 | 0.000 | Não |
| 166b339ecc45c281c498 | ONDO_USDT | LONG | 175 | 0.596 | Não |
| a53d422b16f0556e5a94 | AAVE_USDT | LONG | 15 | 0.014 | Sim |
| 4eea637c0610f0b94466 | ONE_USDT | LONG | 37 | 0.335 | Não |
| 3fe60c8c8c234f353599 | ONE_USDT | SHORT | 10 | 0.000 | Não |

## Limites

- Contrafactuais retrospectivos independentes, não uma estratégia validada nem causas comprovadas dos movimentos.
- Todos os57sinais:33stops,18alvos,6abertas; não escolhe apenas as perdedoras para calcular o efeito dos ajustes.
- TP1R e1,5R mudam a definição de sucesso e não satisfazem o RR mínimo atual de2. Não são recuperação do TP original.
- SL estrutural usa oito candles15m fechados antes da entrada e buffer0,1ATR; volume hipotético reduzido para comparar em1R de risco.
- Recuo exige fechamento0,25da distância original ao SL melhor, em até15min, entrada seguinte dentro da faixa original; prazo final comum de4h.
- Proteção no zero líquido só ativa após fechamento conhecido em+1R, valendo a partir do minuto seguinte; não conta como TP.
- Stop primeiro em ambiguidade; MFE exclui minuto do stop por ordem intrabar desconhecida. Retomar alvo após stop não prova que bastava ampliar SL.
- Mesmo universo, custos e fills hipotéticos anteriores. Gate financeiro recalculado com referência1USDT. SomaR não é carteira.
- Hipóteses fixas para esta auditoria, sem ajustes após resultados; mesmo histórico já explorado, sem validação fora da amostra.

Nenhuma ordem foi enviada e nenhuma estratégia de produção foi modificada.
