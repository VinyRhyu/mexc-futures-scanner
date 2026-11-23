# Teste temporal adicional — RR líquido mínimo 1,5 (não otimizado)

Especificado em 23/11/2026 **depois de observar os três blocos de diagnóstico financeiro** e **antes de calcular os resultados destes dois blocos adicionais**.

## Hipótese única e imutável

A regra candidata é **somente** exigir `net_rr >= 1.5` projetado pelo `finance.evaluate` na cotação hipotética da primeira abertura M1 após a confirmação, com TP/SL técnico original, custos e riscos originais. **Não** adicionar filtro A, nem mudar limiar, stop, target, contratos ou método de carteira após os resultados. Comparar com BASE (`net_rr >= 1`, regra original).

Reproduzir nas **duas bancas paper 1 USDT e 50 USDT**, com **slippage 0,02%, 0,05% e 0,10% por ponta**, com taxa taker hipotética 0,06% por ponta, spread sintético 0,02% e livro sintético infinito (não representam custos executados). Recalcular inteiramente a carteira sequencial de uma posição por vez por cenário.

## Dois blocos adicionais UTC, final exclusivo

| Bloco | Início | Fim | Duração |
| --- | --- | --- | --- |
| H4 | 2026-10-26T00:00:00Z | 2026-10-31T00:00:00Z | 5 dias |
| H5 | 2026-11-14T00:00:00Z | 2026-11-15T20:00:00Z | 44 horas |

Não houve análise do limiar RR 1,5 nos dois blocos antes de escolhê-los. Porém, o modelo M1, e o teste A sobre o intervalo H5 e ativos de baixo giro, já foram investigados; **não** são períodos totalmente cegos para o projeto.

Conservar rigorosamente o mesmo universo congelado de 24 ativos, SHA256 `edf08de9b2c1027c7631069a9b86baa73febd799c56fc8c2edf2274bc82601a1`, e o critério de giro histórico >=5 milhões USDT no sinal. **Requer 24/24 símbolos completos, sem lacunas M1/M15/H1**. Se falhar retenção MEXC, marcar o período **INCONCLUSIVO**; não mover a janela outra vez nem substituir moeda para melhorar resultado.

## Medidas e decisão

Registrar por bloco e cenário: trade count, wins, net R total/médio, drawdown, taxa de bloqueios e motivos, operações substitutas por liberação de slot, sensibilidade ao custo, **quantos vencedores BASE foram vetados**. RR 1,5 positivo agregado com poucos trades não comprova expectativa positiva futura. Comparar a consistência por bloco e saldo, não apenas o ganho agregado ou taxa de acerto.

Não promover para `main` neste estudo. Ainda faltam quotes reais, spreads, livro/fill e top50 historicamente contemporâneo. O objetivo é rejeitar ou manter a hipótese para investigação posterior, não forçar lucro.
