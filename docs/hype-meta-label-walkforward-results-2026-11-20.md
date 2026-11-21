# HYPE — triple-barrier + meta-labeling em walk-forward sem olhar futuro

**Data da pesquisa:** 20/11/2026. **Ativo:** HYPE_USDT perpétuo da MEXC.
**Protocolo congelado antes dos resultados:**
`docs/hype-meta-label-walkforward-preregistered-2026-11-20.md`.
**Implementação em Python stdlib, sem alegar importação do mlfinpy:**
`scripts/audit_hype_meta_label_walkforward.py`.
**Testes unitários (incluindo causalidade das features e desempate
conservador de barreiras):**
`tests/test_hype_meta_label_walkforward.py`.
**GitHub Actions aprovado:**
https://github.com/VinyRhyu/mexc-futures-scanner/actions/runs/44851433554

Metodologia inspirada no MLfin.py (triple-barrier) e separação
temporal do scikit-learn, com regressão logística regularizada
implementada explicitamente para reproduzir o teste sem bibliotecas
externas: https://mlfinpy.readthedocs.io/en/stable/Labelling.html
e https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html.

O estudo é SOMENTE PAPER. Não houve ordens, Telegram,
scanner em produção, mudanças em main ou merge.
**Todo o histórico já foi examinado em outras investigações,
portanto não é prova prospectiva.**

## Precisão do rótulo: WATCH com três barreiras

WATCH original inalterado (TURN, BREAK, DRIFT), de M5 fechado,
com cooldown 30 minutos por família/direção e 30min por direção
na união. Para avaliar qualidade, a partir do close da vela
WATCH analisar até 18 M5 (=90 minutos):
- favorável +1,25% na direção do sinal;
- adverso −0,75%;
- tempo máximo 90 minutos. Se TP+SL no mesmo OHLC, classificar
  como adverso. Rótulo 1 apenas se favorável ocorrer primeiro.

Esta classificação ocorre **a partir do WATCH**, não do ponto
de entrada da estratégia. O trade só acontece após confirmação
M5 posterior e usa SL estrutural mais TP 1,8R bruto.
Há portanto **desalinhamento entre objetivo do classificador
e objetivo econômico real**.

## Walk-forward: treino anterior + embargo 90 minutos

| Treino (após embargo) | Teste | WATCHs teste | Êxitos no total |
|---|---|---:|---:|
| T: 05/06–17/07 | U: 17/07–28/08 | 1.389 | 184 |
| T + U | V: 28/08–09/10 | 1.358 | 177 |
| T + U + V | W0: 09/10–16/11 | 1.236 | 191 |
| **Teste agregado** | | **3.983** | **552** |

A janela W0 acaba antes dos movimentos de 16 e 17/11
usados para motivar pesquisas recentes; no entanto,
também já havia sido examinada anteriormente.

Apenas dados M5/H1 completados no WATCH compõem 13 features
de inclinação EMA, retornos direcionais, volume relativo,
ATR, distância ao canal, tendência H1 e família do detector.
Os parâmetros de padronização são exclusivos do conjunto
de treino; nenhum rótulo futuro é usado para decidir.
Regressão logística L2, 140 épocas, LR 0,15, limiar de
probabilidade no percentil 80 do *treino*, não do teste.

## Qualidade dos alertas, incluindo erros

| Teste | BASE, todos WATCHs | Simples H1 alinhado + vol >=1,2 | Meta-label top20 |
|---|---:|---:|---:|
| U | 184/1.389 = 13,247% | 62/456 = 13,596% | 41/122 = **33,607%** |
| V | 177/1.358 = 13,034% | 78/502 = 15,538% | 16/71 = **22,535%** |
| W0 | 191/1.236 = 15,453% | 86/489 = 17,587% | 60/193 = **31,088%** |
| **Agregado** | **552/3.983 = 13,859%** | **226/1.447 = 15,618%** | **117/386 = 30,311%** |

O meta-label reduz alertas de 3.983 para 386, mas também
descarta 435/552 avisos com rótulo favorável (78,8%);
o recall de alertas bem-sucedidos fica 21,2%. Esta
redução drástica está associada ao limiar de seleção
definido no treino e mudança da distribuição de preços.

## Qualidade probabilística: erro quadrático de Brier

| Teste | Logit | Constante baseada no TREINO | Skill = redução relativa no erro |
|---|---:|---:|---:|
| U | 0,111007 | 0,125368 | +11,455% |
| V | 0,111063 | 0,116468 | +4,641% |
| W0 | 0,122178 | 0,130844 | +6,623% |

Melhora de classificação e Brier nos três testes é
interessante para pesquisa, **mas não comprova
capacidade de selecionar trades lucrativos**.

## Carteira paper e custos, 1 posição simultânea

Usar EXECUTOR ORIGINAL de confirmação M5, não modificar
stop/TP/prazo (24 M5=2h), 1% da conta arriscado
por posição, RR líquido ex ante >=1,2, taker 0,06%
por lado e slippage suposto 0,02% por lado (0,16%
nominal roundtrip), sem funding/slippage efetivo.

| Teste | BASE | H1 simples | Meta-label |
|---|---:|---:|---:|
| U | −36,532% (311 trades) | −21,721% (142) | −2,517% (33) |
| V | −35,793% (339) | −16,901% (172) | −3,529% (19) |
| W0 | −18,432% (286) | −13,810% (153) | −11,455% (50) |
| **Encadeado** | **−66,760%** | **−43,934%** | **−16,730%** |
| **Soma de trades** | **936** | **467** | **102** |
| TP | 78 | 44 | 3 |
| SL | 209 | 106 | 15 |
| TIME | 649 | 317 | 84 |
| Operações/dia médio | 7,693 | 3,838 | 0,838 |
| Max DD de qualquer janela | 39,703% | 21,941% | 12,639% |
| Janelas positivas | 0/3 | 0/3 | 0/3 |

O backtest BASE foi verificado contra os números
congelados do relatório anterior em **cada janela**;
se essa verificação falhasse o programa abortaria.
Todas as séries históricas M5/H1 completas; o job passou
também nos testes unitários e demais testes de CI.

**Conclusão sobre viabilidade:** modelo probabilístico
aumenta a precisão do indicador WATCH, diminui alertas,
perdas e drawdown, mas **não gerou ROI positivo em nenhum
dos três períodos**. Reprovado pelo critério prévio.
Os poucos TPs do meta-label (3 em 102 trades) comprovam
o desalinhamento de etiquetas e executor — boa classificação
da barreira WATCH não garante lucro no TP calculado
posteriormente. Risco real/funding não estão computados.

## O que NÃO foi testado

- Freqtrade, FreqAI, NautilusTrader como engines; este teste
  usou o executor que já existia no repositório.
- Livro de ordens histórico, desequilíbrio de fluxo agressor,
  bid/ask real, porque essas séries não estão no arquivo
  de candles M5/H1 nem nos dumps históricos que usamos.
- Treinamento com rótulo da operação realmente executada
  (stop/TP a partir da confirmação). O presente rótulo
  é ligado ao WATCH e foi a hipótese pré-registrada.

**Próxima hipótese científica mais direta:** rotular
cada confirmação elegível pelo *resultado econômico líquido
do próprio executor*, treinando apenas com features
observadas NO MOMENTO DA confirmação e purging até o fim
da operação, mantendo um classificador simples e
testando em dados realmente posteriores à data de escolha.
Não ajustar um limiar de decisão nos mesmos três blocos
para obter um lucro retrospectivo; recolher dados futuros
prospectivos com spread e fills medidos antes de liberar
ordens. Nenhuma alteração em produção.
