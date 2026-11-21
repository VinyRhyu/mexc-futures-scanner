# HYPE — oito movimentos de 16 a 20/11/2026: replay causal e verificações

**Data do estudo:** 20/11/2026. **Ativo:** HYPE_USDT contrato perpétuo MEXC.
**Execução reprodutível:** https://github.com/VinyRhyu/mexc-futures-scanner/actions/runs/44828807092
**Código:** `scripts/audit_hype_eight_moves_20261120.py`
**Pré-registro antes da extração:** `docs/hype-eight-moves-preregistered-2026-11-20.md`.
**Horário:** São Paulo, UTC−03.
**Fonte:** 1.437 candles M5 e 275 candles H1, inclusive aquecimento; base da
semana 16/11 00h00 a 20/11 19h10. Candles M5/H1 sem buracos conforme
validação do coletor público da MEXC.

## Movimentos escolhidos pelo usuário (observação a posteriori)

O rótulo de direção foi informado *depois* da ocorrência. Não há hipótese
de que a estratégia pudesse antecipar o início escolhido.

| Caso | Janela BRT | Direção declarada | Abertura | Close final | Variação da janela | Extremo a favor |
|---|---|---|---:|---:|---:|---:|
| 16a | 16/11 08h–10h | SHORT | 67,518 | 65,315 | −3,263% | mínimo 65,088 às 09h50 |
| 16b | 16/11 10h–12h15 | LONG (reversão) | 65,315 | 65,971 | +1,004% | máximo 68,100 às 11h35 |
| 16c | 16/11 12h15–19h | LONG lento | 65,971 | 70,163 | +6,354% | máximo 70,795 às 18h50 |
| 17a | 17/11 02h30–06h15 | SHORT | 70,422 | 68,710 | −2,431% | mínimo 68,543 às 06h05 |
| 17b | 17/11 11h15–12h30 | SHORT | 69,880 | 69,312 | −0,813% | mínimo 68,822 às 12h05 |
| 18 | 18/11 10h15–13h | SHORT | 68,760 | 65,890 | −4,174% | mínimo 65,701 às 12h45 |
| 19 | 19/11 00h–08h30 | LONG | 66,630 | 68,661 | +3,048% | máximo 68,775 às 08h25 |
| 20 | 20/11 08h–12h30 | SHORT | 64,952 | 61,954 | −4,616% | mínimo 61,444 às 12h25 |

*16b é uma janela de trabalho inferida do próximo início 12h15 porque
o usuário não indicou o término exato da recuperação imediata.*

## Contexto de EMA20 H1 ANTES do movimento e primeira confirmação observada

Marcador descritivo independente, pré-registrado: candle M5 FECHADO
rompe máxima/mínima das 12 M5 anteriores, corpo >=0,5 ATR14 M5 e
volume cotado >=1,2x mediana das 12 anteriores. Sem H1 como veto.
Long/short na própria direção da ruptura, nunca por rótulo de futuro.

| Caso | H1 ao início vs EMA20 | Primeiro marcador do mesmo lado | Atraso desde início |
|---|---|---|---:|
| 16a SHORT | H1 altista | 08h45 | 45min |
| 16b LONG | H1 baixista | 11h20 | 80min |
| 16c LONG | H1 altista | 16h55 | 280min |
| 17a SHORT | H1 altista | 03h40 | 70min |
| 17b SHORT | H1 altista | 12h10 | 55min |
| 18 SHORT | H1 baixista | 10h55 | 40min |
| 19 LONG | H1 baixista | 00h50 | 50min |
| 20 SHORT | H1 baixista | 08h05 | 5min |

Somente **5 de 8** têm confirmação até uma hora. Três
atrasam mais de uma hora, incluindo o LONG de +6,354% que só gerou
marcador pelo critério de rompimento às 16h55. **Cinco de oito** começam
em direção oposta ao sinal H1 da EMA20. Filtrar rigidamente pela
direção H1 excluiria diversos dos eventos selecionados após o fato;
suspender o filtro indiscriminadamente gera sinais ruins.

