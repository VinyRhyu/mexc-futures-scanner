> Atualização: a publicação autorizada e as coletas foram executadas. Veja [a validação ampliada, com Fair e resolução M5](momentum-expanded-fair-2026-11-16.md). O texto abaixo preserva o checkpoint anterior.

# Desenvolvimento e testes de momentum — 16/11/2026

**Foi encontrada uma candidata com resultado recente positivo, mas nenhuma configuração passou em todos os critérios de consistência.** O momentum diário alinhado à direção de sete dias do Bitcoin terminou em US$ 107,30 após custos; o controle sem esse alinhamento terminou em US$ 102,43. A confirmação adicional de um dia piorou o resultado e foi rejeitada.

## O que foi desenvolvido e executado

Sete configurações distintas, em dois conjuntos de dados e dois cenários de custo: **28 cenários distintos**. Os controles foram repetidos para verificar consistência, totalizando 36 execuções. As quatro etapas foram registradas antes de calcular seus resultados: três configurações de rompimento/correção em 1h/4h; controle diário versus permanência prolongada; alinhamento semanal ao Bitcoin; confirmação adicional diária. Isso é pesquisa adaptativa, com várias tentativas, não uma única descoberta independente.

Todos os modelos usam uma carteira global de US$ 100, margem isolada de 10× e risco planejado de até 2% por posição, incluindo custos e reserva de funding estimada somente a partir de eventos já conhecidos. Contratos são arredondados para lotes válidos, a quantidade respeita margem e um buffer de liquidação de 1,5 vez a distância do stop. Funding realizado usa eventos históricos. Gaps e movimentos rápidos podem exceder o risco planejado.

## Todas as configurações, incluindo as negativas

| Configuração | Histórico antigo, Last como proxy | Recente com Fair real | Trades recentes | Queda máxima recente H1 |
| --- | ---: | ---: | ---: | ---: |
| H1_CHANNEL | 27,53% | -22,09% | 43 | 28,04% |
| H4_CHANNEL | -4,87% | -6,02% | 12 | 9,85% |
| H1_PULLBACK | -32,36% | -16,30% | 46 | 25,11% |
| MOMENTUM_24H | 38,96% | 2,43% | 21 | 7,45% |
| MOMENTUM_PERSIST | -10,77% | 6,64% | 4 | 3,01% |
| MOMENTUM_BTC_GATE | 23,50% | 7,30% | 21 | 4,15% |
| MOMENTUM_BTC_7D_1D | -0,85% | -1,86% | 11 | 3,56% |

O histórico antigo cobre 01/07–30/09 em datas UTC, equivalentes a 30/06 às 21h até 30/09 às 21h de Brasília. Os modelos de 1h/4h usam o recorte recente de 17/10 às 21h a 13/11 às 21h de Brasília, 27 dias. Os modelos de momentum usam **23/10 às 21h a 13/11 às 21h de Brasília, 21 dias**, depois do aquecimento necessário. Portanto, a tabela não permite comparar diretamente o valor absoluto de retorno entre famílias com diferentes janelas. As comparações pareadas de cada etapa usam a mesma janela.

O conjunto de 26 ativos é formado por sobreviventes disponíveis na coleta, com regras de contrato atuais aplicadas retrospectivamente. No recorte antigo ainda falta Fair: Last foi usado como proxy explícito para marcação e liquidação. Essa limitação impede tratar o retorno antigo como plenamente validado. Os hashes dos 52 arquivos foram fixados antes da primeira execução desta rodada.

## A candidata preservada: MOMENTUM_BTC_GATE

1. A cada fechamento diário UTC, calcular o retorno dos sete dias anteriores de cada ativo usando somente candles já fechados.
2. Aceitar LONG somente com momentum positivo; SHORT somente com momentum negativo. Exigir que essa direção concorde com o retorno de sete dias do Bitcoin.
3. Entre os contratos elegíveis, priorizar o maior retorno absoluto normalizado por ATR14/preço; usar custos/risco e símbolo para desempates. Exigir volume financeiro aproximado das 24h anteriores de pelo menos US$ 5 milhões.
4. Aguardar uma hora completa: o sinal das 21h de Brasília tem entrada simulada às 22h. Um stop tocado durante a espera cancela a tentativa. A abertura inclui spread, slippage adverso e arredondamento por tick.
5. Stop inicial a duas vezes o ATR14 diário, limitado a 5% do preço no sinal; revalidar a geometria no preço da execução. O stop pode subir/descer com a trajetória conhecida, sempre após o atraso estabelecido. Não há alvo fixo.
6. Encerrar por stop, mudança de direção do momentum ou prazo de 24h. A avaliação diária permite fechar e eventualmente abrir outra posição no mesmo horário conhecido; nunca usa o desfecho futuro para escolher o ativo.

**Essa proposta muda a duração das operações: até 24h, com decisão diária.** Não é uma melhoria já comprovada para o gatilho M1 nem um mecanismo de alertas a cada minuto. O scanner de produção e os envios não foram alterados.

