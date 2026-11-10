# Gatilho antecipado: comparação histórica M1 × M15

Formações de 25/10 a 07/11/2026, horário de Brasília. Históricos completos e consistentes de 31/31 criptos; nenhum erro de coleta. [Execução](https://github.com/VinyRhyu/mexc-futures-scanner/actions/runs/42879077420) · [Coleta e resultados completos](https://github.com/VinyRhyu/mexc-futures-scanner/actions/runs/42879077420/artifacts/13792493410) (artefato com retenção de 30 dias).

O primeiro fechamento de 1 minuto além da borda por 0,10 ATR é comparado ao primeiro fechamento de 15 minutos além da mesma borda. Entrada simulada na abertura do minuto seguinte. São conservadas a formação da consolidação, o stop, a função que seleciona o TP e os filtros financeiros de produção, incluindo RR líquido mínimo de 2. O TP pode mudar de valor porque a mesma função considera a referência de preço de cada gatilho; a lógica dos pivôs não foi modificada.

## Resultado sem duplicatas exatas

| Gatilho | Entradas | Alvos | Stops | Abertas após 4h | Soma R encerradas |
| --- | ---: | ---: | ---: | ---: | ---: |
| Fechamento M15 | 46 | 9 | 33 | 4 | -11,22 |
| Fechamento M1 | 117 | 28 | 76 | 13 | +3,93 |

R normaliza o resultado pelo risco de cada ensaio, com custos hipotéticos. A soma não representa evolução de saldo: formações e posições podem se sobrepor. Abertas após 4h não são vitórias e não entram na soma encerrada. A taxa de alvos nas encerradas foi 21,4% no M15 e 26,9% no M1; isso não é estimativa prospectiva de acerto.

## Variação entre semanas

| Semana das formações | Entradas M15 | R M15 | Entradas M1 | R M1 |
| --- | ---: | ---: | ---: | ---: |
| 25–31/10 | 28 | +0,28 | 71 | +15,26 |
| 01–07/11 | 18 | -11,50 | 46 | -11,33 |

O ganho agregado concentra-se na primeira semana. A segunda continuou negativa. Os dados não sustentam promover a regra ao scanner de produção.

## Comportamento

- Foram registradas 23.174 formações LONG/SHORT, inclusive as que nunca geraram gatilho em 15 minutos.
- Entre as 3.405 formações com gatilho nos dois métodos, 3.200 dispararam antes no M1; a antecipação mediana foi de 10 minutos.
- 2.210 de 5.226 gatilhos M1 (42,3%) não mantiveram a condição de rompimento no fechamento do candle de 15 minutos correspondente.
- Entre as entradas únicas M1, esse grupo teve 49 entradas: 8 alvos, 37 stops e 4 abertas. Essa classificação só é conhecida depois da entrada; não pode ser usada retroativamente como filtro para escolher vencedores.
- A maioria dos gatilhos continua bloqueada: 4.902 gatilhos M1 falharam no retorno/risco líquido.
- Os 119 ensaios M1 viáveis incluem duas duplicatas exatas de execuções com stop; removê-las produz as 117 entradas da tabela.

## Limites

- Gatilho fixo: primeiro fechamento além da borda da consolidação por 0,10 ATR; M1 versus M15, entrada na abertura do minuto seguinte.
- Mesmas formações causais de oito candles anteriores, largura1–4ATR, dois toques por borda; ATR14 e SL da produção. LONG/SHORT espelhados.
- Inclui todas as formações a cada15m, mesmo sem gatilho posterior. Não aplica supressão de planos ativos do daemon: comparação controlada de gatilhos, não replay exato da carteira/produção.
- Formações podem se sobrepor ou gerar execuções iguais; unique_entries identifica duplicatas exatas. SomaR é de ensaios independentes, não retorno de uma carteira.
- Cada formação tem30min para disparar, inclusive após a data final; primeira tentativa somente. Bloqueio não permite escolher outra entrada depois.
- Usa make_variant e evaluate atuais: mesma seleção/projeção de TP e mesmo SL, RR líquido>=2, saldo1USDT, risco até10%, teto20x e lote.
- O valor do TP pode diferir porque a mesma regra seleciona pivôs à frente da referência de cada gatilho. Não foi alterada a lógica dos pivôs.
- Pivôs apenas de candles1h/2h já fechados naquele minuto. Os níveis são congelados antes de consultar desfechos futuros.
- Janela4h por entrada; SL primeiro na ambiguidade e gaps adversos. Candle de gatilho não conta como lucro após entrada.
- trajectory_blocked descreve SL/TP no preço mesmo quando não há liberação financeira; não representa operação executável nem taxa de acerto do bot.
- Funding zero e livro infinito hipotéticos; taxa0,06% por lado, spread0,02%, slippage configurado ou dois ticks. Taxas pessoais não verificadas.
- Universo/liquidez e regras atuais de contratos, não sua composição histórica. Mesmos dados para os dois métodos, OHLC1m/15m verificado.
- 25–31/10 é período ainda não analisado por este experimento; 01–07/11 já foi explorado em outras hipóteses. Não é validação prospectiva.
- Execução M1 exige monitoramento por minuto; o agendamento atual de15m não entrega esse preenchimento. Latência real não foi medida.

O conjunto das formações é comum aos dois gatilhos e inclui todas as consolidações elegíveis a cada 15 minutos. Não aplica a supressão de planos ativos do daemon, portanto esta tabela é uma comparação controlada do gatilho e não uma reprodução exata do scanner em produção. A rotina do Telegram e a estratégia de produção não foram alteradas.

A coleta salva candles M1, M15 e H1, regras atuais de cada contrato e hashes por arquivo em raw/. all-formations.json.gz contém todos os casos, incluindo bloqueados; summary.json contém o resumo e entradas viáveis.
