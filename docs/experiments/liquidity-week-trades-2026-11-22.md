# Livro de operações — última semana completa, 15–22/11/2026

## Escopo exato e dados congelados

- **Período de sinais:** 15/11/2026 17:00 até 22/11/2026 17:00 (horário de Brasília), equivalente a 15/11 20:00 até 22/11 20:00 UTC, final exclusivo.
- **Observação do resultado:** até quatro horas após cada sinal; disponibilidade completa até 22/11 21:00 BRT. Esta janela foi escolhida antes da coleta semanal, respeitando a disponibilidade atual de candles fechados.
- **12 ativos, mesmo conjunto do experimento anterior:** baixa liquidez ORCA, S, NEO, FLOKI, TRB e SAND; maior liquidez ONDO, ARB, TIA, DOT, AVAX e UNI. Seleção de símbolos já conhecida e sujeita a viés de sobrevivência e conhecimento do caso ORCA.
- **Mesmas regras técnicas:** M15 consolidação, ruptura M1, confirmação no M1 seguinte com retenção >=50% de volume, stop e alvo fixados e com avaliação financeira do projeto.
- **Sem execução de ordens ou Telegram.** Entrada na abertura M1 seguinte simulada com spread, slippage e taxas pressupostos; TP/SL observados com OHLC (stop primeiro em candle ambíguo), prazo máximo de 4h, ausência de histórico de livro e funding real.
- **Um único slot de posição:** operações viáveis ordenadas por instante do sinal e desempate estável por símbolo/ID. Entrada só se slot estiver desocupado. Este método não representa um algoritmo de otimização de carteira e não mostra lucro de conta.
- **Planilhas exportadas:** `portfolio_selecionadas.csv` para a carteira sequencial, `todas_viaveis.csv` para todas as entradas independentes. Incluem preço estimado de entrada, stop, alvo, preço estimado de saída, horário BRT, motivo e resultado líquido R/USDT simulados.
- **Distinção importante:** OHLC e níveis TP/SL são públicos/teóricos; o preço estimado de execução não representa fill observado. R de operações usa preço e custo sintéticos e não pode ser interpretado como retorno realizado ou taxa de acerto garantida.
- A execução só é considerada concluída se os candles M1/M15 forem consistentes, sem lacunas, e houver 4h após o último sinal.

Usar os dois artefatos para conferir que nenhuma operação independente foi duplicada ou confundida com uma seleção de carteira. Não alterar as regras da `main` em função deste único intervalo temporal.
