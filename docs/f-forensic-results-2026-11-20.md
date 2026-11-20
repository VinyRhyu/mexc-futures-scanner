# Diagnóstico da estratégia F: diferenças entre TP, SL e TIME (168 dias)

**Pesquisa retrospectiva, 20/11/2026. Não aprova filtros nem sinais reais.**
**Ação GitHub concluída:** https://github.com/VinyRhyu/mexc-futures-scanner/actions/runs/44825054073
**Código reproduzível:** scripts/audit_f_forensic.py
**Regras pré-fixadas antes de ler os dados:** docs/f-forensic-preregistered-2026-11-20.md

A CI executou testes sem rede e a análise das quatro janelas sem falha de cobertura.
São contratos MEXC perp USDT TAO, SOL, AVAX, ENA, DOT, ZEC, HYPE, AAVE,
BTC, ETH, incluindo os dois benchmarks de grande capitalização (não só altcoins).
Uma posição GLOBAL de cada vez, exatamente como no replay F já testado.
Preços simulados, NÃO fills reais.

## Reprodução da baseline

| Janela UTC | Candidatos F | Selecionados | TP | SL | TIME | ROI simulado 1% risco |
|---|---:|---:|---:|---:|---:|---:|
| T 05/06–17/07 | 28 | 24 | 8 | 12 | 4 | +0,893% |
| U 17/07–28/08 | 10 | 10 | 2 | 6 | 2 | -1,696% |
| V 28/08–09/10 | 28 | 27 | 9 | 15 | 3 | -2,237% |
| W 09/10–20/11 | 25 | 20 | 7 | 10 | 3 | -1,263% |
| **168 dias** | 91 | **81** | **26** | **43** | **12** | **-4,261% composto** |

Retornos em R: TP +34,112R (média +1,312R); SL -43,000R (todos -1R,
com risco definido incluindo custos); TIME +4,993R (média +0,416R).
Total F -3,894R nas quatro carteiras. A ausência de AMBIGUOUS
nos trades escolhidos não exclui problemas de ordem intrabar no mercado real.

## Indicadores causais no sinal ou na abertura seguinte

| Atributo | Mediana TP | Mediana SL | AUC TP-vs-SL global | AUC comparando mesma moeda E período |
|---|---:|---:|---:|---:|
| Quote volume relativo ao histórico M5 | 3,093x | 2,276x | 0,639 | **0,494** |
| Distância stop / ATR14 antes da entrada | 1,482x | 1,649x | 0,393 | 0,455 |
| ATR14 / preço do candle | 0,554% | 0,470% | 0,559 | 0,558 |
| Pavio superior / range do candle | 0,681 | 0,670 | 0,477 | 0,403 |
| Retorno M5 nas últimas 1h | +1,102% | +0,887% | 0,574 | 0,558 |
| Excesso de sweep acima resistência / ATR | 0,621x | 0,605x | 0,468 | 0,351 |
| Distância do close H1 abaixo EMA20 | 1,071% | 1,341% | 0,441 | 0,429 |

AUC é apenas estatística de ordenação: 0,5 indica nenhuma discriminação e
1,0 discriminação perfeita ao favor de valores altos nos TPs. Valor <0,5
não significa falha na hipótese de valores BAIXOS. **Nenhum desses números
tem significância comprovada** após múltiplas comparações.

A comparação estratificada usou 77 pares possíveis de TP e SL dentro de
apenas **oito** grupos com ambas as classes (mesma moeda e janela de 42 dias).
Os pares não são independentes. Valores afastados de 0,5 por pequenos
subgrupos podem ser ruído e são influenciados pela mistura de ativos.

### Conclusão sobre volume

O volume parecia o melhor atributo na população agregada (AUC 0,639,
medianas 3,09x versus 2,28x). Quando TP e SL são comparados **dentro da
mesma moeda e janela**, o AUC vira **0,494**, praticamente ausência de
discriminação. Isto sugere confundimento por tipo de ativo/regime.
**Não aumentar o volume mínimo para “filtrar SLs” com esses dados.**

Não houve separação útil estável por tamanho de pavio.
ATR relativo e retorno M5-1h tiveram AUC estratificado ~0,558, indícios
fracos que precisam ser avaliados numa amostra NOVA. Sweep muito profundo
teve AUC estratificado 0,351, mas orientação varia por período; não criar
limiar novo olhando essa amostra.

## Diferenças por contrato

