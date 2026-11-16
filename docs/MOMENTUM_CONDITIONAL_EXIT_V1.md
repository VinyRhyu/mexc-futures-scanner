# Saída condicional por fraqueza — hipótese rejeitada

A regra testada reduziu o retorno histórico da carteira de risco fixo de 1%, de **20,39% para 17,90%** em 184 dias. Com custos agravados, caiu de **14,22% para 13,26%**. No período recente, transformou +4,19% em −1,35%. Portanto, esta hipótese não deve substituir a saída de 24 horas.

O protocolo foi publicado **antes da avaliação**, no commit [bc19d8c](https://github.com/VinyRhyu/mexc-futures-scanner/commit/bc19d8c56d8d83a9be33beb9255482b5c19290d0). Foi executado um único candidato, sem busca de parâmetros após observar os resultados. A pesquisa é retrospectiva: os dados históricos já foram examinados no desenvolvimento anterior e não constituem validação independente.

## Regra congelada

Depois de pelo menos seis horas desde a entrada, observar dois fechamentos H1 consecutivos contra a EMA20: abaixo para LONG, acima para SHORT. A estimativa de resultado líquido no último fechamento precisa ser menor ou igual a zero, incluindo taxas, spread, slippage e funding já liquidado. A igualdade entre preço e EMA não conta como fraqueza.

O sinal usa apenas candles que terminaram até uma hora antes da execução. A primeira saída possível ocorre sete horas após a entrada, na abertura H1 seguinte ao atraso. Os dois candles precisam começar após a entrada. A EMA usa cálculo recursivo Decimal, iniciado no primeiro fechamento da fonte congelada de 1º de maio, com ao menos 20 observações. O stop continua ativo durante a espera; gaps de stop ou liquidação têm prioridade sobre a saída eletiva. Não se usa a máxima/mínima da hora futura nem se cancela o sinal com base no preço futuro de abertura.

Universo de 26 ativos, entradas diárias, ranking, filtro BTC7, uma posição simultânea, risco fixo de 1% incluindo custos, alavancagem modelada de 10x, stops e prazo máximo de 24h permaneceram iguais. A liberação antecipada do saldo não cria entradas intradiárias adicionais. Cada carteira foi inteiramente recalculada, incluindo efeito do saldo sobre o lote e a seleção futura.

## Comparação completa

Intervalos de dados em UTC, início inclusivo e fim exclusivo; a data final do contínuo corresponde a 15/11 às 21h em Brasília. Todos os retornos são líquidos dos custos modelados. Cada bloco isolado começa com US$ 100; o contínuo mantém a mesma carteira ao longo de todo o período. Os intervalos se sobrepõem e não são amostras independentes.

| Período | 24h, base | Condicional, base | 24h, custos agravados | Condicional, custos agravados |
|---|---:|---:|---:|---:|
| 16/05–01/07 (46 dias) | +0,63% | +0,82% | −0,53% | −0,29% |
| 01/07–01/10 (92 dias) | +17,15% | +24,63% | +14,70% | +21,64% |
| 24/10–16/11 (23 dias) | +4,19% | **−1,35%** | +3,59% | **−1,46%** |
| Contínuo, 16/05–16/11 (184 dias) | **+20,39%** | **+17,90%** | **+14,22%** | **+13,26%** |

| Contínuo, 184 operações por carteira | 24h, base | Condicional, base | 24h, agravados | Condicional, agravados |
|---|---:|---:|---:|---:|
| Saldo final, início US$ 100 | US$ 120,39 | US$ 117,90 | US$ 114,22 | US$ 113,26 |
| Drawdown máximo nas marcações H1 | 9,64% | 9,08% | 10,62% | 9,61% |
| Operações positivas | 83 | 58 | 83 | 57 |
| Tempo médio por operação | 21,50h | 14,42h | 21,50h | 14,32h |
| Taxas de negociação | US$ 4,30 | US$ 4,41 | US$ 6,80 | US$ 6,99 |
| Funding líquido pago | US$ 0,107 | US$ 0,072 | US$ 0,111 | US$ 0,072 |
| Liquidações modeladas | 0 | 0 | 0 | 0 |

A redução de exposição não melhorou o ROI. Também não eliminou meses negativos: no contínuo base, outubro passou de −0,66% para −6,59%. Os custos agravados usam taxa de 0,10% por lado, spread total de 0,04% e slippage de 0,04%; a base usa 0,06%, 0,02% e 0,02%, respectivamente, com mínimo de dois ticks na derrapagem.

## Por que não passou

No contínuo base, 183 entradas tiveram o mesmo ativo, horário e direção; uma entrada mudou devido ao efeito do saldo sobre os lotes elegíveis. Entre os 114 pares com saída diferente, a regra melhorou 57 operações originalmente negativas e piorou outras 23, mas também cortou **27 operações que terminariam positivas**. Essa identificação serve apenas para diagnóstico retrospectivo: não permite saber antecipadamente quais operações se recuperariam. A comparação usa resultado por valor nocional para retirar a diferença de tamanho das posições; a carteira completa mantém os efeitos reais de composição dos lotes.

O critério congelado exigia melhora de ROI contínuo em ambos os cenários de custo, drawdown base de até 10%, retorno positivo nos três períodos separados em ambos os custos e nenhuma liquidação. Falhou nas duas exigências de melhora de ROI e na consistência dos períodos. O critério temporal original também continua reprovado, inclusive para o controle. Nenhum requisito foi afrouxado depois do teste.

## Verificação e reprodução

- **8 carteiras de controle reproduzidas exatamente**, incluindo negócios, curva horária, saldos, custos e meses, contra o resultado anterior congelado.
- 368 testes passaram; 13 novos cobrem causalidade por prefixo, atraso, duração mínima, condições LONG/SHORT, custos, funding liquidado, stop durante a espera e gaps.
- Candles H1 Last/Fair e funding conferidos por SHA256. As duas resoluções M5 anteriores foram mantidas e reproduzem exatamente seus candles H1. Não surgiu liquidação modelada no candidato.
- Resumo de todas as carteiras, meses, critérios e hashes em [research/momentum-conditional-exit-v1-results.json](research/momentum-conditional-exit-v1-results.json). Todos os pares com saídas alteradas estão em [research/momentum-conditional-exit-v1-pairs.csv](research/momentum-conditional-exit-v1-pairs.csv).

A fonte pública congelada e o resultado anterior estão no pacote de evidências já entregue. O resultado anterior deve ter SHA256 `75f8226d6fc4819c9c21bd9b745ebfac3cece8edba8724e2ea203aa154e31e3e`. O protocolo desta hipótese tem SHA256 `184a4c06b9f8b0ea9c158b2a8a88bb84727328f7604c7791f7df19b30993cf98`.

```bash
python -m unittest discover -s tests
python -m scripts.audit_momentum_conditional_exit \
  --protocol config/momentum-conditional-exit-v1-2026-11-16.json \
  --baseline /caminho/resultado-refinado-anterior.json \
  --intrahour-source /caminho/data/reports/momentum-intrahour-source \
  --data-root /caminho/data/reports \
  --output reports/momentum-conditional-exit/results.json \
  --summary-output reports/momentum-conditional-exit/summary.json
```

A opção `--data-root` permite substituir os caminhos locais da fonte pública. Os hashes de conteúdo continuam obrigatórios. O resumo publicado inclui metadados adicionais da execução e os hashes do código; não depende de um caminho local específico. Os dados completos do teste podem ser reconstruídos com o comando acima.

## Decisão

**Rejeitar esta saída e preservar o controle de 24h.** Todo o trabalho fica em `research/momentum-exit-v1`. A validação prospectiva de 30 dias, a produção, os alertas e o Telegram não foram alterados. A próxima hipótese de pesquisa é avaliar o ranking pela força relativa ao BTC, em protocolo separado, sem reutilizar este teste como confirmação independente. Essa próxima hipótese ainda não foi executada.

Permanecem as limitações da pesquisa anterior: viés de sobrevivência do universo e catálogo atuais, fills e derrapagem modelados, liquidação aproximada e drawdown observado apenas em marcações H1. Nenhum resultado aprova operação com dinheiro real.
