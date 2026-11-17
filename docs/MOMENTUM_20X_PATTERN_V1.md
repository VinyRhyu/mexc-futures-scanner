# Pesquisa 20x e padrões históricos — V1

Em 17/11/2026, o teste isolado não justificou substituir a referência 10x: a versão 20x sem aprendizado perdeu patrimônio, e o filtro histórico não teve amostra suficiente para operar. O resultado zero do filtro significa ausência de operações, não capacidade preditiva ou proteção comprovada. Nenhuma aprovação para produção.

Protocolo publicado antes dos resultados: commit `61f58aa3e4e2b2541be2d043bde7d70ebc7776ca`, arquivo `config/momentum-20x-pattern-v1-2026-11-17.json`, SHA256 `529798e980a11afde7877f2dc68ceda152fc1dac7304838839b25198c223c69c`. Base do código: `30e7ade13521d4cf60f33cf859f6e3ead924540a`.

## Hipótese e teste

Três versões: referência relativa ao BTC em 10x; a mesma regra em 20x; 20x com um único filtro de vizinhos históricos. Todas usam orçamento de perda planejada de 1% do patrimônio, uma posição simultânea e prazo máximo 24 h. Mantidos stops, liquidez, contratos e distância mínima de liquidação igual a 1,5 vezes a distância ao stop. O 1% é dimensionamento planejado, não garantia de perda máxima: gaps e liquidação podem superá-lo.

O filtro compara o movimento de 1 dia e a força de 7 dias relativa ao BTC, ambos divididos pela volatilidade ATR14 diária conhecida no sinal. Usa distância euclidiana sem ajuste global de escala, somente exemplos da mesma moeda e direção, 20 vizinhos e média de resultado líquido por unidade de risco estritamente positiva. Não há busca de outros números de vizinhos, pesos ou limiares.

Cada exemplo é uma operação de referência independente de US$ 100, em 20x com 1% de risco, custos base, stops modelados e taxas de funding da fonte histórica, sujeita às mesmas verificações de elegibilidade. Entradas rejeitadas não geram exemplos. O resultado só fica disponível após entrada+24 h+1 h de embargo, mesmo se o stop ocorrer antes. A consulta acontece na fronteira do sinal, antes da hora de atraso. O mesmo aprendizado de custos base é usado no cenário de estresse. Exemplos prévios podem treinar blocos posteriores; não se reinicia o aprendizado artificialmente entre blocos.

## Resultados

Período contínuo de 16/05/2026 00 UTC a 16/11/2026 00 UTC:184 dias; capital hipotético inicialUS$ 100. ROI abaixo é sobre o patrimônio total, após custos modelados e funding. Queda máxima mede patrimônio marcado a cadaH1, sem capturar todas as oscilações intrahorárias.

| Versão | Final base | ROI base | ROI estresse | Queda máxima base | Queda máxima estresse | Operações base/estresse |
|---|---:|---:|---:|---:|---:|---:|
| Referência 10x | US$ 130,18 | +30,18% | +23,70% | 7,54% | 7,80% |184/184|
| Mesma regra 20x | US$ 96,79 | −3,21% | −3,78% | 9,35% | 9,38% |26/26|
|20x + filtro de padrões | US$ 100,00 |0,00%|0,00%|0,00%|0,00%|0/0|

| Bloco separado | Referência 10x base/estresse |20x base/estresse |20x + filtro base/estresse |
|---|---:|---:|---:|
|16/05–01/07,46 dias|+7,76% / +6,50%|+3,66% / +3,17%|0% /0%|
|01/07–01/10,92 dias|+14,41% / +11,71%|−4,75% / −5,35%|0% /0%|
|24/10–16/11,23 dias|+5,59% / +5,00%|−1,10% / −1,09%|0% /0%|

O período contínuo inclui intervalos entre os blocos separados; não é a soma nem um teste independente deles.

## Por que o aprendizado não operou

A mudança para 20x aproximou a liquidação e tornou a maioria dos stops incompatível com a margem isolada do modelo. No contínuo base sem filtro,3.089 candidatos foram rejeitados por proximidade da liquidação. Essa contagem é de candidatos, não dias nem operações. Reduzir stops ou a proteção para aumentar a amostra não fazia parte do protocolo.

Foram produzidos 42 exemplos elegíveis no conjunto completo de treinamento, distribuídos entre 18 moedas; o maior total por moeda foi 5, antes de separar direção e disponibilidade temporal. Nas 42 consultas elegíveis do contínuo base com filtro, havia no máximo 3 exemplos anteriores da mesma moeda e direção. Todas foram recusadas por amostra insuficiente. Não houve consulta com 20 vizinhos e nenhuma decisão positiva ou negativa baseada na médiaR. Portanto, a utilidade preditiva da similaridade permanece **inconclusiva**, e o teste exploratório pré-definido falhou.

