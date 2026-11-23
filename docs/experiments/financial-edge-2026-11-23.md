# Pesquisa: viabilidade e lucro líquido por operação — 23/11/2026

## Objetivo

Investigar o que realmente pode **aumentar o lucro líquido das operações**, não simplesmente a quantidade de sinais ou a taxa de acerto. Continuar com o modelo M1 e as regras da produção congeladas; sem alterar `main`, cronjob.org, alertas, estado ou qualquer ordem.

### Universos e períodos pré-fixados

Reusar **exatamente as mesmas 24 moedas e a mesma ordem** congeladas em 23/11/2026 12:33:54 UTC na pesquisa `expanded-production-eligible-20261123`. Hash do snapshot: `edf08de9b2c1027c7631069a9b86baa73febd799c56fc8c2edf2274bc82601a1`.

Arquivo auditável `docs/experiments/frozen-finance-universe-2026-11-23.json`; **nenhum recálculo atual do top50 entre períodos**. A seleção de contratos de novembro é retroativa aos eventos de outubro, com viés de sobrevivência e sem prova do ranking histórico, mas o **giro 24h mínimo de 5.000.000 USDT no instante histórico** foi reconstruído com 1440 M1 anteriores.

Janelas UTC, limite final exclusivo:
1. 31/10 00h até 07/11 00h (7 dias)
2. 07/11 00h até 14/11 00h (7 dias)
3. 15/11 20h até 22/11 20h (7 dias)

**Esses períodos já foram utilizados na pesquisa anterior do filtro A.** O presente estudo é um **diagnóstico retrospectivo financeiro**, não uma validação out-of-sample independente. Nenhum limiar novo pode ser aprovado a partir dele sem novo bloco temporal.

## Comparações congeladas antes de olhar os resultados da nova simulação

**Banca paper fixa por operação**: 1 USDT (como na configuração `main`) versus 50 USDT (como nas simulações anteriores). Com a mesma quantidade de sinais, replay M1, stop, TP, bandas e modelo de `finance.evaluate`.

Para cada saldo, slippage por execução **0,02%, 0,05%, 0,10%**, mantendo spread sintético total 0,02%, taxa taker assumida 0,06% por ponta, e livro sintético infinito (sem profundidade real). As taxas pessoais ainda não foram verificadas. O funding sintético é zero, sujeito a taxas reais futuras.

**Critérios exploratórios de melhoria por lucratividade projetada**: antes de saber o desfecho, avaliar apenas oportunidades com `net_rr` previsto pelo validador financeiro na abertura do próximo M1 de pelo menos **1,5** ou **2,0**, comparando com `minimum_rr=1` original. Esses limiares não foram otimizados e não alteram o target/stop; podem **remover trades vencedores**. Testar com e sem filtro A (que permanece não validado). O índice RR é observado na simulação de cotação no próximo minuto; não é informação disponível no fechamento da confirmação, e a implementação ao vivo exigiria uma cotação fresca **na hora da entrada**, nunca usar preços futuros.

**Medição:** separação explícita de sinais técnicos, financeiramente bloqueados, não preenchidos por faixa e preenchimentos simulados. Deduplicar planos pelo trio `symbol,side,signal_at` usando plano lexicograficamente primeiro **entre os financeiramente viáveis no cenário**, sem consultar seu resultado. Portfolio de **uma posição por vez é refeito integralmente** por cenário. Comparar também as **mesmas operações BASE** sob slippage adverso, distinguindo operações inviáveis de operações perdedoras (não imputar 0 R nem −1R aos bloqueios).

**Resultados exigidos:** número de operações e vitórias líquidas, total e média R líquido, drawdown realizado, P&L USDT fixo sintético não-composto, status de elegibilidade e motivos bloqueados por cenário, diferenças 1/50 USDT, vetos de sinais vencedores, e testes de regressão para ausência de lookahead.

## Critérios de aprovação

1. Relatório confiável com pelo menos 20/24 ativos completos e, nesta rodada, **falhar se qualquer um estiver incompleto**.
2. Sem desviar do risco/stop/custo real; nenhuma operação real executada, spreads e fills simulados e por isso resultados são apenas estimativas.
3. **Expectativa líquida positiva** precisa ser observada em múltiplas janelas, com custos adversos realistas, lucro dependente de número suficiente de trades e sem depender de apenas uma semana.
4. Para o próximo teste independente: coletar snapshots completos históricos (top50, livro, fees/quantidade) ou bloquear uma janela temporal *não utilizada na escolha de parâmetros*. Só então considerar incorporar um novo filtro.
5. Se a banca paper de 1 USDT não conseguir cumprir mínimos, limites de risco ou alavancagem com consistência, registrar **inviabilidade**, não sugerir aumentar automaticamente a alavancagem nem considerar os trades de 50 USDT como viáveis em 1 USDT.

## Escopo de segurança

Pesquisa inteiramente read-only em branch rascunho. `main` segue com `mode=paper`, `initial_balance=1`, `minimum_turnover=5000000`, `scan.yml` e Telegram originais. Nenhuma modificação de produção foi autorizada ou aplicada por este experimento.
