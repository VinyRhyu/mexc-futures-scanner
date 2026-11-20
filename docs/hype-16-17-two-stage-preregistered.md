# HYPE 16–17 de novembro — detecção separada de entrada (pré-registro)

**Pesquisa exploratória retrospectiva, não testável fora da amostra**: os dias e as cinco janelas foram escolhidos após observar preços. Registrar antes de acessar o replay.
Nenhuma ordem real, Telegram, main ou scanner em produção será alterado.

## Escopo

Somente HYPE_USDT MEXC Futures. Janela de alerta 16/11/2026 00:00 até 18/11/2026 00:00, horário de São Paulo (-03). Carregar 80h H1 e 10h M5 de warmup e *até 18/11 02h* apenas para observar saídas de posições e janelas de avaliação abertas até 17/11 23h55; não gerar novos sinais após 17/11 23h55.
Candles públicos M5/H1 contínuos e fechados, entrada próxima abertura M5. Custos Taker 0,06% + slippage 0,02% por lado. Funding e fills reais não modelados.

## 1. Detecção — avisos NÃO executáveis

Três avisos independentes; todos usam exclusivamente M5 fechado e indicadores calculados sem futuro:

- **TURN**: cruzamento EMA9/EMA21 M5 (EMA9 passa acima para LONG ou abaixo para SHORT), corpo da vela na direção >=0,25 ATR14 pré-vela, volume cotado relativo às 12 anteriores >=0,8.
- **BREAK**: fechamento M5 fora dos extremos de **6 M5 anteriores** na direção da vela; corpo na direção >=0,35 ATR14 pré-vela e volume relativo >=0,8.
- **DRIFT**: EMA9 alinhada acima de EMA21 e EMA9 crescente em quatro barras para LONG (inverso SHORT), preço fecha no lado da EMA9 da direção, e retorno em seis M5 >=0,35% na direção, volume >=0,55.
- Emitir NO MÁXIMO 1 alerta por família/direção a cada 30 minutos, sem conhecer desfecho futuro. Os alertas TURN/BREAK/DRIFT podem coincidir. Também reportar a união dos alertas sem repetir a mesma direção em 30 minutos, prioridade TURN > BREAK > DRIFT. Nenhum bloqueio H1: reportar apenas sua direção H1 EMA20 no aviso.

## 2. Avaliação objetiva da detecção sem posição

Um alerta é **acerto de direção de 90min** se, após seu fechamento M5, preço alcança deslocamento favorável >=+1,25% do preço de referência ANTES de excursionar >=-0,75% contra, dentro das próximas 18 M5 fechadas. SL adverso tem prioridade quando ambas as barreiras ocorrem no mesmo candle; se ambos ausentes, não é acerto. Esses limites definem uma *etiqueta futura só de avaliação*, não um TP/SL de execução.
Calcular taxa-base com TODOS os checkpoints M5 de ambos os dias em ambas as direções sob mesma etiqueta, não apenas alertas. Contabilizar falsos alertas, acertos, horário e quantidade.
Os eventos "observados pelo usuário" são 5 janelas de 16–17/11 e servem só à auditoria de latência (primeiro aviso após início), não a selecionar sinais operáveis nem a calcular precisão geral.

## 3. Entrada, validada em etapa independente

Para cada alerta de união, esperar CONFIRMAÇÃO após a vela de aviso (não usar o próprio candle como confirmação), no máximo seis candles M5 seguintes:
- LONG: candle fechado acima da máxima dos **6 anteriores** e corpo direcional >=0,40 ATR14 anterior; SHORT: simétrico abaixo mínima 6 anteriores;
- volume relativo >=1,0 contra as 12 M5 anteriores;
- entrar na abertura M5 seguinte à confirmação, se ainda dentro da janela (pode haver encerramento até 18/11 02h para validar a última operação);
- stop além da mínima/máxima das 12 M5 anteriores à confirmação, com 0,10 ATR14; TP fixo 1,8R bruto;
- rejeitar caso risco não positivo ou RR líquido <1,2;
- máxima duração 24 candles M5 (2 horas) desde o sinal de confirmação.
- A mesma direção e família podem gerar alertas em sequência; para FINANÇAS usar apenas uma posição global, selecionar cronologicamente os trades elegíveis, não somar sinais simultâneos.
- Em um candle que toca TP e SL, avaliar conservadoramente SL (−1R); em timeout, saída no fechamento do 24º M5.
- Risco hipotético 1% do saldo por trade. Reportar ROI, DD, TP/SL/TIME, gate RR e WATCH_ONLY sem tratar isso como validação de lucro.

## 4. Transparência

Reportar totais por família e direção, união deduplicada, taxa-base M5, número de confirmações, operações elegíveis, operação selecionada pela carteira global, resultados por dia e os primeiros casos cronológicos.
A existência de movimentos de 2–6% não garante entrada a tempo; não usar extremos futuros para definir preço de entrada.
Dois dias escolhidos retrospectivamente NÃO permitem aprovação de um modelo; se positivo, será hipótese para avaliar prospectivamente, sem ajuste retrospectivo de limiares.