| Moeda | Nº | TP | SL | TIME | R acumulado da carteira selecionada |
|---|---:|---:|---:|---:|---:|
| ENA | 29 | 14 | 13 | 2 | +6,993R |
| ZEC | 23 | 5 | 15 | 3 | -7,703R |
| DOT | 8 | 1 | 4 | 3 | -2,030R |
| HYPE | 8 | 3 | 5 | 0 | -0,882R |
| AVAX | 4 | 0 | 4 | 0 | -4,000R |
| SOL | 4 | 1 | 1 | 2 | +0,978R |
| TAO | 3 | 0 | 1 | 2 | +0,343R |
| ETH | 1 | 1 | 0 | 0 | +1,206R |
| AAVE | 1 | 1 | 0 | 0 | +1,200R |
| BTC | 0 | 0 | 0 | 0 | 0R |

ENA e ZEC representam **52 de 81 operações (64,2%)**. A mistura entre
seus regimes pode explicar associações agregadas de indicadores.

ENA por janela: T +2,465R; U -0,887R; V +2,235R; W +3,180R.
ZEC por janela: T -3,323R; U +0,637R; V -0,017R; W -5,000R.
AVAX teve 4 SLs em 4 exemplos — insuficiente para aprovar veto a esse ativo.

**Não é um backtest válido de ENA-only ou sem ZEC.** Filtrar moedas mudaria
quais oportunidades estariam disponíveis durante os horários vagos e alteraria
o conjunto de operações selecionadas globalmente. Reexecutar a carteira e
testar em dados novos ANTES de qualquer comparação de filtros por moeda.

## Custos: grande fonte de deterioração líquida

Taxa taker hipotética 0,06% + slippage hipotético 0,02% por lado,
total 0,16% de preço em ida e volta. A razão mediana de
custo monetário/risco de preço do stop nos 81 trades foi **21,975%**.
O TP de **1,8R bruto** resultou em média **+1,312R líquido**.
Por contraste, SL já vale -1R normalizado incluindo os custos.

**Sensibilidade matemática das MESMAS 81 entradas selecionadas**:
derivamos o R bruto individual a partir do R líquido original e custo/risco
assumido, e aplicamos novos fatores de custos, sem alterar entrada,
stop, TP, duração ou seleção. Os resultados a seguir **NÃO são backtests
completos**, pois um custo mais baixo também mudaria o filtro inicial
RR>=1,2 e liberaria sinais e posições que não estão nesses 81.

| Múltiplo do custo original | T ROI | U ROI | V ROI | W ROI | 168d composto |
|---|---:|---:|---:|---:|---:|
| 0 (sem custos, irrealista) | +5,500% | -0,089% | +3,087% | +2,928% | +11,842% |
| 0,50 | +2,961% | -0,969% | +0,126% | +0,599% | +2,703% |
| 0,75 | +1,877% | -1,349% | -1,118% | -0,381% | -1,000% |
| 1,00 (atual) | +0,893% | -1,696% | -2,237% | -1,263% | -4,261% |
| 2,00 | -2,286% | -2,829% | -5,777% | -4,056% | -14,164% |

O ponto de equilíbrio retrospectivo do conjunto FIXO ocorre com
~**0,679x** o custo modelado, i.e., ~**32% menos**. Isso não garante
preço de execução real, spread, funding, preenchimento passivo ou
rentabilidade em sinais futuros. Mesmo zerando custos, o período U
continua negativo; **custo não é o único problema**.

## Próximas hipóteses (não executadas, sem alteração de estratégia)

1. Medir taxas reais da conta e spread/slippage da MEXC em paper prospectivo,
   registrar spread no instante do sinal, profundidade do livro, funding,
   tamanho mínimo, efeito da alavancagem e limites de margem. Não supor
   execução maker gratuita ou fill garantido em ordem limite.
2. Se custo real materialmente inferior ao simulado, rerodar o replay
   COMPLETO com custos corrigidos e gate RR>=1,2, carteira global,
   em novas datas, sem escolher cortes pelo passado.
3. Registrar regimes de volatilidade, direção BTC/mercado e força recente
   H1, e verificar se o tipo de contexto prevê o resultado *fora da amostra*.
4. Não habilitar novo filtro “volume>3x”, “ENA-only” ou “sem ZEC” a partir
   deste histórico: essas regras foram sugeridas ao olhar os próprios
   resultados. Primeiro especificar a hipótese e validar em amostra
   prospectiva ou realmente reservada.

**Decisão:** F continua referência relativamente menos prejudicial,
mas NÃO está validada para ordens reais. Sem merge para main.
