# HYPE — replay sem alterações do WATCH 16–17/11 em quatro períodos anteriores

**Data:** 20/11/2026. **Contrato:** HYPE_USDT perpétuo MEXC.
**Regras congeladas:** `docs/hype-watch-crossperiod-preregistered-2026-11-20.md`.
**Código executado:** `scripts/audit_hype_watch_crossperiod.py`, reutilizando
sem mudanças `watch_at`, `score_direction` e `execute` do
`scripts/audit_hype_two_stage_1617.py`. A função `confirmation`
apenas recebeu um `cutoff_ms` opcional para aplicar o mesmo critério
em cada janela; no estudo anterior, o padrão segue exatamente END original.
**CI concluído com sucesso:**
https://github.com/VinyRhyu/mexc-futures-scanner/actions/runs/44837848685

**Caráter:** simulação paper retrospectiva com candles públicos MEXC.
Janelas não contêm 16 e 17 de novembro, mas foram examinadas por outros
testes: **não é amostra histórica intocada, nem teste prospectivo.**
H1 somente candles fechados; M5 candles fechados na decisão. Séries sem
lacunas. 160h de aquecimento H1, 10h M5, e duas horas após o final para
avaliar desfechos, sem gerar novos alertas ou confirmações.
Nenhuma ação real ou alteração no scanner principal, main, Telegram.

## Regras aplicadas, idênticas às dos dois dias

- WATCH de TURN: cruzamento EMA9/EMA21 M5, corpo ≥0,25 ATR14, volume ≥0,8x.
- WATCH de BREAK: fechamento rompe máxima/mínima das 6 M5 anteriores,
  corpo ≥0,35 ATR14 e volume ≥0,8x.
- WATCH de DRIFT: EMA9/EMA21 alinhadas, EMA9 inclinada e retorno de
  6 M5 ≥0,35%, volume ≥0,55x.
- Dedup 30 minutos por família+direção e 30min por direção na união.
  Prioridade TURN > BREAK > DRIFT. Nenhum veto por tendência H1.
- Etiqueta FUTURA para avaliação somente: movimento favorável +1,25%
  antes de movimento adverso −0,75% em 90min, empate desfavorável;
  igual nos checkpoints de referência de todos os M5 e duas direções.
- Após WATCH, confirmar nos próximos até 6 M5 por rompimento de 6 M5,
  corpo ≥0,40 ATR e volume ≥1,0x. Entrada hipotética na próxima
  abertura M5, SL estrutura 12 M5 ±0,1 ATR, TP 1,8R bruto,
  RR líquido mínimo 1,2, expiração 24 M5 (2h).
- Taker assumido 0,06% por lado; slippage hipotético 0,02% por lado;
  1% de risco do saldo por trade; carteira com uma única posição
  simultânea. Sem funding, ticks, spreads dinâmicos, fills ou liquidação.

## Qualidade dos alertas em relação à taxa-base

| Janela UTC | Dias | Checkpoints ambos sentidos | Base | WATCH | Alertas | Acertos / falhas WATCH | Aumento |
|---|---:|---:|---:|---:|---:|---:|---:|
| T 05/06–17/07 | 42 | 24.192 | 22,131% | 23,438% | 1.536 | 360 / 1.176 | +1,307 pp |
| U 17/07–28/08 | 42 | 24.192 | 12,054% | 13,247% | 1.389 | 184 / 1.205 | +1,193 pp |
| V 28/08–09/10 | 42 | 24.192 | 11,529% | 13,034% | 1.358 | 177 / 1.181 | +1,505 pp |
| W0 09/10–16/11 00h BRT | 37,667 | 21.696 | 13,256% | 15,453% | 1.236 | 191 / 1.045 | +2,197 pp |
| **Total ponderado** | **163,667** | **94.272** | **14,782%** | **16,525%** | **5.519** | **912 / 4.607** | **+1,743 pp** |

Cada checkpoint M5 é avaliado em LONG e SHORT, logo dois pontos por
candle e eventos correlacionados; **não são 94 mil observações independentes**.
5.519 alertas em 163,667 dias = 33,72 avisos/dia. Mediana de
tempo do WATCH até tocar 1,25% favorável entre acertos:
T 40min; U 40min; V 50min; W0 45min. Não significa que o
detector acertou no primeiro candle do movimento.

