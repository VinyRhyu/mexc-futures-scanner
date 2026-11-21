# Hipótese congelada: rompimento de compressão com momentum (BCM-1), LONG e SHORT

Registro anterior a qualquer execução da estratégia: **20/11/2026**.
Somente pesquisa/paper; sem ordens, Telegram, alteração de main ou otimização retrospectiva.

## Motivação
Estratégias de reversão F (falso rompimento de resistência) e SMC-R
(varredura de liquidez + FVG baixista) tiveram resultados líquidos negativos
em períodos longos. Testar uma **família diferente**, que acompanha
um rompimento de faixa comprimida com volume, sem exigir reteste tardio.

## Regra BCM-1 fixa
Sempre considerar SOMENTE candles M5 e H1 fechados no instante da decisão.
M5 armazena [open_timestamp_ms, open, high, low, close, volume, quote_volume].
**H1**: o último H1 fechado deve terminar com close acima de EMA20 para LONG
ou abaixo de EMA20 para SHORT. EMA20 iniciada pela média dos 20 primeiros
candles H1 fechados; nenhuma barra H1 aberta participa.

**Consolidação ANTERIOR ao candle gatilho**:
- Janela dos 12 M5 imediatamente anteriores (60 min), sem o atual.
- Amplitude (max(high)-min(low)) <= **4,0 × ATR14 M5** anterior ao gatilho.
- Média do true range dos 12 M5 anteriores <= **0,85 ×** média do
  true range dos 36 M5 imediatamente anteriores a essa janela.
- ATR14 calculado estritamente antes do gatilho, usando os 14 candles
  M5 anteriores e seus respectivos closes precedentes.

**Rompimento de continuidade**:
- LONG: o M5 gatilho fecha acima da máxima da caixa de 12 candles por
  >= 0,10 ATR14, candle verde, close acima EMA20 H1 (já aferido H1).
- SHORT: fecha abaixo da mínima da caixa por >= 0,10 ATR14,
  candle vermelho, close H1 abaixo EMA20 H1.
- Corpo do gatilho / (high-low) >= **0,60**.
- True range do gatilho entre **1,0 e 3,0 × ATR14 M5**.
- Volume financeiro (amount) do M5 gatilho >= **1,5×** mediana
  dos 12 M5 imediatamente anteriores.
- Acontece **no fechamento do gatilho M5**; entrada simulada no
  **open M5 seguinte**. Não aceitar entradas intrabar não confirmadas.

**Stops e alvos fixos ao entrar**:
- LONG stop = low(gatilho) − 0,10 ATR14, TP = entrada + 1,8× distância até stop.
- SHORT stop = high(gatilho) + 0,10 ATR14, TP = entrada − 1,8× distância.
- Exigir RR líquido >= 1,2 após taxa taker 0,06% por lado + slippage
  hipotético 0,02% por lado. Rejeitar stop inválido ou TP <= 0.
- Timeout **24 M5 (120 min)** contados da primeira barra pós-gatilho,
  liquidando a posição na última close simulada, com custos.
- Caso SL e TP toquem na mesma barra M5, classificar AMBIGUOUS e
  atribuir −1R na carteira, nunca vitória.
- Bloquear novo trade no mesmo ativo enquanto outro trade do mesmo
  ativo continua; simulação portfolio aplica no máximo 1 posição global.
  Desempate para sinais simultâneos: maior volume financeiro relativo
  conhecido no instante do gatilho, seguido ordem alfabética do símbolo.
- Sem stop dinâmico, take-profit parcial, filtro BTC novo ou seleção
  retrospectiva de ativos.

## Dados, períodos, comparação justa
10 contratos fixos MEXC: TAO, SOL, AVAX, ENA, DOT, ZEC, HYPE, AAVE, BTC, ETH.
BTC é incluído como ativo de referência/controle já usado nas análises anteriores,
mas os relatórios de altcoins também o separam explicitamente.
Janelas históricas FIXAS (42 dias cada):
- **S — menos examinada**: 24/04 11:00 UTC → 05/06 11:00 UTC.
- **T**: 05/06 → 17/07, 11:00 UTC.
- **U**: 17/07 → 28/08, 11:00 UTC.
- **V**: 28/08 → 09/10, 11:00 UTC.
- **W**: 09/10 → 20/11, 11:00 UTC.

Incluir warmup mínimo M5 80 barras e H1 80 barras, não inventar dados
ausentes; uma janela incompleta deve falhar, não ter ROI parcial apresentado.
Para cada janela executar **BCM-1 LONG, BCM-1 SHORT e BCM-1 ambos**;
comparar com **F original SHORT inalterada** nos mesmos contratos, datas e
custos. Reportar 21+21 dias, 42 dias, nº candidatos, operações da
carteira, TP/SL/TIME/AMBIGUOUS, R, ROI composto sob 1% risco por
trade, drawdown, número de dias e cobertura. Combinar janelas
temporalmente sem somar percentuais. Todas as análises são
retrospectivas, NÃO são resultados prospectivos nem provas de lucro futuro.

## Critérios de estudo para avançar
- ROI líquido positivo em **S e pelo menos 3 de 4 janelas T–W**,
  considerando a versão global BCM-1 ambos, **sem** escolher
  preferencialmente apenas LONG ou SHORT após observar resultados.
- Positivo no total e superior à F nos mesmos 210 dias.
- Pelo menos 40 trades de carteira nos 210 dias;
  até 3 trades por dia em média; drawdown máximo <=10%
  arriscando hipoteticamente 1% da banca por trade.
- Os dois sentidos LONG e SHORT precisam ser reportados,
  ainda que um lado vá pior. Caso falhe critério, rejeitar,
  não "corrigir" thresholds com base nessas mesmas datas.
