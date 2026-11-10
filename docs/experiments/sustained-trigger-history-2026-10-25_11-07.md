# Sustentação de dois fechamentos M1

Teste exploratório em 31 criptos, com formações de 25/10 a 07/11/2026, horário de Brasília. Foi reutilizada a coleta anterior: checksums e OHLC verificados. Os 5.226 gatilhos M1 foram reconstruídos com os mesmos resultados antes de aplicar a nova regra.

[Execução](https://github.com/VinyRhyu/mexc-futures-scanner/actions/runs/42890505005) · [Todos os resultados](https://github.com/VinyRhyu/mexc-futures-scanner/actions/runs/42890505005/artifacts/13798640548) · [Coleta original](https://github.com/VinyRhyu/mexc-futures-scanner/actions/runs/42879077420/artifacts/13792493410).

## Regra fixada antes desta execução

O primeiro candle M1 fecha além da borda por 0,10 ATR. O candle imediatamente seguinte também precisa fechar além do mesmo nível, sem exigir novo topo/fundo. TP, stop e faixa ficam congelados no primeiro gatilho. Se SL ou TP forem tocados durante a espera, ou o segundo fechamento perder o gatilho, a tentativa termina. Não se procura um substituto posterior. A entrada é simulada na abertura seguinte, respeitando os mesmos custos, faixa e RR líquido mínimo de 2.

## Resultado sem duplicatas exatas

| Regra | Entradas | Alvos | Stops | Abertas após 4h | Acerto nas encerradas | Soma R encerradas |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Primeiro fechamento M1 | 117 | 28 | 76 | 13 | 26,9% | +3,93 |
| Dois fechamentos M1 | 57 | 18 | 33 | 6 | 35,3% | +14,31 |

R é normalizado pelo risco de cada ensaio. Formações e posições podem se sobrepor; a soma não reproduz uma carteira ou saldo disponível. Abertas após 4h não são vitórias e não entram na soma encerrada.

## Comparação por semana

| Semana das formações | Primeiro M1 | Dois M1 |
| --- | ---: | ---: |
| 25–31/10 | +15,26R | +16,24R |
| 01–07/11 | -11,33R | -1,93R |

A regra melhorou o resultado nas duas semanas deste recorte, mas a segunda continuou negativa. A hipótese foi definida após examinar resultados anteriores desse mesmo histórico: não há validação fora da amostra.

## O que foi evitado e perdido

Das 117 entradas únicas anteriores, a nova regra deixou de entrar em 53 que terminavam em stop e em 12 que atingiam o alvo. Outras 23 continuaram terminando em stop. Nenhum stop antigo virou alvo e nenhum alvo antigo virou stop nos pares que continuaram com entrada.

A reavaliação financeira no preço um minuto depois também liberou 12 novas entradas antes bloqueadas: duas atingiram alvo e dez atingiram stop. Por isso, os 53 stops antigos evitados não são a diferença líquida de 43 stops entre as tabelas.

Os contadores são de ensaios; não mostram que se saberia de antemão quais operações venceriam. A redução de perdas veio com perda de oportunidades vencedoras.

## Conversão simbólica do exemplo de US$ 50

Com risco fixo de US$ 5 em cada ensaio, sem reinvestimento e somente operações encerradas: ganhos equivalentes de US$ 236,56, perdas de US$ 165,00 e diferença de +US$ 71,56. É apenas multiplicação de R; não demonstra que US$ 50 permitiriam todas as posições ou sobreviveriam à sequência. O teste foi dimensionado originalmente com referência independente de 1 USDT.

## Limites e hipóteses

- Mesmo universo, candles, contratos e configuração da coleta anterior. Checksums e OHLC validados; todos os gatilhos M1 reconstruídos idênticos antes do teste.
- Exige apenas o candle1m imediatamente seguinte ao primeiro gatilho: fechamento também além da borda por0,10ATR. Não exige novo topo/fundo e não procura substituto se falhar.
- TP, SL e faixa originais congelados no primeiro gatilho. Não recalcula pivôs com a confirmação. SL/TP tocado durante a espera cancela a nova entrada.
- Entrada na abertura seguinte à confirmação; mesmo validador financeiro e custos. Janela4h desde cada entrada; abertas separadas e stop primeiro na ambiguidade.
- Primeiro gatilho é elegível dentro dos30min da formação; confirmação pode ocorrer um minuto depois desse prazo, dentro da validade do primeiro gatilho.
- Inclui todas as formações, inclusive sem gatilho M15 ou bloqueadas no primeiro M1. Não aplica a supressão de planos ativos da produção.
- Deduplicação remove somente execuções exatamente iguais. Formações e posições podem se sobrepor; somaR não é evolução de carteira nem saldo reproduzível.
- O teste anterior usou referência de1USDT, risco até10%, teto20x, taxa0,06% por lado, spread0,02%, slippage configurado ou2ticks; funding zero e livro infinito hipotéticos.
- Regra definida após observar os resultados anteriores das mesmas duas semanas; análise exploratória, sem validação fora da amostra. Não escolher ajustes retroativamente.
- Dados/contratos congelados refletem universo elegível da coleta, não a composição histórica. Exige monitoramento por minuto; cron atual de15min não entrega esses fills.
- Diferenças pareadas indicam stops evitados e acertos perdidos; não permitem identificar antecipadamente quais trades vencerão.

A rotina e os alertas de produção não foram modificados. O próximo passo necessário para avaliar disponibilidade real de capital é uma simulação cronológica de carteira, com exposição simultânea limitada e tratamento explícito das posições ainda abertas.
