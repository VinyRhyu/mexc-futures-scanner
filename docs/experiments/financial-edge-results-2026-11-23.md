# Resultado da auditoria de rentabilidade — 1 e 50 USDT, custos e RR projetado

Data: 23/11/2026. Códigos e dados: [PR #13](https://github.com/VinyRhyu/mexc-futures-scanner/pull/13); [três semanas de diagnóstico, GitHub Actions #45178288485](https://github.com/VinyRhyu/mexc-futures-scanner/actions/runs/45178288485); [dois blocos temporais adicionais, Actions #45178891985](https://github.com/VinyRhyu/mexc-futures-scanner/actions/runs/45178891985). Os cinco jobs de replay concluíram com sucesso, cobertura 24/24 símbolos em cada bloco; testes causais passaram. Universo congelado SHA256 `edf08de9b2c1027c7631069a9b86baa73febd799c56fc8c2edf2274bc82601a1`.

## Descoberta primária

A banca de **1 USDT** não gera a mesma lista de operações que a banca de 50 USDT, porque as restrições do avaliador financeiro alteram quem passa nos filtros de risco, quantidade, margem e faixa.

O critério exploratório de entrada **RR líquido projetado >=1,5** (sem filtro A) pareceu lucrativo nas três semanas previamente conhecidas, mas **NÃO demonstrou lucro positivo nos dois blocos temporais de verificação**.

| Período | Banca 1 USDT, slip 0,02% — BASE | Banca 1 USDT, slip 0,02% — RR >=1,5 | Diferença |
| --- | --- | --- | ---: |
| **Diagnóstico** 31/10–07/11 UTC | 27 trades / −7,1487 R | 4 trades / +2,2839 R | +9,4326 R |
| **Diagnóstico** 07–14/11 UTC | 23 / −1,6836 R | 6 / +5,5490 R | +7,2326 R |
| **Diagnóstico** 15–22/11 UTC | 31 / −3,9819 R | 7 / −2,4301 R | +1,5518 R |
| **Subtotal diagnóstico, carteiras reiniciadas por bloco** | **81 / −12,8141 R** | **17 / +5,4029 R** | **+18,2170 R** |
| **Verificação adicional** 26–31/10 UTC | 14 / −3,9955 R | 4 / +3,0442 R | +7,0397 R |
| **Verificação adicional** 14/11 00h–15/11 20h UTC | 15 / −2,8713 R | 8 / −3,1305 R | −0,2593 R |
| **Subtotal verificação, carteiras reiniciadas por bloco** | **29 / −6,8668 R** | **12 / −0,0864 R** | **+6,7804 R** |

O limiar RR 1,5 preservou apenas **3 operações líquidas positivas das 12 selecionadas** nos dois blocos adicionais. A perda total foi pequena (−0,0864 R), mas **não há evidência suficiente de expectativa positiva**.

## Comparação com custos adversos (slippage por execução)

Cada linha **refaz** a carteira com outro conjunto de entradas elegíveis; não é apenas subtrair custos de trades constantes. Contagens mudam e, portanto, retornos agregados entre níveis de slippage não são comparações pareadas.

| Grupo temporal | Banca | Slippage | BASE trades / R | RR >=1,5 trades / R |
| --- | ---: | ---: | --- | --- |
| Diagnóstico (3 blocos) | 1 USDT | 0,02% | 81 / −12,814 R | 17 / +5,403 R |
| Diagnóstico | 1 USDT | 0,05% | 36 / −3,980 R | 7 / +5,220 R |
| Diagnóstico | 1 USDT | 0,10% | 14 / −5,626 R | **2 / +1,162 R** |
| Verificação (2 blocos) | 1 USDT | 0,02% | 29 / −6,867 R | **12 / −0,086 R** |
| Verificação | 1 USDT | 0,05% | 19 / −3,069 R | 8 / +0,569 R |
| Verificação | 1 USDT | 0,10% | 8 / −0,171 R | **6 / +1,829 R** |
| Diagnóstico | 50 USDT | 0,02% | 79 / −13,169 R | 17 / +0,807 R |
| Diagnóstico | 50 USDT | 0,05% | 33 / −11,329 R | 8 / +0,829 R |
| Diagnóstico | 50 USDT | 0,10% | 8 / −5,567 R | **2 / −2,000 R** |
| Verificação | 50 USDT | 0,02% | 31 / −0,947 R | 13 / +4,273 R |
| Verificação | 50 USDT | 0,05% | 19 / +4,662 R | 8 / +0,569 R |
| Verificação | 50 USDT | 0,10% | 7 / +2,737 R | **5 / −0,337 R** |

**Não classificar stress como prova de robustez**: o volume de operações pode cair a 2 ou 5 por grupo. As mesmas operações BASE foram adicionalmente reprecificadas sob custo adverso e a saída `paired_fixed_baseline_trades` não atribui lucro/prejuízo a operações que perderam viabilidade.

## Diagnóstico operacional

Nos três blocos de diagnóstico com 1 USDT e slip 0,02%, a maioria dos planos técnicos foi financeiramente bloqueada. Motivos predominantes agregados por plano: `RETORNO_RISCO_INSUFICIENTE`, `CUSTO_RELATIVO_ELEVADO`, `PRECO_FORA_DO_PLANO`; `LOTE_MINIMO_OU_META_EXCEDE_RISCO` ocorreu em número menor. Esses códigos são da simulação com book sintético, não restrições de uma conta real confirmada.

O filtro A anterior também foi testado no mesmo replay; não demonstrou consistência e **não** deve ser acoplado automaticamente ao RR1,5 para tentar melhorar retrospectivamente o resultado. A regra de RR >=2,0 tampouco demonstrou vantagem estável. Não procurar novos limiares olhando os mesmos desfechos.

## Decisão técnica

1. **Manter `main`, cronjob.org, Telegram e scanner atual inalterados.** Nenhuma entrada foi enviada à MEXC.
2. **RR 1,5 é uma hipótese para pesquisa, NÃO uma estratégia validada para produção.** O conjunto adicional de 12 trades com 1 USDT e slip base fechou negativo. Não há margem estatística nem regime de mercado suficientemente variado para afirmar ganho futuro.
3. **Prioridade agora: identificar padrões ex-ante de qualidade e testar realisticamente a execução.** Capturar snapshots contemporâneos de ranking top50, spread e livro, medir as verificações de margem/mínimo em 1 USDT, e auditar os fatores de rompimentos bem-sucedidos vs falsos.
4. Usar histórico temporal realmente não aproveitado na escolha de um próximo filtro, preservando a possibilidade de concluir que nenhum novo critério tem edge. Sem histórico confiável fora da amostra, não aprovar mudanças de produção.

## Limitações inegociáveis

- Universo de 24 moedas selecionadas **no dia 23/11**, não ranking top50 efetivamente histórico. A disponibilidade e classificação do mercado foram reconstruídas parcialmente pelo giro M1.
- Spread fixo de 0,02%, taker 0,06% por ponta, slippage hipotético, funding sintético e livro artificialmente profundo. Não há fills pessoais MEXC nem preço executável de mercado historicamente observado.
- Resultados em R são risco normalizado de portfolios de **uma posição por vez reiniciados por bloco**, não ROI alavancado, lucro efetivamente recebido nem evolução contínua da banca.
- Os blocos adicionais não foram usados para escolher a hipótese RR1,5, mas já houve pesquisa prévia do modelo M1 e do filtro A sobre parte desses dados. São comparação temporal complementar, não blind test total do desenvolvimento.
