# HYPE M1 + tendência M5 — expansão temporal semanal pré-registrada

**Registrado em 20/11/2026 antes de executar estes novos blocos.**

Objetivo: verificar a hipótese percebida de que o setup M1+M5 encontrou
mais TPs que SLs em 16–17/11; distinguir 6 TPs / 4 SLs / 6 TIME
(6/10 de eventos TP-ou-SL, não 6/16 de todas operações)
de rentabilidade e de generalização.

## Protocolos congelados (SEM alterações)

Usar exatamente o código existente
`scripts/audit_hype_m1_trend.py`, com `ARM` original, WATCH
M5 original (TURN/BREAK/DRIFT), condições e threshold M1/M5/H1,
SL nas últimas 15 M1 com buffer ATR, TP=1,8R bruto,
RR líquido mínimo=1,2, 120 M1 de tempo máximo, stop prioritário
se TP/SL mesmo M1, uma posição por vez, risco fictício 1% da conta,
custos 0,06% taker + 0,02% slippage por lado = 0,16% ida+volta,
sem funding, spreads reais, profundidade de book ou liquidação.

A **única modificação permitida** antes do teste é adicionar
nomes/datas às janelas do mapa PERIODS; a função `simulate`,
`candidate_minute`, `execute_m1`, contextos e detecção WATCH
não podem ser modificados. Os testes executam os quatro braços
(M5 original, M1_FAST, M1_M5_TREND, M1_H1_TREND)
sem alterar entradas, parâmetros ou seletividade.

Quatro pares **fixos antes de ler resultados M1**, segunda–terça
de 00h00 BRT de segunda até 00h00 BRT de quarta, limite de
sinal estrito no fim, MEXC HYPE_USDT M1/M5/H1 íntegros:

- **OCT05:** 05/10/2026 00h → 07/10/2026 00h;
- **OCT12:** 12/10/2026 00h → 14/10/2026 00h;
- **OCT19:** 19/10/2026 00h → 21/10/2026 00h;
- **OCT26:** 26/10/2026 00h → 28/10/2026 00h.

Além dos novos períodos, manter como **referência separada**:
CMP2 02–03/11; CMP 09–10/11; REF 16–17/11.
Todos os blocos são disjuntos. O ano é 2026.

Cada período carrega 90 minutos M1, 10h M5 e 160h H1 para
warmup e até 2h posteriores APENAS para saída. Recusar
candles incompletos/gaps/órfãos. Nenhuma ordem real ou alteração
na main, produção, Telegram ou scanner.

## Comparações e critérios antes da observação

Reportar por dia/bloco/braço: WATCHs, quantidade elegível/selecionada,
TP/SL/TIME, ROI líquido composto (1% risco), drawdown, latência
WATCH→confirmação e frequência. Agregar as quatro novas janelas
pelo produto dos respectivos (1+ROI/100) e somar contagens;
não apresentar acerto 6/(6+4) sem também informar 6/16 com TIME.
Janelas já investigadas em pesquisas anteriores; por isso
**NÃO** alegar que são holdout intocado ou prova fora da amostra.

Regra principal de triagem: estratégia M1+M5 só pode ser candidata
para novo teste prospectivo se ROI for positivo em **pelo menos
3/4 novas janelas**, soma das quatro ROIs encadeados positiva,
máximo drawdown <=10%, frequência <=3 operações/dia; e não
inferir robustez porque um único período foi excelente.
Critério é exploratório e não autoriza uso real.

Não modificar os parâmetros ao encontrar resultados negativos.
Não adaptar filtros a dias selecionados no gráfico.


## Adendo de indisponibilidade M1 e janelas de fallback (antes dos resultados)

O primeiro replay do plano original falhou no acesso ao histórico Min1
de **05/10/2026**: API MEXC respondeu 0 candles para 3.090 esperados,
interrompendo o job antes de qualquer cálculo de ROI dos blocos propostos.
Log do primeiro teste: https://github.com/VinyRhyu/mexc-futures-scanner/actions/runs/44842291237.
Não supor retenção exata da API, nem substituir por candles fabricados.

Como substituição por DISPONIBILIDADE DE DADOS — não por desfechos
das operações — registrar os quatro períodos abaixo ANTES de ler
seus resultados M1:

- **OCT26:** 26/10/2026 00h → 28/10/2026 00h BRT;
- **NOV04:** 04/11/2026 00h → 06/11/2026 00h BRT;
- **NOV06:** 06/11/2026 00h → 08/11/2026 00h BRT;
- **NOV12:** 12/11/2026 00h → 14/11/2026 00h BRT.

Não se sobrepõem aos blocos de comparação já conhecidos CMP2
(02–03/11), CMP (09–10/11) e REF (16–17/11), embora todos
sejam histórico previamente observado por outros métodos.
Se faltar M1 em OCT26, reportar como indisponível em vez de
escolher arbitrariamente mais um período para "completar 4".
Os demais períodos serão processados independentemente para
não perder seus resultados se uma janela estiver indisponível.
Para triagem robusta, exigir QUATRO disponíveis; caso contrário
considerar inconclusivo, sem selecionar a janela vencedora.

A restrição "somente segundas e terças" do desenho original
foi abandonada por indisponibilidade de dados; isso reduz
a comparabilidade por dia da semana e deve constar no relatório.
Mantêm-se todos os thresholds e a lógica M1 originais.
