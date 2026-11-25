# Avaliar um sinal externo MEXC

A avaliação usa sinais públicos com quatro alvos publicados. No GitHub, abra
**Actions → Avaliar sinal externo MEXC → Run workflow** e informe contrato,
data e hora de publicação com fuso, direção, alavancagem e TP1 a TP4 separados
por espaço. Confira o resultado no resumo da execução. Os dados incluídos na
execução ficam visíveis aos leitores deste repositório público.

O fluxo usa a abertura do primeiro candle de 1 minuto após o sinal. O cálculo
considera degraus de cerca de 2% entre os alvos, retorno líquido até o TP1 de
pelo menos 1,6 vez o risco, stop de 35% sobre a margem e custo total estimado
de 0,20% sobre o nocional. A posição simulada encerra integralmente no TP1,
no stop ou após 24 horas. Quando stop e alvo estão no mesmo candle e a
abertura fica entre os dois, a simulação prioriza o stop.

Para rodar localmente com um sinal histórico, use:

    python -m mexc_scanner.external_signal WLFI_USDT 2026-11-24T10:05:50-03:00 LONG 30 0.04169 0.04250 0.04332 0.04414

O resultado é um relatório paper da API pública. A análise dos sinais próprios
continua no workflow **Scanner MEXC**.
