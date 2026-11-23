# Resultado — universo ampliado de moedas elegíveis (BASE versus filtro A)

Data: 23/11/2026. Evidências: [GitHub Actions #45175484608](https://github.com/VinyRhyu/mexc-futures-scanner/actions/runs/45175484608) (todos os 4 jobs SUCCESS) e [PR #12](https://github.com/VinyRhyu/mexc-futures-scanner/pull/12). JSONs, portfólios BASE e A, CSV de entradas viáveis únicas e snapshot congelado estão arquivados nos quatro artifacts do workflow.

## Universo, congelamento e cobertura

- A MEXC retornou em pré-teste **24** símbolos elegíveis pela seleção **atual** do scanner (allowlist, contrato perpétuo USDT, ticker com 24h >=5 milhões USDT, até top50). O corte inicial de 35 símbolos impediu a primeira execução **antes de haver backtest**. Com motivo documentado, reduziu-se o mínimo de cobertura para **20 ativos**, não o piso de giro nem a estratégia.
- Snapshot imutável congelado em **2026-11-23T12:33:54Z**: SHA256 `edf08de9b2c1027c7631069a9b86baa73febd799c56fc8c2edf2274bc82601a1`.
- Lista: BTC, ZEC, ETH, SOL, XRP, DOGE, QNT, TAO, PEPE, HYPE, SUI, NEAR, LINK, WLD, XLM, AAVE, ENA, INJ, ADA, AVAX, UNI, ARB, ONDO e TIA.
- **24/24** símbolos com histórico M1, M15 e H1 íntegro em cada um dos três períodos, sem exclusões e sem falhas de OHLC M1/M15.
- **Limitação:** o conjunto reflete a elegibilidade **em 23/11**, não necessariamente o top50 de 31/10 a 22/11. Em cada entrada o **giro histórico de 24h de USDT** foi efetivamente recalculado e exigido >=5 milhões. Ainda falta ranking de todo o mercado, histórico de livro, taxa/funding e regras históricas dos contratos.

## Resultado do portfólio com uma posição por vez

A versão A mantém a regra congelada de **extensão direcional >=2 ATR(14) M15 nas quatro horas anteriores à confirmação M1**. TP/SL técnicos e custos hipotéticos BASE são idênticos entre as versões. Planos duplicados com mesmo símbolo, direção e minuto foram reduzidos a um `plan_id` determinístico antes de calcular o portfólio.

| Período UTC, final exclusivo | BASE ops / positivas | BASE R líquido | A ops / positivas | A R líquido | Delta A−BASE |
| --- | ---: | ---: | ---: | ---: | ---: |
| 31/10–07/11 | 19 / 6 | −3,8767 | 14 / 4 | −4,0087 | **−0,1320** |
| 07/11–14/11 | 30 / 9 | −6,7410 | 19 / 9 | +4,3188 | **+11,0598** |
| 15/11 20h–22/11 20h | 30 / 12 | −2,5508 | 22 / 9 | −2,7224 | **−0,1716** |
| **Soma descritiva, reinício por bloco** | **79 / 27** | **−13,1685** | **55 / 22** | **−2,4123** | **+10,7562** |

**Interpretação:** A reduziu a perda combinada, mas **piorou em duas das três semanas**. O ganho ocorre inteiramente no bloco 07–14/11 e não pode ser apresentado como melhora estável, expectativa positiva ou prova de lucro. A e BASE somadas continuam negativas em R nas três janelas.

## Cobertura de sinais e duplicações

| Período | Sinais técnicos | Sinais com giro histórico >=5M | Planos de fill base | Eventos viáveis distintos | Trades carteira BASE |
| --- | ---: | ---: | ---: | ---: | ---: |
| 31/10–07/11 | 639 | 639 | 33 | 27 | 19 |
| 07/11–14/11 | 592 | 592 | 64 | 58 | 30 |
| 15/11–22/11 | 633 | 613 | 75 | 62 | 30 |
| **Total** | **1.864** | **1.844** | **172** | **147** | **79** |

Sinais confirmados ≠ fill financeiro estimado ≠ operação efetivamente executada. Todos os resultados são simulações OHLC.

## Operações vetadas e substituídas

- 31/10–07/11: A retirou 5 trades BASE, **dois alvos positivos** (LINK LONG +1,43R, ZEC LONG +1,70R) e três stops. Nenhum novo trade entrou após liberação de slot; resultado piorou −0,13R.
- 07–14/11: A retirou 13 trades BASE (12 stops e 1 alvo de ENA SHORT +1,51R), e permitiu duas substituições (ENA SHORT alvo +1,57R, XRP LONG stop −1R). O delta líquido foi +11,06R, grande e **concentrado neste período**.
- 15–22/11: A retirou 9 trades BASE (6 stops e **3 alvos positivos**, ZEC SHORT +2,34R, HYPE SHORT +1,22R, BTC SHORT +1,61R); uma substituição TAO LONG parou em −1R. Resultado piorou −0,17R.
- No período 15–22/11, a escolha de **vencedoras vetadas** é especialmente importante para entender por que o filtro A é perigoso quando a tendência se prolonga.

## Sensibilidade aos custos (hipótese adversa)

Ao elevar **slippage assumido de 0,02% para 0,10% por ponta**, a própria lógica financeira do projeto deixa passar:
- **somente 5 das 79** operações do portfólio BASE ao reavaliar os mesmos planos sob stress;
- **somente 3 das 55** operações do portfólio A.

Isso **não** significa que as demais teriam dado prejuízo caso executadas, mas que **não são viáveis segundo o modelo financeiro sob esses custos**. Os poucos sobreviventes ao stress resultaram em netR −1 cada nesta simulação emparelhada. Comparar médias de stress de **subconjuntos diferentes** seria incorreto. Esse teste indica forte fragilidade da exequibilidade, mesmo antes da discussão sobre lucratividade.

## Conclusão técnica

**NÃO incorporar A à produção.** O filtro não entregou melhora uniforme, e a viabilidade a custos adversos é extremamente limitada. O resultado combinado de −13,17R para −2,41R é melhoria retrospectiva, mas não demonstra expectativa positiva.

**Próximos passos científicos:** validar contas/contratos reais do modo paper com 1 USDT (o teste atual usou 50 USDT fictícios), diferenciar spread, funding e slippage entre moedas/regimes, e construir um arquivo histórico próprio de snapshots do **universo top50 contemporâneo**, para evitar viés de sobrevivência e permitir testes futuros verdadeiramente causais. Avaliar contexto e origem de rompimentos, não escolher limiares novos vendo os mesmos resultados.

**Não foram modificados** `main`, `engine.py`, `scan.yml`, regra de 5M, Telegram, cronjob.org, ordens ou `scanner-state`.
