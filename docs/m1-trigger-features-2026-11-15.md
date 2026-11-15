# Características do gatilho e filtro de progressão do segundo M1

**O filtro simétrico de progressão foi rejeitado pelo critério registrado.** O fator de lucro aumentou, mas o retorno total normalizado caiu e o efeito variou entre semanas e direções.

## Dados e regra

Mesmas 123 entradas M1 hipotéticas da captura de 25/10 a 07/11/2026, com critérios financeiros atuais, níveis, quantidade, horário de entrada e custos preservados. A primeira semana contém 66 entradas; a segunda 57, separadas pelo horário de confirmação em 01/11/2026 00h de Brasília. Ambas já haviam sido examinadas em outras hipóteses. Não é holdout independente.

Antes de produzir estas estatísticas, foi fixada a única regra candidata: LONG só passa se o segundo M1 fecha no mínimo no preço do primeiro; SHORT só passa se fecha no máximo no preço do primeiro. Igualdade aceita. Não há terceiro candle, mudança de TP/SL, saída dinâmica, ajuste de limite por desempenho ou redistribuição do orçamento rejeitado.

## Diagnóstico da primeira semana

As características usam somente candles fechados antes da entrada. ATR e limite rompido são os valores já conhecidos na formação original. Volume relativo usa os 20 minutos anteriores ao primeiro M1, excluindo os dois gatilhos da referência.

| Característica | Mediana dos 28 TPs | Mediana dos 37 SLs |
|---|---:|---:|
| Avanço favorável do segundo fechamento / ATR | 0.0084 | 0.0228 |
| Corpo favorável do segundo M1 / ATR | 0.0084 | 0.0228 |
| Posição do fechamento na amplitude, 0 a 1 favorável | 0.5192 | 0.6250 |
| Distância do fechamento à borda / ATR | 0.2490 | 0.2106 |
| Volume médio dos dois gatilhos / média anterior | 1.2952 | 1.4369 |
| Volume segundo / primeiro | 1.1754 | 1.6511 |

As distribuições se sobrepõem. Nesta primeira semana, os stops inclusive apresentaram medianas maiores de avanço, posição favorável do fechamento e volume relativo. Isso não prova que volume ou força de fechamento causem perdas, nem justifica inverter esses indicadores. O corpo e o avanço são iguais nesta captura quando a abertura do segundo minuto coincide com o fechamento do primeiro; não são duas evidências independentes.

## Resultado do filtro geral

| Período | Entradas sem→com filtro | TP sem→com | SL sem→com | R com marcação sem→com | Fator de lucro sem→com |
|---|---:|---:|---:|---:|---:|
| Total | 123 → 79 | 49 → 33 | 71 → 43 | +17.668R → +16.237R | 1.229 → 1.345 |
| Primeira semana | 66 → 43 | 28 → 18 | 37 → 24 | +15.826R → +8.967R | 1.405 → 1.338 |
| Segunda semana | 57 → 36 | 21 → 15 | 34 → 19 | +1.842R → +7.270R | 1.038 → 1.355 |

No total, a taxa de TP entre encerradas passou de 40,83% para 43,42%. Foram retirados 28 stops e 16 TPs. As três posições abertas permaneceram na amostra. A soma das encerradas caiu de +16,283R para +14,852R; incluindo a marcação em 4h das abertas, caiu de +17,668R para +16,237R. As operações rejeitadas ainda somavam +1,431R.

Critério registrado: melhorar retorno marcado e fator de lucro no total, não piorar retorno em nenhuma das duas semanas e manter pelo menos 20 entradas na segunda. O filtro geral falhou, sobretudo na primeira semana. Não foi promovido apesar do fator de lucro maior.

## Diferença por direção: origem de uma hipótese posterior

| Direção | Rejeitadas | TP rejeitados | SL rejeitados | R das rejeitadas |
|---|---:|---:|---:|---:|
| LONG | 24 | 12 | 12 | +12.405R |
| SHORT | 20 | 4 | 16 | -10.974R |

O filtro descartava LONGs lucrativos e SHORTs com saldo negativo. **Isso é um achado posterior à análise dos resultados**, não valida aplicar a regra somente em SHORTs. Essa hipótese específica foi congelada separadamente e foi avaliada no período seguinte, de 08/11 a 14/11. A comparação parcial dos 29 ativos completos também rejeitou a regra; veja [o relatório da nova semana](m1-short-progress-validation-2026-11-15.md). Não foi escolhido outro período de EMA, limite de volume, janela ou threshold de progressão.

## Verificações e limites

- Três testes direcionados passaram: simetria/igualdade da regra, impossibilidade de futuros preços e volumes alterarem as características, e exclusão dos gatilhos da referência de volume.
- As 123 referências foram reconciliadas com o replay anterior. Houve 123 verificações de prefixo temporal; nenhum candle posterior à confirmação é necessário para calcular a regra.
- Entrada imediata hipotética, taxa 0,06% por execução, modelo original de spread/slippage, funding zero, contratos congelados e livro sintético. Não simula latência real nem liquidações Fair M1.
- R é risco inicial normalizado, não ROI da carteira de US$ 100. Sinais simultâneos e correlacionados não compartilham capital nesta análise; descartados contam como orçamento ocioso, sem redistribuição.
- Existem 123 entradas, mas 102 combinações distintas de ativo/lado/minuto. Amostra curta e reutilizada, com viés de sobrevivência dos 31 ativos.
- Código e resultados somente na branch de auditoria. Bot, Telegram e ordens reais não alterados.

Fonte: [coleta 42879077420](https://github.com/VinyRhyu/mexc-futures-scanner/actions/runs/42879077420). Protocolo e resultados completos no JSON adjacente e em `config/audit-m1-trigger-features-2026-11-15.json`.
