# HYPE — pareamento de entradas M1/M5 com SL e TP fixos no WATCH

**Data da análise:** 20/11/2026. **Ativo:** HYPE_USDT perpétuo MEXC.
**Especificação pré-registrada antes da execução:**
`docs/hype-m1-fixed-watch-risk-preregistered-2026-11-20.md`.
**Código:** `scripts/audit_hype_m1_fixed_watch_risk.py`;
**testes unitários:** `tests/test_hype_m1_fixed_watch_risk.py`.
**Execução completa bem-sucedida:**
https://github.com/VinyRhyu/mexc-futures-scanner/actions/runs/44849483992

**Natureza:** estudo exploratório histórico de sete janelas separadas de
48 horas de HYPE com candles M1 e M5 completos, 3.090 M1 e 720 M5 em
cada período, incluindo warmup e 2 horas apenas para monitorar saídas.
Histórico já utilizado em pesquisas anteriores, portanto **não é
validação prospectiva fora da amostra**. Não houve ordens, mudanças no
scanner real, main ou Telegram.

## Intenção M5 única, preço de execução variável

O WATCH original TURN/BREAK/DRIFT não foi mudado e passa a definir,
no seu instante de fechamento M5, stop além da máxima/mínima das
12 M5 encerradas (incluindo o candle de WATCH) +0,1 ATR14,
e TP fixo a 1,8 vezes a distância entre close WATCH e SL.
AMBOS são iguais para os braços M1 e M5 do mesmo WATCH,
independentemente dos preços de execução posteriores.

- `M5_FIXED`: confirmação antiga M5 após WATCH; usar SL/TP do WATCH,
  ignorando stop calculado pela confirmação.
- `M1_FIXED`: confirmação M1 e EMA9, com tendência EMA9/21
  M5 fechada, mantendo SL/TP do WATCH.
- `M1_FAST_FIXED`: confirmação M1 sem filtro EMA9/21 M5,
  mesmo SL/TP do WATCH.

Em todos: confirmação até 30 minutos após WATCH; preço de abertura
da M1 imediatamente após confirmação; impedir entradas no lado
errado dos níveis; RR líquido ex ante >=1,2 utilizando preço de
entrada efetivo, SL/TP imutáveis; encerramento em TP/SL ou 120 M1;
stop prioritário se TP/SL no mesmo minuto. Custo estimado
taker 0,06%/lado + slippage 0,02%/lado, total notional de
0,16% ida+volta; 1% do saldo arriscado a cada trade, uma posição
por vez; carteira reiniciada em cada bloco.

Essa comparação controla o **mesmo SL/TP e mesma resolução M1
das saídas**, mas ainda altera o gatilho e a elegibilidade de RR
conforme o preço: logo não é experimento causal perfeito.
Uma intenção antiga com TP referenciado ao WATCH pode ter
RR inadequado quando o M5 confirma mais tarde. Isto é uma
limitação esperada do desenho fixo, NÃO uma falha da coleta.

## Resultado por bloco e braço (ROI %)

| Bloco BRT | M5_FIXED | M1_FIXED | M1_FAST_FIXED |
|---|---:|---:|---:|
| 26–27/10 | −1,335 | −3,161 | −4,689 |
| 04–05/11 | +1,834 | −0,251 | −0,104 |
| 06–07/11 | −0,425 | −0,729 | −1,900 |
| 12–13/11 | +0,097 | +1,629 | +5,235 |
| 02–03/11 | +0,195 | −1,903 | −6,456 |
| 09–10/11 | 0,000 | −5,298 | −6,741 |
| 16–17/11 | +0,736 | −0,936 | −2,956 |
| **Composto entre 7 blocos** | **+1,078** | **−10,313** | **−16,786** |
| **Blocos positivos** | **4/7** | **1/7** | **1/7** |

Os retornos são calculados por carteira de cada braço, cada bloco
reiniciado em 100% e produtos encadeados somente descritivos.

## Contagens financeiras de sete blocos

| Braço | Posições | TP | SL | TIME | Trades/dia | DD máximo por bloco |
|---|---:|---:|---:|---:|---:|---:|
| M5_FIXED | 14 | 1 | 0 | 13 | 1,00 | 1,335% |
| M1_FIXED | 84 | 7 | 14 | 63 | 6,00 | 5,298% |
| M1_FAST_FIXED | 106 | 9 | 29 | 68 | 7,57 | 6,741% |

Na carteira `M1_FIXED`, 84 operações em 14 dias representam
média de 6/dia, acima do piso operacional pretendido <=3/dia.
O M5_FIX não alcançou frequência de 3/dia; apenas 14 trades
e 13 saídas por tempo tornam a aparente estabilidade frágil,
não uma estratégia "vencedora".

## Comparação pareada das mesmas intenções WATCH

Somente **13** WATCHs tinham entrada elegível nas regras
M5_FIXED E M1_FIXED (não são trades de carteira obrigatoriamente
selecionados). Os níveis SL/TP foram validados idênticos em todos.

- 11/13 confirmaram primeiro em M1, 1/13 teve M1 posterior à M5,
  1/13 coincidiu no mesmo momento;
- 8/13 tiveram R líquido isolado melhor no M1, 3/13 no M5,
  2/13 empate;
- o ganho de tempo mediano nas subamostras por janela foi
  de cerca de 2 a 4 minutos onde havia pares.

Esse diagnóstico **não pode** ser tratado como 8 vitórias
do M1 em 13 operações efetivamente realizadas: condiciona-se
à elegibilidade retrospectivamente observada nos dois
braços e ignora os sinais extras que diferenciam as carteiras.

## Por que difere do +5,855% anterior de 16 e 17?

No experimento M1 anterior, entrada M1 vinha com stop/TP
baseados nos 15 candles M1 anteriores à confirmação.
Agora M1 tem stop/TP imutáveis calculados no WATCH M5.
Ao mudar o preço de referência para risco, a frequência,
o RR permitido e os alvos mudam. Resultado neste novo
modelo fixo para 16–17/11: **−0,936% em M1_FIXED versus
+0,736% em M5_FIXED**. Essa diferença não autoriza afirmar
que o +5,855% original decorreu unicamente de stops;
demonstra que o +5,855% NÃO se transfere automaticamente
quando fixamos estrutura de risco idêntica.

## Conclusão

**Reprovado** segundo critério pré-registrado:
M1_FIXED superou M5_FIXED em apenas **1 de 7** blocos, perdeu
−10,313% composto no replay, embora possa melhorar entradas
individuais; 6 trades/dia em vez de <=3.
M1_FAST_FIXED perdeu −16,786%.
Não otimizar thresholds nos mesmos dados, nem adotar M5_FIXED
como estratégia pronta: sua contagem é baixa e não é robustez
estatística independente.

A contribuição útil para a próxima hipótese é medir,
em eventos novos ainda não examinados, a **probabilidade de
continuação da tendência** após um WATCH, com filtros de
qualidade pré-definidos e foco em reduzir alertas, em vez de
forçar entrada em todo rompimento.
Sem book, ticks, funding, fills reais, spread/slippage
dinâmicos ou simulação de margem/alavancagem.