## Incerteza de stop e liquidação

Na versão 20x sem filtro, TIA_USDT em 23/09/2026, candle 14–15 UTC, toca stop e liquidação estimada dentro da mesmaH1. Sem uma sequência intrahorária congelada para essa hora, o replay assume liquidação primeiro. Isso aparece uma vez em cada cenário do contínuo e uma vez no bloco 92 dias; são repetições do mesmo evento histórico, não quatro incidentes distintos. **Não há comprovação de liquidação real nem preenchimento real do stop.** O ROI 20x depende dessa convenção conservadora.

Há também dois exemplos de treinamento de TIA com ambiguidadeH1, sinais 23/09 e 28/09. Foram preservados com o resultado conservador, identificados noJSON; nenhum chegou a integrar uma previsão com 20 vizinhos, pois essa quantidade nunca foi alcançada. Nenhuma nova cotação ou sequência de minutos foi inventada. As duas resoluçõesM5 previamente verificadas continuam disponíveis apenas nas horas originais de WLD e ARB.

## Verificação e reprodução

- 380 testes locais passaram, incluindo 14 novos testes de causalidade, maturação, empate, amostra mínima,20x/margem e rejeição de stops.
- 8 carteiras completas da referência 10x reproduzidas exatamente, incluindo curvas e operações.
- Todos os 42 exemplos de treinamento conferidos contra replay independente de uma entrada: mesmos preços, stops, quantidade, funding, taxas, resultado e horário de saída.
- 3 reconstruções com fonte truncada no tempo,78 consultas de previsão idênticas com/sem futuro e 234 checagens dos sinais/ranking a partir de prefixos fechados.
- Contabilidade e limite de risco planejado conciliados por operação; nenhuma sobreposição de posições.

Resultados compactos: `docs/research/momentum-20x-pattern-v1-results.json`. Todos os exemplos, inclusive perdas: `docs/research/momentum-20x-pattern-v1-labels.json`. Todas as consultas elegíveis por bloco/custo: `docs/research/momentum-20x-pattern-v1-predictions.csv`. O resultado completo reproduzível, com curvas e operações, tem SHA256 registrado noJSON compacto.

```bash
python -m unittest discover -s tests -q
python -m scripts.audit_momentum_20x_pattern \
  --protocol config/momentum-20x-pattern-v1-2026-11-17.json \
  --parent /caminho/momentum-relative-btc/results.json \
  --data-root /caminho/data \
  --intrahour-source /caminho/data/reports/momentum-intrahour-source \
  --output reports/momentum-20x-pattern
```

`--data-root` contém `reports/multihour-public-source`; os hashes congelados validam as 26 fontes. O resultado pai é oJSON completo da pesquisa relativa ao BTC, SHA256 `cbd182fbcd8affe219057d2e5f707a3e052e336d40e0ed352f6557bfd904af16`. A documentação dessa pesquisa descreve sua geração. Sem `--data-root`, mantêm-se os caminhos originais de execução do protocolo histórico.

## Alcance da conclusão

A causalidade temporal evita usar informação futura em cada decisão. Não transforma dados históricos já explorados em validação independente. O universo e catálogo atuais trazem viés de sobrevivência/metadados; fills são simulados e a liquidação é aproximada. A referência 10x já apresenta concentração em poucos lucros e períodos negativos, documentados em `MOMENTUM_RELATIVE_BTC_V1.md`; seu ROI superior não é aprovação.

Aumentar de 10x para 20x, mantendo o mesmo tamanho de posição, reduz a margem exigida e aproxima a liquidação; não dobra automaticamente o lucro monetário. Neste teste, as verificações de elegibilidade mudaram fortemente os ativos e dias operados. Fonte primária das relações de margem: [MEXC Margin Calculation Guide](https://www.mexc.com/support/article/mexc-margin-calculation-guide-312054740132052992). A separação temporal com intervalo antes do teste segue o princípio descrito na documentação [TimeSeriesSplit](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html); a escolha de 20 vizinhos é apenas uma hipótese exploratória deste projeto.

A próxima hipótese deve resolver primeiro a escassez de exemplos 20x elegíveis, com história adicional verificável ou outro protocolo de representação previamente registrado. Não reduzir os 20 vizinhos depois de observar este resultado para aparentar sucesso. Nenhuma alteração emmain, scanner-state, Telegram, conta de negociação ou na validação prospectivaMOMENTUM_PROSPECTIVE_30 D_V 1, que segue em andamento com sua política 10x congelada.
