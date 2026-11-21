# HYPE_USDT — teste do gatilho M1 com contexto M5/H1

**Data:** 20/11/2026, replay executado às ~21h BRT.
**Protocolo congelado antes da coleta:** `docs/hype-m1-trend-preregistered-2026-11-20.md`.
**Código de análise:** `scripts/audit_hype_m1_trend.py`;
**testes unitários:** `tests/test_hype_m1_trend.py`.
**Fonte:** API pública de Futures MEXC, contrato HYPE_USDT,
M1, M5 e H1 somente candles fechados.
**Execução GitHub Actions:** https://github.com/VinyRhyu/mexc-futures-scanner/actions/runs/44841347339

## Integridade dos dados

Todos os três blocos possuem **3.090 candles M1, 720 M5 e 210 H1**
cada, incluindo períodos de aquecimento antes e duas horas depois
do encerramento para observar stops/TP/tempo; nenhuma lacuna nem
OHLC inválido. M1 foi buscado em páginas limitadas a 1.400 registros.

Períodos locais não sobrepostos (America/Sao_Paulo):
- REF: 16/11 00h a 18/11 00h (dois dias já escolhidos pelo usuário);
- CMP: 09/11 00h a 11/11 00h (comparação anterior);
- CMP2: 02/11 00h a 04/11 00h (comparação anterior).

**ATENÇÃO:** todos esses dados históricos já estavam sob investigação
em outros estudos; não são amostras prospectivas ou holdout intocado.

## Protocolos comparados

WATCH congelado M5: TURN / BREAK / DRIFT,
um por família+direção a cada 30 minutos, dedup de união por direção.

- `M5_ORIGINAL`: confirma M5 nos seis candles seguintes, SL baseado
  nas 12 M5 anteriores; o estudo original 16/17 foi replicado exatamente.
- `M1_FAST`: confirma em até 30 M1 após WATCH rompimento dos 5 M1
  anteriores, corpo >=0,35 ATR14 M1, volume >=1x,
  EMA9 M1 alinhada e inclinada; SL baseado em 15 M1 anteriores.
- `M1_M5_TREND`: anterior + M5 fechado com EMA9/EMA21 alinhadas
  e inclinação EMA9 coerente.
- `M1_H1_TREND`: anterior + último H1 fechado acima/abaixo EMA20
  a favor do mesmo lado.

Para ambos os tempos, TP bruto 1,8R, RR líquido >=1,2,
máx 120min, entrada abertura da vela seguinte, carteira de uma
única posição simultânea, capital arriscado 1% por operação,
taker 0,06% + slippage 0,02% em cada lado (0,16% ida+volta).
Ambiguidade intrabar tratada como STOP. Sem funding ou fills reais.

**Limite causal:** WATCH apenas com M5 completo; M1 confirma apenas
depois do WATCH; contexto M5/H1 escolhido pela última vela fechada
na hora da confirmação M1. Os rótulos de desempenho não influenciam
as entradas.

**Limitação comparativa:** versão M1 muda o *gatilho E a
escala do stop*, não apenas a resolução de tempo. Logo,
diferença entre ROI M1 e M5 não pode ser causalmente atribuída
somente ao uso de M1.

## Resultados por período

### REF — 16 e 17/11

73 avisos WATCH comuns a todos os modelos; baseline M5 original
foi reproduzido **exatamente**: 32 elegíveis, 17 selecionadas,
−3,204% ROI, 1 TP / 6 SL / 10 TIME.

| Regra | Mediana WATCH→confirmação | Operações escolhidas | TP | SL | TIME | ROI composto | DD |
|---|---:|---:|---:|---:|---:|---:|---:|
| M5 original | 15min | 17 | 1 | 6 | 10 | −3,204% | 4,387% |
| M1 FAST | 6min | 20 | 5 | 8 | 7 | +0,413% | 4,123% |
| M1 + M5 tendência | 6min | 16 | 6 | 4 | 6 | **+5,855%** | 1,990% |
| M1 + M5 + H1 tendência | 10min | 12 | 4 | 5 | 3 | −0,726% | 2,970% |

Amostra selecionada a posteriori pelo usuário, de apenas 48 horas;
esses resultados não demonstram edge.