## Simulações diagnósticas para os cinco eventos com primeiro gatilho até 1h

São **hipóteses de entrada**: preço abertura da M5 imediatamente
seguinte ao fechamento de confirmação, stop extremo oposto das 12 M5
anteriores ±0,1 ATR, TP bruto 1,8R, horizonte máximo 24 M5 (2h),
custo taker 0,06% + slippage 0,02% por lado.
A configuração serve para estudar sinais, NÃO constitui uma estratégia
aprovada ou um replay prospectivo independente.

| Episódio | Confirmação / entrada BRT | Direção | Entry | Stop | TP | Desfecho em até 2h | R líquido simulado |
|---|---|---|---:|---:|---:|---|---:|
| 16a | 08h45 | SHORT | 66,590 | 67,90840 | 64,21688 | TIME 10h40–10h45 | +0,6074R |
| 17b | 12h10 | SHORT | 68,941 | 70,04778 | 66,94880 | TIME 14h05–14h10 | +0,3498R |
| 18 | 10h55 | SHORT | 68,106 | 68,91230 | 66,65466 | TP 11h45–11h50 | +1,4666R |
| 19 | 00h50 | LONG | 67,242 | 66,11426 | 69,27194 | TIME 02h45–02h50 | +0,4731R |
| 20 | 08h05 | SHORT | 64,632 | 65,46304 | 63,13614 | TP 09h05–09h10 | +1,4901R |

A estratégia F original, imutável, não emitiu nenhuma operação autorizada
na semana: apenas 18/11 04h20 SHORT com RR líquido 0,934 abaixo do
piso 1,2. F somente SHORT e opera rejeições de rompimento, não continuidade
genérica de preço.

## Teste da hipótese descritiva em toda a semana (e não só acertos escolhidos)

138 marcadores direcionalmente determinados (81 SHORT / 57 LONG).
43 ocorreram durante ao menos uma das oito janelas; 39 na direção
previamente indicada pelo usuário; **95 fora de todas as janelas**.
134 marcadores aceitos pelo critério de RR líquido ex-ante, um
bloqueado e três perto do final sem horizonte de 2h disponível.

Na simulação para a semana completa, com apenas uma posição simultânea
global, 49 operações escolhidas, 4 TP, 13 SL, 32 TIME,
**−4,208R** e **−4,255%** retorno composto com 1% de risco hipotético
por operação; drawdown máximo 7,878%. *Esse resultado NÃO generaliza
para outras semanas e o marcador não deve ser implementado na produção.*

Importante: o subconjunto de oito movimentos foi selecionado retrospectivamente
por um humano. As operações selecionadas em toda a semana demonstram que
encontrar determinados movimentos após o fato não demonstra ganho ao operar
sem saber o futuro. Precisamos separar detecção precoce de início de
tendência, reversão, continuação e tendência lenta; uma regra genérica
de rompimento não funcionou bem.

**Limitações:** ticks e fills reais ausentes; timestamp de saída é janela
M5, não instante de execução; custos e slippage hipotéticos, funding
e liquidação não considerados; amostras curtas e sem validação
fora da amostra; períodos e direção foram selecionados com hindsight.
Nenhuma alteração no scanner de produção, Telegram ou execução de ordens.

## Sugestão de pesquisa, não regras de operação

Classificar REGIME observável causalmente: deslocamento de tendência com
sweep/rejeição, continuação impulsiva de alta/baixa e reversão após
exaustão. Para cada família, definir gatilho objetivo e medir TODOS
os períodos (sem escolher apenas o que deu certo), com risco, taxas
e frequência. Diferenciar "monitorar possível reversão" de "liberar
entrada": a primeira fase admite indícios fracos, a segunda exige
confirmação e relação risco-retorno ex-ante. Se testar, pré-registrar
parâmetros e guardar janela prospectiva não examinada.
