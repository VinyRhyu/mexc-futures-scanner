# HYPE: oito movimentos escolhidos pelo usuário — diagnóstico histórico pré-registrado

Data: 20/11/2026. **Não é teste fora da amostra.** Os horários/ativos foram
escolhidos pelo usuário após observar os movimentos. Não transformar esses
intervalos em operações supostamente previstas, nem ajustar parâmetros
para encontrar ganhos.

Fonte: HYPE_USDT perpétuo MEXC, dados H1 e M5 contínuos, somente candles
fechados. Todas as horas exibidas em America/Sao_Paulo (UTC-03).

Janelas fixadas antes da análise:
1. 16/11 08:00–10:00, SHORT
2. 16/11 10:00–12:15, LONG ("logo após" o short; fim inferido a partir do início do próximo)
3. 16/11 12:15–19:00, LONG
4. 17/11 02:30–06:15, SHORT
5. 17/11 11:15–12:30, SHORT
6. 18/11 10:15–13:00, SHORT
7. 19/11 00:00–08:30, LONG
8. 20/11 08:00–12:30, SHORT.

Para cada intervalo calcular preço de abertura M5 no começo, close M5 no fim,
movimento percentual dirigido, máximo/mínimo M5 e horário de seus candles,
medidas de oscilação antes do fechamento. NÃO usar extremos para definir
entrada, TP ou SL retrospectivamente.

Para checkpoints t-15min, t e t+15min, t+30min, t+60min, usar SOMENTE M5 que
fecharam até t e H1 cujo candle fechou até t. Medir:
- direção e distância do fechamento H1 para EMA20 e EMA50;
- tendência EMA20 H1 crescente/decrescente entre dois fechamentos H1;
- retorno M5 nos últimos 60min, ATR14 M5 relativo ao preço;
- volume da última M5 versus mediana das 12 anteriores;
- rompimento confirmado do máximo/mínimo dos 12 M5 anteriores;
- corpo na direção do intervalo dividido pelo ATR.

Como explicação objetiva de possíveis gatilhos precoces (NÃO implementação
de estratégia aprovada), identificar a PRIMEIRA vela M5 entre o começo do
intervalo e os 60 primeiros minutos (ou até o encerramento) que:
(1) feche fora do canal das 12 velas M5 anteriores na direção indicada;
(2) tenha corpo nessa direção >=0,5 ATR14 pré-vela;
(3) tenha volume cotado >=1,2 mediana das 12 anteriores; (4) candle completo.
NÃO exigir viés H1 como filtro; relatar se estava alinhado à EMA20 no momento.
A abertura seguinte representa apenas um preço de entrada hipotética; não
afirmar execução. Stop diagnóstico: máximo (SHORT) ou mínimo (LONG) das 12
velas pré-gatilho +/− 0,1 ATR; alvo 1,8R bruto, RR líquido >=1,2 com custo
0,06% taker +0,02% slippage por lado; saída até 24 M5 (2h), SL prioritário
se tocar TP+SL no mesmo candle. Análise exploratória de setup com eventos
ESCOLHIDOS, logo não é rentabilidade esperada.

Em paralelo, rodar a MESMA regra sobre todos os candles da semana, relatar
quantidade de gatilhos direcionais (sem escolher eventos) e a quantidade
dentro/fora dos oito intervalos; não inferir ganho de selecionar apenas
os que o usuário viu. Reproduzir F congelada para lembrar que seu LONG
não existe.

Nenhuma modificação na estratégia principal, no scanner de produção, na
mensageria Telegram nem em ordens.