### CMP — 09 e 10/11

65 WATCH comuns.

| Regra | Mediana WATCH→confirmação | Operações | TP | SL | TIME | ROI |
|---|---:|---:|---:|---:|---:|---:|
| M5 original | 10min | 17 | 3 | 5 | 9 | −0,655% |
| M1 FAST | 7min | 17 | 2 | 8 | 7 | **−3,732%** |
| M1 + M5 tendência | 8min | 14 | 2 | 7 | 5 | **−3,260%** |
| M1 + M5 + H1 tendência | 8min | 9 | 1 | 5 | 3 | −2,458% |

### CMP2 — 02 e 03/11

69 WATCH comuns.

| Regra | Mediana WATCH→confirmação | Operações | TP | SL | TIME | ROI |
|---|---:|---:|---:|---:|---:|---:|
| M5 original | 10min | 18 | 3 | 4 | 11 | +0,399% |
| M1 FAST | 7,5min | 14 | 3 | 5 | 6 | **−0,716%** |
| M1 + M5 tendência | 8min | 13 | 1 | 5 | 7 | **−3,358%** |
| M1 + M5 + H1 tendência | 9min | 9 | 1 | 3 | 5 | −1,614% |

Nenhum dos três braços M1 fechou os três períodos
com retorno positivo e todos superaram 3 trades por dia em REF;
a hipótese foi **reprovada pelos critérios de triagem pré-registrados**.

## Preços e horários de exemplos 16 e 17/11
Carteira selecionada exclusivamente do braço **M1 + M5 tendência**,
com uma posição simultânea em HYPE; todos horários de Brasília:

| Dia/hora confirmação e entrada M1 | Tipo | Entry USDT | Stop USDT | TP USDT | Saída simulada | R líquido |
|---|---|---:|---:|---:|---|---:|
| 16/11 08h45 | SHORT | 66,590 | 67,284143 | 65,340543 | TP no M1 de 09h13 | +1,42742R |
| 16/11 11h18 | LONG | 66,187 | 65,472943 | 67,472303 | TP no M1 de 11h33 | +1,43837R |
| 16/11 12h46 | LONG | 66,712 | 66,050789 | 67,902179 | TIME M1 14h45 | −0,02831R |
| 16/11 15h21 | LONG | 67,093 | 66,530432 | 68,105622 | TP M1 16h55 | +1,35132R |
| 16/11 18h35 | LONG | 69,087 | 68,618646 | 69,930036 | TP M1 18h43 | +1,26534R |
| 17/11 03h36 | SHORT | 69,530 | 70,201111 | 68,322001 | TIME M1 05h35 | +0,48156R |
| 17/11 12h37 | SHORT | 68,847 | 69,710643 | 67,292443 | TIME M1 14h36 | +0,35310R |

Esses registros **não são todos os 16 trades**: houve perdas relevantes
em outros horários. A tabela apenas exemplifica o efeito da
antecipação e os cenários do usuário. Horário de saída designa
o início da vela M1 que tocou TP/SL; não o tick exato.

**Observação:** exemplo SHORT 16/11 08h45 foi selecionado
e alcançou TP com o stop curto de M1. No estudo M5 original o
SHORT das 08h45 era inviável por posição LONG anterior ainda em
aberto e o SHORT escolhido às 09h15 terminou negativo. Mudaram
tanto stop/horizonte de escolha quanto a ordem de posições.

## Decisão

- **Velocidade:** confirmada melhoria descritiva, mediana 6–10min M1
  versus 10–15min no baseline M5.
- **Qualidade:** o pacote M1 + tendência M5 melhora muito no REF
  previamente estudado (+5,855%), mas piora em CMP/CMP2
  (−3,260% e −3,358%) e excede a frequência máxima.
- **Regime H1 rígido:** remove parte das reversões e tampouco salva
  lucratividade.
- **Operação real:** nenhuma variante aprovada.
- **Hipótese para nova pesquisa:** em vez de usar M1 para descobrir
  todos os movimentos, testar o **M1 como refinamento de EXECUÇÃO
  após setup M5 validado** — comparando em novo experimento a mesma
  intenção de entrada/risco, TP/SL e todas as oportunidades, com
  dados de outro período ainda não observado.
