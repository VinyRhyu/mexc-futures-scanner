# HYPE — prever lucro líquido das operações elegíveis: resultados

**Data:** 21/11/2026. **Ativo:** HYPE_USDT perpétuo, MEXC.
**Protocolo congelado:** `docs/hype-economic-metalabel-preregistered-2026-11-21.md`.
**Código:** `scripts/audit_hype_economic_metalabel.py`.
**Testes de causalidade e classificação:** `tests/test_hype_economic_metalabel.py`.
**Run GitHub Actions:** https://github.com/VinyRhyu/mexc-futures-scanner/actions/runs/44909735986

**Pesquisa paper somente.** Sem alteração do scanner principal,
main, Telegram ou envio de ordens. O histórico utilizado havia sido
examinado por várias estratégias; *walk-forward* cronológico **não
elimina** viés de escolha histórica de modelo/parâmetros.

## Hipótese e desenho

No teste anterior, o meta-label foi criado sobre +1,25%
favorável / −0,75% adverso após o WATCH em até 90 minutos,
enquanto a operação só se iniciava depois da confirmação, com
stop e alvo diferentes. Neste teste, o alvo do aprendizado é
**`1[net_R > 0]` da operação realmente elegível no executor
original**, incluindo TIME positivo/negativo conforme o P&L
líquido real da simulação.

A variável resposta só fica disponível após a saída; nenhum
dado posterior ao fechamento da confirmação entra nas 13
features (EMA H1/M5, ATR, retorno, volume, corpo de candle,
estrutura, risco pré-preço de abertura, tempo após WATCH,
alinhamento H1 e família WATCH). Rotulagem/normalização do
modelo apenas nos conjuntos de treino. Embargo de 120 min
**depois do fim observado da operação** antes do começo
de cada teste; seleção do modelo nunca usa labels do teste.

Janelas:
- Treino T / teste U (17/07–28/08);
- Treino T+U / teste V (28/08–09/10);
- Treino T+U+V / teste W0 (09/10–16/11).

Somente operações **confirmadas e elegíveis** alimentam
os modelos, com duplicações do mesmo sinal/lado removidas
antes de treinamento e replay. Rótulos positivos incluem
TIME com líquido >0, e negativos incluem TIME com <=0.

- BASE: operar todos os elegíveis; verificação exata do
  backtest original por janela.
- H1_VOL_SIMPLE: último H1 fechado coerente com direção
  e volume relativo da confirmação >=1,2.
- LOGIT_TOP20_TRAIN: regressão logística regularizada (L2=0,02;
  LR=0,15; 140 épocas; z-score train-only; threshold percentil
  80 dos scores **do treino**), sem ajuste pelo teste.

**Executor congelado:** SL estrutural das últimas 12 M5
anteriores +0,1 ATR, TP bruto 1,8R, RR líquido ex ante
>=1,2, até 24 M5 (2h); stop primeiro na mesma vela;
1% risco da conta/trade; 1 posição simultânea; custo
suposto 0,06% taker + 0,02% slippage por lado
(0,16% ida+volta sobre notional). Sem funding, bid/ask,
fills, book/liquidação reais.

## Universos e taxas econômicas

| Período | WATCHs originais | Operações elegíveis | net R positivo dentre elegíveis |
|---|---:|---:|---:|
| T (treino original) | 1.536 | 647 | 264 (40,804%) |
| U | 1.389 | 509 | 192 (37,721%) |
| V | 1.358 | 579 | 244 (42,142%) |
| W0 | 1.236 | 498 | 207 (41,566%) |
| **Três períodos teste** | **3.983** | **1.586** | **643 (40,542%)** |

A seleção probabilística reteve **155 elegíveis** nos três
blocos, dos quais **64 (41,290%)** tinham net R positivo.
É um aumento mínimo sobre 40,542% da base, embora
o modelo reduza muito a quantidade de trades.

## Resultado financeiro por período e método

| Período TESTE | ALL_ELIGIBLE | H1_VOL_SIMPLE | LOGIT_TOP20_TRAIN |
|---|---:|---:|---:|
| U | −36,532% (311 trades) | −25,373% (195) | −3,922% (41) |
| V | −35,793% (339) | −25,777% (219) | −5,250% (24) |
| W0 | −18,432% (286) | −10,729% (187) | −8,034% (68) |
| **Composto das 3 carteiras de teste** | **−66,760%** | **−50,552%** | **−16,280%** |
| Janelas positivas | 0/3 | 0/3 | 0/3 |
| Operações selecionadas | 936 | 601 | 133 |
| TP | 78 | 61 | 8 |
| SL | 209 | 142 | 31 |
| TIME | 649 | 398 | 94 |
| Trades/dia | 7,693 | 4,940 | 1,093 |
| Max DD em qualquer janela | 39,703% | 29,532% | 12,585% |

ROI encadeado = produto (1+ROI_por_faixa), com 1% da
conta em risco por trade e reinício do capital por faixa.
Esse número NÃO representa uma única conta operando 168
dias sem interrupções.

## Métricas do classificador — qualidade probabilística

| Teste | Positivos elegíveis (base) | Positivos dos escolhidos | Brier do logit | Brier constante do treino | Skill |
|---|---:|---:|---:|---:|---:|
| U | 192/509 = 37,721% | 19/46 = 41,304% | 0,235218 | 0,235800 | +0,247% |
| V | 244/579 = 42,142% | 11/28 = 39,286% | 0,246759 | 0,244542 | −0,906% |
| W0 | 207/498 = 41,566% | 34/81 = 41,975% | 0,243452 | 0,243036 | −0,171% |

O Brier só melhorou em **1 de 3 testes** e o filtro
**não** conseguiu aumentar materialmente a precisão de
ganho líquido das operações elegíveis.

## Interpretação e decisão

1. O modelo econômico **não solucionou** o problema que
   desejávamos atacar: +64 sinais econômicos positivos
   em 155 elegíveis, comparado à base de 643/1.586.
2. A quantidade de operações selecionadas caiu de 936
   para 133 e o prejuízo caiu consideravelmente, mas
   o ROI simulado ficou negativo em **todos** os folds.
   Filtrar drasticamente reduz a exposição a perdas,
   mas não equivale a identificar oportunidades rentáveis.
3. Não atendeu os critérios fixados antes da simulação:
   0/3 períodos com ROI positivo, composto −16,280%,
   drawdown 12,585% >10%, Brier favorável 1/3 e não >=2/3.
   A frequência de 1,093 trade/dia ficou sob 3/dia.
4. A previsão de **probabilidade de R > 0** não estima
   o valor esperado líquido em R: uma operação levemente
   positiva não compensa obrigatoriamente outra que perde
   1R. A hipótese futura adequada poderia prever
   diretamente **expectativa de retorno líquido em R**,
   com erro e estabilidade verificados em dados NÃO
   utilizados em desenvolvimento; não retreinar nas mesmas
   janelas para extrair uma curva lucrativa.

**Decisão: reprovado para uso real.** Não alterar thresholds
ou pesos com base no resultado destes três blocos.
Necessário coletar novas sessões cronológicas depois do
pré-registro e, se possível, dados contemporâneos de spread,
book de ofertas e prints agressivos, incluindo custos e
fills mensuráveis antes de aprovar entrada ao vivo.

Todos os números vêm de dados de candles históricos,
não ordens reais; operações e retornos são hipotéticos.
