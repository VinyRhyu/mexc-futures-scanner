# HYPE — validação de robustez do WATCH de 16–17/11 em outros períodos

Registrado em 20/11/2026 **antes de executar esta versão do replay**.
Pesquisa histórica exploratória: os períodos T,U,V,W já foram examinados
com outras estratégias. São diferentes dos dois dias usados para criar os
detectores, mas **não constituem holdout histórico intocado nem teste
prospectivo genuíno**. Não alterar scanner, main, Telegram ou executar ordens.

## Hipótese fixa

Reutilizar sem mudar os limiares:
`scripts/audit_hype_two_stage_1617.py` (TURN EMA9/21 volume 0,8;
BREAK últimos 6 M5 corpo 0,35 ATR e volume 0,8; DRIFT EMA9/21 + 30m
0,35% e volume 0,55). WATCH deduplicado por família+direção 30min
e uma união de alertas por direção 30min com prioridade TURN > BREAK > DRIFT.
Sem veto pelo H1. Confirmação posterior em até 6 M5 rompendo faixa de
6 M5, corpo 0,4 ATR e volume 1,0; entrada abertura seguinte. Stop
12 barras +/-0,1 ATR, TP bruto 1,8R, RR líquido mínimo 1,2,
máximo 24 M5; uma posição global e risco 1% saldo por entrada.
Custos 0,06% taker e 0,02% slippage por lado; funding e fills ausentes.

## Janelas temporais sem 16 e 17

Todas em UTC (America/Sao_Paulo = UTC-03 em 2026):

- T: `2026-06-05T11:00:00+00:00` a `2026-07-17T11:00:00+00:00`
- U: `2026-07-17T11:00:00+00:00` a `2026-08-28T11:00:00+00:00`
- V: `2026-08-28T11:00:00+00:00` a `2026-10-09T11:00:00+00:00`
- W0: `2026-10-09T11:00:00+00:00` a `2026-11-16T03:00:00+00:00`

W0 encerra exatamente à meia-noite antes dos dias escolhidos.
Amostras têm ~42+42+42+37,67 dias, sem sobreposição. Baixar
160 H1 de warmup e 10h M5 anteriores, além de até 2h posteriores
exclusivamente para mensuração de desfechos (nunca novas entradas).
Todos os períodos de teste precisam de dados íntegros e completos.
Um candle da barra H1 aberta não pode entrar no sinal.

## Métricas predefinidas

1. **Detecção vs taxa-base:** mesma etiqueta em qualquer M5 LONG/SHORT
   que o estudo 16/17: tocar +1,25% a favor ANTES de −0,75% contra
   até 18 M5 (90min), empate ruim. Alertas WATCH vs todos os checkpoints
   M5 e por lado. Reportar taxa-base, precisão, falso/não followthrough,
   diferença em pontos percentuais, número de avisos por dia,
   e mediana do tempo desde o WATCH até tocar a barreira favorável
   para os acertos. Sem usar etiqueta futura na decisão.
2. **Tipos de WATCH:** TURN, BREAK, DRIFT separadamente; mesma dedup
   de 30min por família/direção. Overlap entre famílias não aumenta
   evidência independente.
3. **Filtro H1 diagnóstico pré-registrado (SEM otimização):**
   estatísticas de alertas alinhados com H1 EMA20 versus contrários.
   Comparar precision/recall de alertas vencedores antes/depois de
   descartar os contrários; taxa de alertas mantidos, sem afirmar
   vantagem a partir do histórico.
4. **Confirmação/entrada:** WATCH-only, confirmação, RR/stop rejeitado,
   operações hipotéticas elegíveis e carteira global com uma por vez.
   TP/SL/TIME, ROI por bloco a 1% de risco, max drawdown e trades/dia.
   Incluir operações negativas; cada bloco reseta saldo para 100%.
5. **Comparação fixa** com pesquisa original dois dias (16/17):
   73 WATCH, 18/73 (24,66%) etiquetas favoráveis vs base 269/1152
   (23,35%); 32 elegíveis, 17 selecionadas, 1 TP/6 SL/10 TIME,
   ROI −3,204%. Esses resultados não se misturam com janelas novas.

## Critérios de triagem predefinidos

Sem otimização pós-resultado. Para indicar DETECTOR potencial:
precisão WATCH acima da taxa-base **nos quatro períodos** e alertas
no máximo 12 por dia. Para indicar candidato a ENTRADA:
ROI positivo em cada período após custos, MDD <=10% e menos de
3 trades por dia. Os critérios são hipotéticos, NÃO garantias.
Se falhar, encerrar esta hipótese e não ajustar limiares nesta amostra.
Periodização histórica e amostras de decisões em M5 são correlacionadas.
