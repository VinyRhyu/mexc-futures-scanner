# HYPE — teste pareado M1 versus M5 com stop e alvo ANCORADOS no mesmo WATCH

**Pré-registro em 20/11/2026, antes de executar este novo replay.**
Pesquisa histórica exploratória; todos os períodos já examinados por outras
pesquisas. Não se trata de holdout prospectivo. Nada em main/produção,
Telegram ou ordens reais será modificado.

## Pergunta e unidades de comparação

O benefício observado nos dois dias 16–17 foi causado pelo gatilho M1
mais rápido, ou pelo stop/TP diferentes? Para reduzir essa confusão,
reutilizar os mesmos WATCHs M5 deduplicados de
`scripts/audit_hype_m1_trend.py` nos mesmos SETE pares de 48h fixados
(REF 16–17/11, CMP 09–10/11, CMP2 02–03/11, OCT26 26–27/10,
NOV04 04–05/11, NOV06 06–07/11 e NOV12 12–13/11).

A cada WATCH M5 fechado, **fixar uma única intenção**: direção LONG/SHORT,
stop e TP imutáveis até o fim das possíveis confirmações, utilizando
somente M5 já fechadas no instante WATCH:
- ATR14 calculado antes da M5 que originou WATCH;
- stop LONG = menor low entre as últimas 12 M5 encerradas INCLUINDO
  a vela WATCH menos 0,1 ATR14; stop SHORT = maior high desse grupo
  +0,1 ATR14;
- preço de referência = close do candle WATCH;
- distância de referência = distância positiva entre close e stop;
- **TP fixo** = referência +1,8 distância (LONG) ou −1,8 distância (SHORT).
  Esse TP é fixo para todos os braços daquele mesmo WATCH, até se
  as entradas ocorrerem em preços distintos. É alvo de comparação
  e não igual a 1,8R de cada nova entrada.

## Braços experimentais: mesmo alerta, stop, TP e OHLC para saídas

- `M5_FIXED`: primeira confirmação M5 **original** em até seis
  velas M5 seguintes (max 30min), função
  `audit_hype_two_stage_1617.confirmation` intacta;
  ignorar stop calculado nessa confirmação, pois usar o stop
  original congelado no WATCH.
- `M1_FIXED`: primeira confirmação M1 após WATCH em até 30min com
  rompimento M1 (5 M1 anteriores), corpo >=0,35 ATR14 M1,
  volume >=1x mediana 10 M1 anteriores, EMA9 M1 alinhada e
  EMA9 crescente/decrescente 3 M1; exigir M5 fechado com
  EMA9 versus EMA21 alinhado e crescente/decrescente versus
  2 velas M5 anteriores; utilizar diretamente a regra
  `first_confirmation_m1(..., "M1_M5_TREND", ...)` congelada.
- `M1_FAST_FIXED`: como sensibilidade pré-registrada, mesma
  detecção M1 porém **sem** filtro de alinhamento da M5,
  exatamente a regra `M1_FAST` original. Nenhum ajuste
  de thresholds depois de analisar os resultados.

Cada confirmação, em qualquer braço, deve acontecer após o WATCH
e ANTES do fim da janela. Entrada hipotética na abertura M1
imediatamente seguinte ao candle confirmador (a M5 também fecha
em um instante múltiplo de minuto). Avaliar TP/SL/timeout para TODOS
os braços utilizando os MESMOS candles públicos de M1,
a partir da abertura executável por até 120 M1 (2h).
TP e SL simultaneamente no mesmo M1 contam como perda.
Timeout: close da última M1 dos 120min.
Se, ao abrir, o preço já estiver no TP ou do lado contrário ao SL,
recusar, nunca presumir fill garantido. Risco financeiro baseado na
DISTÂNCIA entre entrada efetiva e o stop fixo, não no close WATCH.

Custos taker=0,06%/lado + slippage assumido 0,02%/lado,
0,16% total notional; RR líquido ex ante calculado com TP e SL
fixos e preço de cada braço, exigindo >=1,2. Se não, bloquear
sem olhar o desfecho. Risco hipotético de 1% do saldo/trade,
posição única por braço e carteira com saída exatamente
após a M1 do evento (não a folga conservadora de 5min
que o seletor de carteira M5 introduzia).

## Testes e saídas antes de ler os resultados

- Exigir M1/M5 de datas exatamente iguais aos períodos, M1
  paginado sem lacunas, contexto M5 somente de candle fechado.
- Para cada WATCH, atribuir ID (watch timestamp, lado, família)
  e stop+TP fixos sem futuro. Registrar WATCHs sem confirmações,
  risco bloqueado e elegíveis.
- Avaliar **TODOS** os WATCHs, não somente episódios de sucesso.
- Para cada janela e braço: elegíveis, selecionados, TP/SL/TIME,
  net R, ROI composto, MDD, trades/dia, mediana de latência
  WATCH→confirmação e sinais perdidos.
- Diagnóstico PAREADO entre WATCHs que possuem entradas
  elegíveis NOS DOIS braços: tempo do gatilho e retorno de cada
  operação isolada, sem fingir que são a carteira realizável;
  usar para distinguir latência de seleção/frequência.
- Fazer teste de causalidade unitário: alterações em candles M1
  futuros ou M5 futuros não mudam os sinais existentes;
  alterar preço de entrada não pode mudar o stop nem TP do WATCH.
- Diferenças entre braços ainda incluem o critério do gatilho
  (EMA9 M1 vs rompimento M5), mas **não diferem mais pelo
  stop/TP ou pela resolução da vela de saída**.
- Critério prévio: `M1_FIXED` deve ter ROI líquido maior
  que `M5_FIXED` em >=5 de 7 pares, retorno composto positivo
  e não aumentar DD acima 10% nem superar 3 operações/dia para
  merecer estudo prospectivo futuro. Como o histórico já foi
  examinado, qualquer lucro permanece exploratório.
- Não ajustar regras à luz de perdas e não implantar em produção.