| Medida recente, 21 dias | Controle diário | Alinhamento BTC 7 dias |
| --- | ---: | ---: |
| Saldo inicial | US$ 100,00 | US$ 100,00 |
| Saldo final líquido | US$ 102,43 | US$ 107,30 |
| Retorno líquido base | +2,43% | +7,30% |
| Retorno com custos elevados, carteira recalculada | +1,36% | +6,29% |
| Operações | 21 | 21 |
| Positivas / negativas | 9 / 12 | 12 / 9 |
| Fator de lucro líquido | 1,27 | 2,14 |
| Queda máxima H1 | 7,45% | 4,15% |

Taxa-base de 0,06% por execução, spread total de 0,02% e slippage igual ao maior entre 0,02% do preço e dois ticks. No estresse: taxa de 0,10% por execução, spread total de 0,04% e slippage de 0,04% ou dois ticks. Os cenários recalculam carteira, quantidades e decisões financeiras; não são uma mera subtração de taxas nos mesmos trades. Essas taxas não são uma tabela pessoal verificada.

## Por que a candidata ainda não foi aprovada

No histórico antigo, o alinhamento semanal obteve +23,50% no total, mas teve **−10,35% em julho**, +5,64% em agosto e +30,41% em setembro. Julho–agosto somou −5,29%. A queda máxima antiga foi 14,44%, medida com o proxy Last. O ganho agregado esconde dependência do período de setembro.

No recorte recente, o melhor trade contribuiu US$ 4,29: aproximadamente 58,7% do ganho líquido. Retirando-o contabilmente e mantendo as quantidades dos demais, o saldo seria US$ 103,01; isso não é outra simulação de carteira. A reamostragem exploratória por blocos está no JSON, com intervalos largos e sensíveis ao tamanho do bloco. Depois de escolher uma candidata entre várias, esses intervalos não são testes formais de significância nem probabilidades de lucro futuro.

Há somente 21 posições recentes e os dados já eram disponíveis em trabalhos anteriores. Nenhum recorte desta entrega é apresentado como holdout intocado. Todos os critérios registrados continuam falsos; não foram relaxados para acomodar o resultado positivo. Faltam Fair no histórico amplo, dados novos e execução observável para considerar promoção.

## Verificação do código e dos dados

**344 testes locais passaram.** Houve 1.092 comparações em snapshots reais, retirando todos os candles futuros: entradas, ATR, escores de seleção e atualizações de stop permaneceram iguais; 669 comparações continham candidatos de entrada. Testes específicos verificaram o uso somente de funding passado, o alinhamento ao Bitcoin, LONG/SHORT, gaps, liquidação por Fair, ausência de dupla cobrança, caixa, lotes e igualdade entre saldo final e soma dos fluxos.

As oito comparações de controles entre etapas foram idênticas. Foram preservados todos os cenários negativos. A auditoria final também trata de forma conservadora um crédito de funding e uma saída por gap no mesmo instante, sem atribuir crédito cuja precedência não é demonstrada.

## Próxima coleta preparada, ainda não executada em rede

O coletor local recebeu uma página HTML “Site Unavailable” ao consultar a API MEXC. Não foram inventados candles nem substituída a fonte por outro mercado. Foi preparado um job separado de pesquisa, que faz apenas GET em endpoints públicos, sem credenciais de negociação, estado de produção ou Telegram.

O job preparado coleta Last H1, Fair H1 e funding dos mesmos 26 ativos entre 01/05 e 16/11 UTC. O plano é avaliar somente a candidata congelada e seu controle: uma checagem retrospectiva em datas anteriores ainda não examinadas por este experimento, substituir o proxy antigo por Fair real e estender o recorte recente. Uma avaliação em meses anteriores não substitui validação prospectiva em dados posteriores ao congelamento.

Arquivos preparados: `scripts/collect_multihour_source.py`, `config/multihour-source-v1-2026-11-16.json` e `.github/workflows/research-multihour-source.yml`. O workflow é isolado à branch `research/multihour-v1` e coleta quando esses arquivos são publicados nessa branch. Não foi publicado ou acionado nesta entrega. A publicação depende de autorização explícita, pois a revisão automática bloqueou anteriormente o envio de arquivos de pesquisa ao repositório público.

## Como reproduzir este lote

Na raiz do projeto extraído do pacote:

```bash
python -m unittest discover -s tests
python -m scripts.run_research_batch --data-root data --output reports/reproducao
```

O diretório `data` do pacote contém os históricos públicos congelados de `momentum/source` e `momentum-week10x/source`. O comando não acessa rede, não executa ordens e não envia mensagens. Os protocolos preservam os hashes originais; `--data-root` apenas remapeia a localização dos mesmos bytes.

## Fundamentação e limites da pesquisa

[Liu e Tsyvinski — Risks and Returns of Cryptocurrency](https://www.nber.org/papers/w24877) é uma motivação para estudar momentum temporal em cripto; seus resultados em outros ativos e épocas não validam nossos sete dias, nosso filtro Bitcoin, a MEXC ou o retorno encontrado aqui. Esses detalhes são hipóteses próprias de projeto, identificadas nos protocolos.

A [documentação oficial de candles MEXC](https://www.mexc.com/api-docs/futures/market-endpoints/get-candlestick-data) foi conferida para a nova coleta: intervalos e timestamps são explícitos, com limite de 2.000 pontos por chamada. O coletor usa janelas de 1.900 pontos e falha diante de lacunas, duplicatas conflitantes, histórico incompleto ou símbolos ausentes. Sua integração foi testada com fonte sintética; a execução real da próxima coleta continua pendente.
