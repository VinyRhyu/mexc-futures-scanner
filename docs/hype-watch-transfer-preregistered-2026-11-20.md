# WATCH → CONFIRM → ENTRY: transferência temporal congelada em HYPE

**Criado em 20/11/2026, antes de inspecionar resultados dos novos períodos.**
Regras de detecção e execução intactas de `scripts/audit_hype_two_stage_1617.py`,
registradas originalmente em `docs/hype-16-17-two-stage-preregistered.md`.
Pesquisa retrospectiva paper, HYPE_USDT perpétuo MEXC, horários UTC no código
e America/Sao_Paulo na interpretação; nenhum envio ao Telegram ou alteração
de produção/main. **O histórico já foi analisado por outras estratégias.**
Chamar de estudo de transferência temporal RETROSPECTIVA, não de holdout
independente nem de avaliação prospectiva.

## Datas antes de ler o replay

Conjuntos contíguos NÃO sobrepostos (início inclusivo, fim exclusivo),
no fuso America/Sao_Paulo:

- **P1:** 19/10/2026 00h00 – 26/10/2026 00h00.
- **P2:** 26/10/2026 00h00 – 02/11/2026 00h00.
- **P3:** 02/11/2026 00h00 – 09/11/2026 00h00.
- **P4:** 09/11/2026 00h00 – 16/11/2026 00h00.
- **REF:** 16/11/2026 00h00 – 18/11/2026 00h00 (somente regressão
  exata contra o teste original, NÃO incluir nos novos períodos).

Amostragem M5 e H1 públicos completos; 120 M5 e 160 H1 para aquecimento,
até 2h após o final de cada janela exclusivamente para fechamento/scoring.
Não criar watch/confirm após o fim; liquidar hipoteticamente trades
abertos dentro de 24 M5 quando todos os candles estiverem disponíveis.

## Regras IMUTÁVEIS

Reutilizar diretamente `watch_at`, `score_direction`,
`confirmation`, `execute`, `group_summary` do script original,
sem alterar os limiares, sem filtrar horários e sem H1 como veto:
- TURN: EMA9/EMA21 M5 cruzam, corpo ≥0,25 ATR14 e volume ≥0,8 mediana.
- BREAK: fechamento além da máxima/mínima 6 M5 anteriores, corpo
  ≥0,35 ATR14 e volume ≥0,8.
- DRIFT: EMAs M5 alinhadas, retorno 30min ≥0,35%, volume ≥0,55.
- 1 watch por família+direção em 30min; união deduplicada por
  direção em 30min, prioridade TURN→BREAK→DRIFT.
- Etiqueta de avaliação de WATCH (nunca critério de decisão): preço
  atinge +1,25% favorável antes de −0,75% adverso em 18 M5 (90min).
  Ambiguidade = adverso primeiro. Se não atingir = erro de detecção.
- CONFIRM até 6 M5 depois de WATCH: rompimento de fechamento além das
  6 M5 anteriores, corpo ≥0,4 ATR14, volume ≥1,0.
- Entrada papel abertura M5 seguinte, stop além dos extremos 12 M5
  anteriores ±0,1 ATR, TP 1,8R bruto, RR líquido ≥1,2, máx 24 M5,
  Taker 0,06% e slippage hipotético 0,02% por lado (0,16% roundtrip).
- 1 posição global simultânea, 1% risco por trade, TP/SL na mesma
  vela = −1R conservador, funding/fills/spread dinâmico não modelados.

## Saídas obrigatórias

Para cada janela: M5/H1 completude, taxa-base por lado de TODOS
os pontos M5, precisão de WATCH individual por família e união,
precisão de WATCH por lado, composição por lado, baseline
ponderada pela composição LONG/SHORT dos avisos, diferença em
pontos percentuais, número de alertas por dia, rótulos positivos/negativos,
*minutos entre WATCH e toque favorável* para acertadores (não inferir
antecipação de mudanças de tendência que não foram rotuladas),
quantos alertas tiveram confirmação, quantos foram elegíveis, escolhidos
pela carteira única, TP/SL/TIME, net R, ROI, DD e taxa de trades/dia.
Reportar se algum dos períodos foi fonte incompleta; não preencher com
dados simulados.

Para **REF**: exigir coincidência exata no total de 73 watches unidos,
18 acertos, 32 entradas elegíveis, 17 operações escolhidas, 1 TP,
6 SL, 10 TIME, −3,202R e −3,204% ROI, sem considerar novamente REF
como validação. Qualquer divergência impede conclusão comparativa.

## Decisão congelada

Não declarar melhora se alerta ~base de movimentos ou desempenho
financeiro não positivo. Uma única semana positiva NÃO aprova.
Critério de triagem para investigar mais: WATCH superar base ponderada
nos 4 blocos, razão de falsos positivos não piorar, tempo mediano
ao deslocamento positivo aceitável (descritivo), retorno líquido
positivo em ao menos 3 de 4 semanas e sem DD >10%.
Mesmo que passasse, NÃO seria aprovação para negociação real pois
já testamos repetidamente todo esse histórico. Não otimizar limiares
com resultados dessas 4 semanas, nem escolher apenas períodos/entradas
favoráveis.