- Sensibilidade a taxas dobradas e paper prospectivo obrigatórios
  **somente para a hipótese que passar**.

## Riscos técnicos
OHLC M5 não informa ordem intrabar de toques SL/TP; fill
next-open pode ser irreal com gaps/slippage, e taxas assumidas
não representam confirmação de fee do usuário. Funding, lotes,
liquidação, spread e alavancagem não são simulados. Com capital
de US$1, tamanho mínimo/margem podem tornar o plano não executável.
Nenhum desses testes executa dinheiro ou justifica entrar no
mercado agora.

## Implementação
scripts/audit_compression_momentum.py e
tests/test_compression_momentum.py. Executar em GitHub Actions
em branch experiments/confluence-tao-20261120 sem merge.


---

## Resultado final do teste congelado — 20/11/2026

O GitHub Actions executou as CINCO janelas de 42 dias de MEXC USDT
perp com os mesmos 10 contratos e sem preenchimento de gaps históricos.
**50 combinações contrato/janela processadas com dados completos**;
**307 testes automatizados aprovados**. Nenhuma ordem real executada.

- [Ação GitHub, teste unitário e cinco janelas aprovadas](https://github.com/VinyRhyu/mexc-futures-scanner/actions/runs/44761927459)
- O script foi congelado antes da ação e não foram alterados limiares
  segundo os resultados. A ação rodou as variantes BCM_BOTH, BCM_LONG,
  BCM_SHORT, e controle F_baseline_SHORT.

### ROI composto por janela (1% do saldo de risco por trade; custos hipotéticos)

| 42 dias UTC | F SHORT | BCM LONG | BCM SHORT | BCM carteira LONG+SHORT |
|---|---:|---:|---:|---:|
| S 24/04–05/06 | -0,685% | -9,248% | -7,379% | **-14,237%** |
| T 05/06–17/07 | +0,893% | -8,425% | -20,502% | **-26,464%** |
| U 17/07–28/08 | -1,696% | -1,174% | -8,923% | **-9,083%** |
| V 28/08–09/10 | -2,237% | -4,603% | -11,417% | **-13,114%** |
| W 09/10–20/11 | -1,263% | -8,431% | -2,782% | **-10,079%** |
| **210 dias, encadeamento aproximado** | **-4,917%** | **-28,256%** | **-42,247%** | **-55,202%** |

Última linha calculada como produto dos cinco fatores (1 + ROI_i/100) - 1,
**não** soma aritmética. Cada janela foi simulada isoladamente, logo
os números de 210 dias são uma aproximação concatenada, não recomputação
de carteira contínua atravessando bordas. Não foi calculado o drawdown
global de 210 dias a partir de trades completos: não atribuir valor inventado.

### Resultados das operações selecionadas pela carteira

| Modelo | Candidatos | Trades executados em papel | TP | SL | TIME | R líquido agregado |
|---|---:|---:|---:|---:|---:|---:|
| F original SHORT | 102 | 91 | 30 | 49 | 12 | -4,515R |
| BCM LONG | 284 | 245 | 75 | 135 | 35 | -31,794R |
| BCM SHORT | 321 | 239 | 65 | 137 | 37 | -53,608R |
| **BCM LONG+SHORT** | **605** | **475** | **140** | **265** | **70** | **-77,638R** |

As variantes LONG/SHORT são avaliadas separadamente como subcarteiras
condicionadas aos trades aceitos pelo replay BCM completo;
não devem ser somadas como se fossem a mesma carteira combinada.
No portfólio combinado houve 140 TPs contra 265 SLs e 70 timeouts.
Taxa de acerto TP/(TP+SL) ≈ 34,57%. O pior drawdown observado
em janela de 42 dias foi **29,891%** (T, portfólio combinado);
não representa DD de todo o período.

### Decisão e implicações

**REPROVADO.** O BCM_BOTH teve ROI negativo em S/T/U/V/W, falhando
com grande margem os critérios pré-estabelecidos. A hipótese de LONG
isolado também perdeu em todos os períodos; o SHORT isolado idem.
Não há justificativa para alterar os parâmetros sobre esta mesma amostra.
A versão F segue **menos negativa**, não aprovada. Nenhuma regra deve
ser integrada ao Telegram ou ao runtime main.

O padrão tem alta taxa de falsos rompimentos apesar de compressão,
corpo forte, volume relativo e H1 alinhado. Os stops atingidos
superam os alvos, mesmo com modelo de custo fixo conservador.
Isso não prova que toda estratégia de momentum falhe, mas rejeita
a configuração BCM-1 nos dados e condições testados.

### Avisos e próximos passos não executados

- Não verificamos taxa real da conta, spread intra-candle,
  funding, margem de liquidação e lote mínimo.
- Não realizamos sensitividade dobrando custos porque não há
  estratégia candidata a integração após o teste inicial.
- Os 210 dias são históricos; não é paper prospectivo.
- Melhor próximo trabalho é um diagnóstico quantitativo de
  **onde ocorreram os 265 stops** (volatilidade, regime, liquidez,
  horário, distância ao SL, direção), seguido de hipótese nova
  fixada ANTES de outra janela inédita, ou avaliar
  modelos de regime/market-making com book/tick dados, sem
  perseguir apenas um ROI retrospectivo.
- Manter apenas a PR experimental. A etapa de coleta histórica
  foi removida do CI automático após a execução, para evitar
  repetir centenas de chamadas à API a cada commit;
  o teste pode ser reproduzido manualmente pelos cinco comandos
  python -m scripts.audit_compression_momentum --window S/T/U/V/W
  (executar um valor de janela por vez) com acesso à API MEXC.
