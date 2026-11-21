# Resultado BCM-1: compressão + momentum, LONG e SHORT — 210 dias

Rodada de pesquisa em 20/11/2026. Regras do modelo BCM-1 foram congeladas
ANTES do backtest em
[compression-momentum-preregistered-2026-11-20.md](compression-momentum-preregistered-2026-11-20.md).

Run auditável: https://github.com/VinyRhyu/mexc-futures-scanner/actions/runs/44761927459
- GitHub Actions: **completed / success**.
- Testes: **307 passed**.
- Cinco janelas S/T/U/V/W de 42 dias, dez contratos MEXC
  BTC, ETH, TAO, SOL, AVAX, ENA, DOT, ZEC, HYPE e AAVE.
- Nenhuma falha de continuidade M5/H1, nenhuma substituição de ativos.
- Entrada hipotética no open M5 seguinte, TP 1,8R, SL fixo da vela
  de rompimento +/-0,1 ATR, saída no máximo em 24 M5; taxa taker
  0,06% + slippage 0,02%, **por lado**.
- Simulação global de apenas uma posição ativa; risco hipotético de
  1% do saldo por trade, não alavancagem real.
- Dados retrospectivos; todos os períodos já integram o processo amplo
  de pesquisa, **não há conjunto prospectivo validado**.

## Resultados por período

| Modelo | 24/04–05/06 S | 05/06–17/07 T | 17/07–28/08 U | 28/08–09/10 V | 09/10–20/11 W | 210 dias, retorno composto aproximado |
|---|---:|---:|---:|---:|---:|---:|
| F baseline SHORT | -0,685% | +0,893% | -1,696% | -2,237% | -1,263% | **-4,917%** |
| BCM LONG | -9,248% | -8,425% | -1,174% | -4,603% | -8,431% | **-28,256%** |
| BCM SHORT | -7,379% | -20,502% | -8,923% | -11,417% | -2,782% | **-42,247%** |
| BCM LONG+SHORT (exclusividade global) | -14,237% | -26,464% | -9,083% | -13,114% | -10,079% | **-55,202%** |

Combinação matemática das cinco rentabilidades por janela:
prod_janelas (1 + ROI_janela). Cada janela reiniciou a banca simulada;
os números da última coluna NÃO são um replay de carteira única
atravessando todos os limites de janelas. Não afirmar drawdown
máximo de 210 dias se não foi computado de trade a trade.

### Quantidade de operações globais selecionadas

- F SHORT: 91 trades em 210 dias.
- BCM LONG: 245 em 210 dias.
- BCM SHORT: 239 em 210 dias.
- BCM combinada: **475 trades**, dos quais 140 atingiram TP,
  265 atingiram SL e 70 tiveram saída por tempo.
- Resultados LONG/SHORT isolados não são somáveis à carteira
  combinada porque disputam os mesmos intervalos de capital.
- Em cada janela BCM combinada: S 79, T 113, U 55, V 127, W 101,
  respectivamente com ROI -14,237%, -26,464%, -9,083%,
  -13,114% e -10,079%.

### Por que o filtro econômico importa

Nas 50 avaliações ativo×janela:
- **3.656** eventos técnicos passaram no critério gráfico de
  compressão+rompimento.
- **3.048 (83,37%)** não resultaram em operação por **RR líquido
  insuficiente ou stop/preço inválido**, conforme diagnóstico interno.
- **608** operações foram aceitas na simulação individual por símbolo
  (286 LONG e 322 SHORT), e **475** escolhidas na carteira global.
  Não interpretar os 608 como operações efetivamente simultâneas.

A distância de stop deste protótipo, baseada apenas no candle gatilho,
pode ser estreita ante custo taker+slippage. Isto é uma **hipótese de
mecanismo**, não um diagnóstico causal demonstrado: o contador mistura
RR insuficiente e stop inválido. BTC e ETH geraram muitos padrões
técnicos (426 e 443) mas quase todos foram rejeitados (423 e 431),
consistentemente com essa possibilidade. Não reduzir as taxas
presumidas artificialmente para transformar o ROI em lucro.

### Decisão

**BCM-1 falhou critérios pré-registrados e não será integrado ao scanner
ativo nem ao Telegram.** Nenhuma das cinco janelas foi lucrativa na
carteira combinada, mesmo antes de financiamento, livro de ofertas,
liquidação ou restrições de lote. Não ajustar parâmetros para maximizar
um período já examinado, pois isso cria sobreajuste.

Próximo passo metodológico mais útil: antes de outra família de gatilhos,
auditar economia da execução e stops versus ATR e estrutura, com candles
M5/M15/H1 e taxa real de contrato. Se formular uma nova hipótese,
congelá-la antes do próximo conjunto de dados e exigir paper
prospectivo. Alternativa: testar uma abordagem de timeframe superior
(M15/H1) com menos sinais e folga real para os custos, sem assumir
rentabilidade. O projeto permanece paper-only nesta branch em PR rascunho.
