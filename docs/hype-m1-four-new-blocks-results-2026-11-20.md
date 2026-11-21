# HYPE — expansão do teste M1: quatro novos blocos e sete blocos no total

**Registro:** 20/11/2026. **Contrato:** HYPE_USDT MEXC futures.
**Experimento congelado:** `scripts/audit_hype_m1_trend.py`.
**Pré-registro e indisponibilidade antiga:** `docs/hype-m1-weekly-expansion-preregistered-2026-11-20.md`.
**Execução aprovada:** https://github.com/VinyRhyu/mexc-futures-scanner/actions/runs/44842423916

## Limite de dados e decisão de fallback ANTES dos resultados

O plano inicialmente previa pares seg–ter de 05/10, 12/10, 19/10, 26/10,
mas a MEXC devolveu **zero candles M1 para 05/10**, impedindo o teste
(https://github.com/VinyRhyu/mexc-futures-scanner/actions/runs/44842291237).
Em vez de fabricar valores, registraram-se previamente quatro alternativas
mais recentes, sem sobreposição com REF (16/17), CMP (09/10 de novembro)
e CMP2 (02/03 de novembro). O efeito de dia da semana agora não é controlado.

Janelas adicionais, BRT, início inclusivo/fim exclusivo:
- OCT26: 26–27 de outubro;
- NOV04: 04–05 de novembro;
- NOV06: 06–07 de novembro;
- NOV12: 12–13 de novembro.

Todos os quatro blocos possuem **3.090 candles M1, 720 M5 e 210 H1**
incluindo warmup e 2h futuras apenas para medir saídas.
A coleta rejeita falhas, duplicatas conflitantes, gaps e OHLC inválido.

## O que NÃO mudou

- WATCH original de M5 (TURN/BREAK/DRIFT);
- gatilho M1 de confirmação com 1m, corpo, volume e EMA9;
- gate M5 EMA9/EMA21 e gate H1 opcional;
- SL com máximos/mínimos de 15 M1 anteriores + 0,15ATR14;
- TP 1,8R bruto, RR líquido mínimo 1,2, máxima permanência 120 M1;
- taxas Taker 0,06% por lado + slippage assumido 0,02% por lado,
  total 0,16% roundtrip de notional;
- uma posição aberta por braço, risco hipotético de 1% do patrimônio;
- não operar de verdade, não alterar main/produção/Telegram.

A **única alteração ao código da estratégia** foi a lista de janelas
`PERIODS`. Comparação M1 vs M5 muda tanto a confirmação quanto
o stop, portanto não isola efeito causal do tempo de candle.

## Quatro blocos adicionais: retornos por regra

| Bloco | M5 original | M1_FAST | M1 + M5 tendência | M1 + M5 + H1 |
|---|---:|---:|---:|---:|
| 26–27/10 | +1,569% | −4,912% | −1,420% | +0,092% |
| 04–05/11 | +4,680% | +2,011% | +3,315% | −0,389% |
| 06–07/11 | −4,456% | −3,427% | −3,592% | −1,000% |
| 12–13/11 | +7,198% | +2,847% | +7,346% | +6,099% |
| **Composto dos quatro blocos** | **+8,897%** | **−3,657%** | **+5,403%** | **+4,726%** |
| Blocos com ROI positivo | 3/4 | 2/4 | 2/4 | 2/4 |

São carteiras de cada braço **independentes e reiniciadas a cada
bloco**. O produto dos retornos por bloco é um resumo descritivo,
não uma execução monolítica com posições carregadas no intervalo.

### M1 + M5 tendência — detalhes dos quatro novos blocos

| Bloco | Selecionados | TP | SL | TIME | ROI | DD | Latência mediana WATCH→sinal |
|---|---:|---:|---:|---:|---:|---:|---:|
| OCT26 | 12 | 3 | 6 | 3 | −1,420% | 3,690% | 8 min |
| NOV04 | 19 | 6 | 6 | 7 | +3,315% | 3,728% | 7 min |
| NOV06 | 5 | 0 | 3 | 2 | −3,592% | 3,592% | 5 min |
| NOV12 | 15 | 7 | 3 | 5 | +7,346% | 1,312% | 7 min |
| **Soma das contagens** | **51** | **16** | **18** | **17** | **+5,403% composto** | **não somar** | **5–8 min** |

Foram **16 TPs entre 34 encerramentos TP ou SL (47,1%)**, e
**16 TPs sobre 51 operações (31,4%)**, com outros 17 TIME de
resultado financeiro misto. O retorno positivo foi concentrado em
NOV12 e NOV04; não sustenta uma taxa de acerto majoritária
fora dos dias 16–17.

### Incluindo as três janelas da análise anterior (7 pares de dias)

| Braço | Operações | TP | SL | TIME | ROI encadeado | Blocos positivos |
|---|---:|---:|---:|---:|---:|---:|
| M5 original | 116 | 15 | 22 | 79 | +5,135% | 4/7 |
| M1_FAST | 108 | 25 | 47 | 36 | −7,536% | 3/7 |
| M1 + M5 tendência | 94 | 25 | 34 | 35 | +4,312% | 3/7 |
| M1 + M5 + H1 | 63 | 19 | 26 | 18 | −0,227% | 2/7 |

A série de sete pares representa **14 dias não contíguos**, todos
históricos, previamente examinados em outras investigações. Não
constitui backtest fora da amostra intocada e pode estar sujeita a
overfitting por escolha de modelo após observar resultados iniciais.
M1+M5 realiza **94/14 = 6,71 operações/dia**;
o limite de triagem original era <=3/dia.

## Resultado e decisão do protocolo

O M1 confirma mais depressa; isso foi demonstrado. Porém,
**M1 + M5 passou apenas em 2/4 janelas adicionais**, não
atendendo o critério fixado de 3/4 positivas e frequência
<=3 trades/dia. O M5 original teve ROI maior nos quatro blocos
(+8,897% vs +5,403%). Nenhuma nova estratégia passou no
protocolo de seleção.

**Não integrar ao scanner real.** A próxima comparação mais
informativa isolaria o gatilho M1 do stop M1, mantendo setup,
SL e risco ancorados no mesmo sinal M5, além de avaliar regime
de mercado sem selecionar dias pelo resultado. Critérios devem
ser definidos antes de observar novos dados cronológicos.

**Limitações:** spread, order book, taxas efetivas por símbolo
e conta, funding, gaps intrabar e fills não observados; slippage
de 0,02%/lado é suposição; M1 executa um replay OHLC, não ordens
reais; alavancagem amplia sensibilidade a spread, stops e
liquidação. Nenhuma alteração em produção ou ordem real.
