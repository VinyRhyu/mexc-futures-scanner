# Resultado: 35% de ROI sobre margem MEXC, comparando 10x, 15x e 20x

Data: 23/11/2026. [PR #17](https://github.com/VinyRhyu/mexc-futures-scanner/pull/17) em rascunho, **sem merge**. Execução [GitHub Actions #45290434937](https://github.com/VinyRhyu/mexc-futures-scanner/actions/runs/45290434937): **SUCCESS**, 32 testes aprovados, incl. verificação do resultado anterior. Artefatos `roi35_leverage_results.json` e `roi35_margin_ledger.csv` com trades, margem, ROI projetado e realizado, saldo e bloqueios.

## Exatamente o que está sendo medido

A MEXC denomina `ROI = PNL / Margem inicial`; com a posição ainda aberta, é PNL **não realizado** ao preço justo. Este experimento usa `PNL líquido realizado após fees/slippage do modelo / margem inicial simulada × 100`, para representar a rentabilidade de operação **encerrada**. Isso não equivale literalmente ao indicador da posição aberta no aplicativo. Sem histórico de funding/fees pessoais, o ROI continua hipotético.

Todas as seis carteiras: banca paper 1 USDT inicial, capital composto sem reset entre os cinco blocos de 26/10 a 22/11/2026, 24 moedas congeladas, RR líquido projetado >=1,5, risco por operação até 10% da banca, desfecho conservador OHLC até 4h, custo-base do modelo (slippage 0,02% por ponta, taker 0,06% por ponta), uma posição por vez, alavancagem **exatamente** 10x/15x/20x revalidada na `finance.evaluate`, contrato, margem e buffer de liquidação.

O cenário com filtro de ROI exige na abertura `gain_usdt_projected_to_TP / initial_margin >=35%`; não olha desfecho futuro e não garante que o preço alcance TP.

## Resultado com mesmo histórico e mesmo cenário de custos

| Alavancagem fixa | Gate ROI líquido >=35% projetado ao TP? | Trades | Positivas | Positivas fechadas ROI >=35% | Saldo final 1 USDT paper | Retorno total de banca | DD máximo % pico |
|---|---|---:|---:|---:|---:|---:|---:|
| 10x | Não | 18 | 7 | 1/7 | 1,1512 USDT | +15,12% | 34,73% |
| 10x | Sim | 1 | 1 | 0/1 | 1,0102 USDT | +1,02% | 0%* |
| 15x | Não | 27 | 9 | 3/9 | 0,9409 USDT | −5,91% | 38,75% |
| **15x** | **Sim** | **12** | **5** | **3/5** | **1,1875 USDT** | **+18,75%** | **32,33%** |
| 20x | Não | 27 | 9 | 6/9 | 0,9409 USDT | −5,91% | 38,75% |
| **20x** | **Sim** | **17** | **7** | **5/7** | **1,1856 USDT** | **+18,56%** | **41,75%** |

* A carteira 10x com gate teve apenas **uma operação**. Não interpretar drawdown 0% como estratégia segura.

Para checar o modelo anterior: com alavancagem 15x ou 20x sem o gate de ROI, as **mesmas 27 entradas** foram selecionadas e o saldo final foi exatamente `0.9408652174548 USDT`, reproduzindo o PR #16. Apesar de 20x aumentar ROI percentual, **não aumentou lucro líquido em USDT** quando o tamanho dos contratos, o stop, o alvo e a seleção permaneceram os mesmos.

### Por que um filtro de ROI potencial >=35% não garante 35% realizado

O desfecho ao TP tem rentabilidade suficiente em exemplos reais deste replay:

| Alavancagem | Trades que realmente bateram TP com ROI líquido >=35% | Outros trades positivos, mas abaixo de 35% |
|---|---|---|
| 10x+gate | Nenhum | SUI, saída por tempo em 4h, ROI **+1,78%** sobre a margem, apesar de TP projetado +37,9% |
| 15x+gate | INJ (+36,2%), LINK (+49,1%), AAVE (+56,7%) | ONDO (+2,9%), LINK (+2,1%), ambos por tempo |
| 20x+gate | INJ (+48,2%), LINK (+65,5%), NEAR (+46,6%), AAVE (+75,7%), ZEC (+42,2%) | ONDO (+3,8%), LINK (+2,8%), ambos por tempo |

Os números das posições são hipóteses de execução do modelo. Todos os stops ainda geram prejuízo. Em 20x + gate, **10 de 17 operações** não encerraram positivas e o drawdown chegou a **41,75%** do pico da banca: ROI por trade não é retorno sobre saldo e não demonstra rentabilidade consistente.

### Interpretação, riscos e decisão

1. **35% de retorno na posição é uma meta tecnicamente alcançável quando o preço atinge o TP**, e 15x/20x a viabilizam em algumas entradas históricas. A regra de abertura só consegue garantir **potencial de ganho**, não ganho realizado.
2. **Alavancagem maior altera o denominador (margem)**. Mantidos notional e movimentos do preço, **não aumenta o P&L em USDT**. Pode permitir ou vetar diferentes ordens por margem e distância de liquidação; por isso cada cenário é carteira simulada separada.
3. As carteiras com filtro de ROI>=35% mostram +18,75% e +18,56% de retorno sobre a banca nos dados retrospectivos, mas seus **drawdowns são elevados**, sua frequência é baixa e os períodos foram usados para elaborar outras regras. **Não há validação independente**.
4. **Não autorizar alteração do scanner**, ampliação de alavancagem, aumento de risco, remoção de stops, ordens reais ou metas automáticas. 10x/15x/20x são variantes fixas apenas do teste, sendo 20x o limite já configurado.
5. Próxima fase científica deve comparar **os mesmos trade IDs e notionals** em cenários de alavancagem, verificar quais bloqueios mudaram por margem/liquidação, e testar entradas com ROI potencial >=35% em novo período independente com histórico contemporâneo de contrato/ranking/fees/funding/orderbook. Não ajustar filtros lendo o mesmo histórico.

O código permanece apenas na branch `research/roi35-margin-leverage-20261123`, PR #17 em draft. **Produção intacta**: `main`, `scan.yml`, Telegram, cronjob.org, capital paper e alavancagem operacional sem alterações.
