# Hipóteses congeladas — Confluência SHORT H1/M5 v2

Registrado antes da execução dos experimentos comparativos. Não alterar critérios
em resposta ao resultado até nova rodada de pesquisa explicitamente separada.

## Diagnóstico anterior

Em 42 dias (09/10–20/11/2026), 10 contratos: 524 sinais, 78 TP, 104 SL,
342 saídas por tempo. Carteira de uma posição simultânea, 271 operações,
-21,156% com 1% do patrimônio em risco por entrada, máximo drawdown 24,026%.
Baseline usa taxas teóricas taker 0,06% e slippage 0,02% por lado.

## Hipóteses A/B/C/D

**Todas as versões preservam** entrada técnica H1/M5, stop, TP, custos,
relação retorno/risco e timeout da baseline; só adicionam filtros ex ante.

- **B: H4 alinhado:** último H4 fechado com fechamento abaixo EMA20 H4 e EMA20 em declínio entre dois H4 fechados.
- **C: BTC alinhado:** último H1 de BTC_USDT fechado com fechamento abaixo da EMA20 H1.
- **D: B + C:** ambos os filtros, sem flexibilizar qualquer requisito.
- **E: Qualidade de volume:** volume financeiro do M5 de confirmação >=2x mediana dos 12 M5 anteriores e TR do M5 entre 0,75x e 2x ATR14 M5 anterior.
- **A: Baseline:** mesmas condições anteriores, sem filtro adicional.

H4 agregado de H1 de UTC em blocos de quatro H1; H4 só vale após completar
quatro horas, e só dados fechados disponíveis no instante da decisão são usados.
Usar BTC do mesmo provedor MEXC, não preço externo. Qualquer ausência ou falha
de dados bloqueia o filtro, não libera entrada.

## Protocolo

- Exatamente 10 pares: TAO, SOL, AVAX, ENA, DOT, ZEC, HYPE, AAVE, BTC, ETH.
- Dados MEXC M5/H1 completos, 42 dias em duas janelas de 21 dias:
  2026-10-09 11:00 UTC até 2026-10-30 11:00 UTC; e até 2026-11-20 11:00 UTC.
- Pré-entrada não enxerga futuros (sinal em candle M5 fechado, próxima abertura
  somente para simulação de execução), sem varrer manualmente resultados.
- Sem posição simultânea. Em sinais concorrentes priorizar maior volume relativo
  registrado no momento do sinal. Simular risco de 1% por entrada como métrica
  comparativa, não prescrição de risco real; detalhes MEXC e lotes não validados.
- Medir quantidade, TP, SL, TIME, soma de R líquido, ROI composto e drawdown,
  por janela e no período combinado, além de retenção do caso TAO.
- Critérios exploratórios de avanço: ROI líquido positivo em **ambos** os períodos,
  máximo drawdown <=10% nos 42 dias, pelo menos 30 operações selecionadas na
  carteira, média <=3 operações/dia, bater baseline. Mesmo se passar, ainda
  exigirá teste **prospectivo** em paper, já que o histórico foi observado.
- Não ativar Telegram, não alterar main e não executar ordens.

Para reduzir múltiplas comparações, **não** testar grades de dezenas de
combinações nem trocar limiares até aparecer um lucro. Somente as cinco
variantes acima são autorizadas neste experimento.
