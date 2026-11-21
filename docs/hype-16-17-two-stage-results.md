# HYPE 16 e 17/11/2026 — estudo duas etapas: aviso e entrada

**Pesquisa histórica, somente no contrato futuro HYPE_USDT da MEXC.**
**Regras registradas antes da coleta:** `docs/hype-16-17-two-stage-preregistered.md`
**Código:** `scripts/audit_hype_two_stage_1617.py`
**Execução validada:** https://github.com/VinyRhyu/mexc-futures-scanner/actions/runs/44836748136

Análise de **16/11 00:00 a 17/11 23:55**, fuso São Paulo UTC−03.
Foram baixadas 720 M5 e 210 H1 **incluindo 10h de aquecimento M5,
160h de aquecimento H1 e 2h adicionais somente para avaliação futura
e encerramento de sinais do dia 17**; 576 pontos M5 compõem os
dois dias examinados. Verificação de sequência contínua sem lacunas.
Sem Telegram, produção, automações e ordens reais.

## Como funciona o estudo

**Etapa A — WATCH:** três detectores:
- TURN: cruzamento EMA9/21 com corpo >=0,25 ATR e volume relativo >=0,8;
- BREAK: fechamento fora do range das 6 M5 anteriores, corpo >=0,35 ATR,
  volume relativo >=0,8;
- DRIFT: EMA9 > EMA21 crescente e retorno 30min >=0,35% no LONG,
  simétrico SHORT; volume relativo >=0,55.
Limite de um aviso por família/direção a cada 30 minutos, e união de
avisos com limite por direção de 30 minutos, prioridade TURN/BREAK/DRIFT.

**Teste objetivo de WATCH (não é operação):** em até 90min depois do
aviso, preço deve atingir +1,25% a favor ANTES de atingir −0,75% contra.
Se ambas as barreiras são tocadas no mesmo M5, conta como contra.
A mesma etiqueta é calculada para *todos* os checkpoints M5 e as
duas direções como taxa-base, sem selecionar extremos futuros
na lógica do WATCH.

**Etapa B — entrada:** confirmação em um dos 6 próximos M5 fechados
(rompimento dos seis anteriores na direção, corpo >=0,4 ATR, volume
>=1,0); entrada na próxima abertura; stop além do extremo das 12 M5
anteriores ±0,1 ATR; TP 1,8R bruto e RR líquido ex ante >=1,2.
Saída por TP, SL ou 24 candles de 5min (duas horas). Risco hipotético
1% de conta por operação. Custos simulados: 0,06% Taker +0,02%
slippage por lado, total nominal de 0,16% ida e volta.
Funding, spread dinâmico, liquidez de livro, fills e liquidação
não considerados.

## Qualidade da detecção — tudo que ocorreu nos dois dias

| Etapa | Alertas/pontos | Com +1,25% antes de −0,75% | Sem sequência favorável | Taxa |
|---|---:|---:|---:|---:|
| Todos checkpoints M5 em LONG e SHORT (taxa-base) | 1152 | 269 | 883 | **23,35%** |
| WATCH combinado 30min por direção | 73 | 18 | 55 | **24,66%** |
| WATCH de 16/11 | 36 | 10 | 26 | 27,78% |
| WATCH de 17/11 | 37 | 8 | 29 | 21,62% |

Diferença do combinado versus taxa-base: **+1,31 ponto percentual**;
não é evidência robusta de que esses três avisos tenham vantagem
preditiva. Observações correlacionadas no mesmo ativo/dia.

Os avisos por família (contados individualmente, antes da união
de alertas) foram:
TURN 10, com 4 acertos (40%); BREAK 56, com 16 (28,57%);
DRIFT 58, com 14 (24,14%). Alguns avisos coincidem; **não somar
essas quantidades como se fossem alertas independentes**.
A aparente vantagem de TURN é amostra mínima de dez avisos.

## Funil de entradas hipotéticas