Referência original 16/17: base 23,35%, WATCH 24,66%,
73 avisos, 18 acertos, 55 não-acertos.
Nos quatro períodos novos, a vantagem do WATCH sobre a base é
pequena, consistentemente positiva, e **falhou no limite de 12
avisos/dia pré-registrado**, além da maioria dos alertas não
alcançar o alvo direcional.

## Tipos de WATCH

| Período | TURN precisão (n) | BREAK precisão (n) | DRIFT precisão (n) |
|---|---:|---:|---:|
| T | 24,458% (323) | 23,490% (1.192) | 24,613% (1.227) |
| U | 16,118% (304) | 11,389% (1.159) | 16,301% (957) |
| V | 12,541% (303) | 12,643% (1.139) | 15,855% (965) |
| W0 | 11,915% (235) | 14,341% (1.039) | 18,498% (892) |

Os grupos de família se sobrepõem; **não somar n** e não escolher
um vencedor pós-resultado. O TURN de 40% visto nos dois dias 16/17
era amostra pequena (10 avisos) e não se sustentou aqui.

## Tendência H1: diagnóstico, NÃO nova regra

Sem mudar o detector, dividimos os 5.519 alertas pela direção
do último H1 fechado frente à EMA20 no momento do WATCH.

| Grupo | Alertas | Acertos | Precisão |
|---|---:|---:|---:|
| H1 alinhado ao WATCH | 2.968 | 536 | 18,059% |
| H1 contrário | 2.551 | 376 | 14,739% |
| WATCH total | 5.519 | 912 | 16,525% |

Exigir H1 alinhado **reduziria os avisos em 46,22%**, mas também
eliminaria **41,23% dos alertas que atingiram a barreira favorável**.
Esse é um contraste de detecção histórica, **NÃO um backtest com
reescalonamento da carteira global**. Não afirmar melhor ROI.
O filtro também pode perder reversões e capturas de mudança de
regime, como as de 16/11.

## Funil financeiro: todas as posições da carteira

| Janela | WATCH únicos | Confirmados | Elegíveis RR | Selecionados (1 posição) | TP | SL | TIME | ROI a 1% risco | MDD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| T | 1.536 | 658 | 647 | 356 | 29 | 86 | 241 | −29,967% | 36,952% |
| U | 1.389 | 578 | 509 | 311 | 24 | 65 | 222 | −36,532% | 39,703% |
| V | 1.358 | 642 | 579 | 339 | 30 | 83 | 226 | −35,793% | 36,554% |
| W0 | 1.236 | 564 | 498 | 286 | 24 | 61 | 201 | −18,432% | 26,864% |
| **Soma de eventos** | **5.519** | **2.442** | **2.233** | **1.292** | **107** | **295** | **890** | **−76,721% composto entre blocos** | **não somar DDs** |

ROI composto é produto dos quatro retornos por janela **com cada
período reiniciado em 100% de capital e sem carry de posições**,
uma medida descritiva das perdas acumuláveis, não uma simulação
monolítica exata de 163,67 dias. Soma dos R líquidos nas carteiras
independentes: −142,324R. Frequência: 7,89 trades/dia, acima do
limite 3/dia. Em todos os períodos, prejuízo e DD muito acima
de 10% a 1% de risco.

Os 890 encerramentos por tempo representam 68,89% dos trades.
TPs 107/1.292 = 8,28% e SLs 295/1.292 = 22,83%. Esse padrão
não demonstra que apenas alongar prazo seria útil; prazo maior
aumenta exposição e mudaria seleção global, exigindo novo teste
pré-registrado.

## Decisão

- **Detecção:** pequena elevação de precisão contra a taxa-base,
  porém 4.607/5.519 avisos sem alcançar a etiqueta e ~34 por dia.
  Insuficiente para aprovar um radar seletivo.
- **Entrada:** sem edge: 4/4 períodos com ROI negativo, altíssimo
  drawdown, excesso de posições e saídas por tempo. Hipótese de
  trading reprovada.
- **Filtro H1:** causa grande redução de alertas mas sacrifica
  quase metade dos acertos; observar, não implementar.
- Não ajustar limiares em cima dessas janelas para forçar resultado.
  Para próxima pesquisa, mudar o tipo de pergunta (previsão de
  persistência e falsos rompimentos, observabilidade de regime),
  pré-registrar e avaliar dados futuros ainda não observados.
  Apenas WATCH contextual não executável é candidato à discussão,
  sem prometer performance.
