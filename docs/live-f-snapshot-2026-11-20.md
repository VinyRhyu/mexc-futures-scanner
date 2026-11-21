# Observação F SHORT ao vivo — MEXC Futures, 20/11/2026

**Somente pesquisa, sem execução de ordens e sem envio Telegram.**
Modelo: F_sweep_rejection M5/H1, inalterado (scripts/audit_confluence_v3.py).
O ROI histórico do modelo F foi negativo: aproximadamente -5,11% composto
em três janelas de 42 dias, com risco simulado de 1% por operação.

## Coleta verificável

GitHub Actions: https://github.com/VinyRhyu/mexc-futures-scanner/actions/runs/44755535858

- Horário de consulta à MEXC (server time): 2026-11-20T14:39:29Z (11h39 Brasília).
- Último M5 **fechado** considerado: 2026-11-20T14:35:00Z (11h35 Brasília).
- Último H1 fechado considerado: 2026-11-20T14:00:00Z.
- Exclusivamente perps USDT negociáveis, sem BTC e tokens estáveis/fiat, exigindo
  volume financeiro 24h >=2.000.000 USDT.
- 60 contratos habilitados e líquidos, 59 analisados integralmente,
  1 sem histórico H1 mínimo (DCTY_USDT).
- Resultado: **0** novas rejeições F no último M5 fechado;
  **4** setups F anteriores (SOL 11h30, RARE 11h30, ARB 11h10,
  VVV 11h15); **1** WATCH (HBAR); 54 sem padrão.

## Único WATCH no candle M5 fechado de 11h35

- HBAR_USDT: close 0.05330; referência de resistência 0.05353,
  vol relativo M5 1,325 (<1,5 exigido), H1 abaixo EMA20.
  **Observação, não gatilho confirmado, nem entrada.**

## Estudo pontual do fechamento anterior de 11h30

Primeira coleta https://github.com/VinyRhyu/mexc-futures-scanner/actions/runs/44754420485
detectou 2 padrões gráficos F (de 69 históricos íntegros):

- SOL_USDT: referência de close 71,55, stop 71,71614286,
  alvo hipotético 71,250943. RR líquido ex ante **0,658**, portanto
  não atinge o filtro financeiro mínimo de 1,2.
- RARE_USDT: referência 0,01217, stop 0,01241964,
  alvo hipotético 0,011720648. RR líquido ex ante ~1,597, antes de
  spread específico, funding, lotes e slippage real. Distância ao stop
  ~2,05% do preço subjacente.

No M5 seguinte fechado às 11h35, SOL fechou 71,04 (abaixo do alvo
hipotético de fechamento anterior) e RARE fechou 0,01274 (acima do stop
hipotético). Isso NÃO comprova execução em TP/SL ou ordem real, e não permite
conhecer ordem intrabar de toques apenas pelos fechamentos.

## Limite de uma varredura sem filtro de liquidez

Tentativa experimental https://github.com/VinyRhyu/mexc-futures-scanner/actions/runs/44755015622
consultou contratos de diversas classes, incluindo ativos sintéticos/ações,
e teve 921 erros de API (código 510, excesso de requisições), de 1086
symbols USDT considerados. **Não constitui uma varredura completa**, e não
permite afirmar ausência de oportunidades nesses 921 símbolos.

O filtro de liquidez, além de proteger contra slippage, evita dezenas de
solicitações para mercados em que uma simulação de preenchimento não teria
credibilidade. Novo acesso a todos contratos exigiria amostragem em batches
rate-limited e classificação explícita do tipo de instrumento.

### Decisão

Não houve sinal F novo confirmado no último fechamento observado (11h35).
Não habilitar entrada automática nem notificar como sinal operável.
O dado é histórico e fica vencido após novos candles. O scanner main está
inalterado, e a PR permanece experimental.