- 73 WATCH únicos;
- 41 ficaram apenas em acompanhamento, sem confirmação válida;
- 32 tiveram confirmação e passaram pelo teste RR/stop;
- desses, **17** foram selecionados pela carteira global de
  somente uma posição aberta por vez;
- 1 TP, 6 SL, 10 saídas por tempo;
- **−3,202R**, ROI composto simulado **−3,204%** e
  drawdown máximo **4,387%**.

16/11: 36 avisos, 14 entradas elegíveis e 8 selecionadas.
17/11: 37 avisos, 18 elegíveis e 9 selecionadas.

## Cinco episódios marcados pelo usuário

| Evento histórico | Primeiro WATCH | Primeiro sinal com RR elegível | Operação efetiva da carteira global |
|---|---|---|---|
| 16/11 SHORT 08:00–10:00 | 08:40 | 08:45 | SHORT 09:15, TIME −0,38543R |
| 16/11 LONG 10:00–12:15 | 10:35 | 11:20 | LONG 11:20, TIME −0,15659R |
| 16/11 LONG lento 12:15–19:00 | 12:45 | 16:55 | LONG 16:55, TP +1,55518R |
| 17/11 SHORT 02:30–06:15 | 03:35 | 03:40 | SHORT 03:40, TIME +0,32558R |
| 17/11 SHORT 11:15–12:30 | 12:10 | nenhuma até 12:30 | não houve SHORT autorizado nesse trecho |

**Por que SHORT 16/11 08:45 não integra a carteira?** Havia LONG
aberto às 07:30 que atingiu o stop num candle iniciado às 08:45.
A seleção global não permite abrir posição simultânea; o SHORT
de 08:45 teria resultado em TIME +0,60736R se operado isoladamente,
mas não pode ser contado como lucro de carteira. A primeira posição
SHORT realmente selecionada no episódio foi a de 09:15, TIME
−0,38543R. É fundamental não confundir um alerta oportuno com
um trade que a carteira poderia executar.

Exemplos de operações selecionadas, preços USDT:

| Dia, entrada | Direção | Entrada | SL | TP | Resultado |
|---|---|---:|---:|---:|---|
| 16/11 09:15 | SHORT | 65,284 | 67,710357 | 60,916557 | TIME −0,38543R |
| 16/11 11:20 | LONG | 66,551 | 64,796043 | 69,709923 | TIME −0,15659R |
| 16/11 16:55 | LONG | 67,986 | 66,850671 | 70,029591 | TP +1,55518R |
| 17/11 03:40 | SHORT | 69,425 | 70,493121 | 67,502381 | TIME +0,32558R |
| 17/11 11:20 | LONG | 70,005 | 69,188079 | 71,475459 | SL −1R |
| 17/11 12:50 | SHORT | 67,513 | 69,804579 | 63,388159 | TIME −0,54802R |

Os resultados acima podem ser conferidos nos eventos
`HYPE_1617_TRADE` da execução GitHub Actions.

## Diagnóstico e próximo passo lógico

A separação de fases **melhorou a capacidade de acompanhar** algumas
viradas antes das entradas finais, mas não produziu edge estatística
no detector (24,66% contra 23,35% base), nem lucro na carteira
(−3,204%). Os avisos são frequentes: 73/48h = 1,52/h,
32 confirmações e 17 posições em dois dias.

O caso LONG gradual 16/11 12:15 mostra boa distinção:
WATCH 12:45, mas entrada somente 16:55 depois de confirmação;
não tratar 12:45 como preço executável.

**Não ajustar limiares com base nesses mesmos dois dias.**
Próxima hipótese deve ser testada com períodos cronologicamente
novos e medir redução de falsos positivos, tempo de alerta,
confirmações oportunas, execução e sensibilidade a custo sem
perder a distinção entre WATCH e ENTRY.

O trabalho ficou exclusivamente na branch
`experiments/confluence-tao-20261120`, PR #2 aberta, sem merge.
