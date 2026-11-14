# Momentum relativo de 7 dias com reavaliação diária — 14/11/2026

Resultado exploratório positivo, porém modesto: +2,11% em 90 dias após custos
modelados e funding histórico. A vantagem não está aprovada para produção.
O universo foi escolhido hoje e contém sobreviventes; não é um teste sem viés
de todo o mercado nem valida uma banca de US$1 ou alavancagem de 10x.

## Regra congelada antes de coletar os resultados

O protocolo foi publicado no commit 62449f2a176870def370ce3c230c8a11003b9ae8.
Ranqueamento dos retornos fechados dos últimos sete dias. Entre ativos com
história suficiente e volume financeiro aproximado de pelo menos US$5 milhões
nas 24h anteriores, selecionar a cauda superior de 20% para LONG somente com
retorno positivo e a cauda inferior para SHORT somente com retorno negativo.
Empates pelo símbolo. Slots sem sinal ficam em caixa, sem redistribuição.

Decisão diária às 00h UTC e abertura uma hora depois, às 01h UTC (22h BRT).
Peso nominal igual por slot, metade por cauda, limite de 20% por ativo.
Escala conjunta para no máximo 1x de exposição inicial e 2% de perda planejada
nos stops incluindo taxas e execução estimadas; arredondamento para baixo
pelas regras públicas dos contratos. Fechamento e reabertura diária mesmo
quando o ativo continua no ranking. Sem reinvestir no mesmo dia após stop.

Stop fixo a duas vezes a média simples dos 14 true ranges diários anteriores.
Saída no stop ou após 24h, sem TP fixo e sem gate prospectivo de RR baseado
em TP. Esta é uma adaptação experimental, não reprodução literal de um paper.
O modelo não reutiliza o piso 10x ou o risco de 10% por trade do bot intradiário.

## Período e referência

26 ativos atuais, todos com histórico de preços e funding cobrindo a janela.
Dados H1 de 03/06 a 01/10/2026 UTC, com 30 dias iniciais de aquecimento e
90 decisões de 03/07 a 30/09 UTC. Em BRT, carteira acompanhada de 02/07 às
22h até 30/09 às 22h; bloco reservado começa em 31/08 às 22h.

Primeiros 60 dias para conferência, últimos 30 reservados à validação desta
regra. Nenhum parâmetro foi ajustado após os resultados. As datas precedem
os testes intradiários de outubro/novembro, mas o universo atual ainda produz
viés de seleção/sobrevivência e não há múltiplos blocos de validação.

Referência de US$1.000 para permitir observar o método e os lotes, sem
amplificação por alavancagem. Exposição bruta média efetivamente aberta de
14,10% do patrimônio, pois o risco conjunto limita a quantidade e slots podem
ficar em caixa. Maior risco planejado observado: 1,988% antes de funding e gaps;
isso não é uma garantia de perda máxima.

## Resultado da carteira simulada

| Janela | Retorno líquido | Trades | Trades positivos | Acerto | Profit factor | Queda máxima H1 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Primeiros 60 dias | +0,06% | 427 | 196 | 45,90% | 1,004 | 2,80% |
| Últimos 30 reservados | +2,05% | 194 | 75 | 38,66% | 1,225 | 2,80% |
| Total 90 dias | +2,11% | 621 | 271 | 43,64% | 1,091 | 3,33% |

Saldo: US$1.000 -> US$1.021,08. O retorno dos blocos é composto, não somado.
Trades positivos consideram taxas, execução estimada e funding. Houve 10
stops e 611 saídas pelo prazo: a taxa de acerto não é TP versus SL.
Queda máxima é medida nos fechamentos H1 e após execuções, não tick a tick.

Custos acumulados: taxas US$15,18; spread/deslizamento estimados US$13,00;
funding líquido pago US$1,20. Funding usa os eventos históricos com sinal
LONG/SHORT e marcas de preços H1 aproximando o preço justo; não se supôs
funding zero. P&L por execução antes das taxas já incorpora spread e slippage.

LONGs contribuíram +US$67,39 e SHORTs -US$46,31. Isso é diagnóstico do mesmo
teste, não valida eliminar SHORTs depois de olhar os resultados. Essa mudança
seria uma nova hipótese e exigiria outra validação.

## Referência contextual

BTC comprado e mantido a 1x, com os mesmos custos de execução e funding,
retornou +33,88%, com queda máxima H1 de 7,91%. A comparação não equipara
riscos: BTC fica quase totalmente exposto, não tem o teto conjunto de risco
dos stops e não gira a carteira diariamente. Portanto o resultado positivo
não demonstra superioridade ao BTC ou alfa ajustado ao risco.

## Banca de US$1

Na checagem proporcional de dimensionamento desta mesma regra sem alavancagem,
651 das 653 ordens candidatas ficariam abaixo do lote mínimo; apenas duas
passariam por esse requisito isolado. Não foi simulada uma carteira completa
de US$1 nem uma adaptação a 10x. Os resultados percentuais não podem ser
projetados para esse capital e essas condições.

## Integridade

- 26 histórias completas, 2.881 candles H1 por ativo, funding histórico cobrindo
  início e fim e sem intervalos não explicados maiores que oito horas na janela.
- 90 verificações de prefixo: ranking e ATR do dia usam somente informação já fechada.
- Replay separado dos 60 dias reproduziu exatamente os mesmos 427 trades e saldo,
  confirmando que os últimos 30 dias não influenciam os primeiros.
- Conservação de caixa: soma dos P&Ls líquidos dos trades coincide com a variação
  da carteira. Risco e exposição agregados verificados em cada abertura.
- Cinco testes cobrem causalidade, risco/lotes, sinal do funding, exclusão de cobranças
  de funding após stop e custos em saída com preço inalterado.

## Limites e reprodução

Usam-se os 26 ativos hoje listados/líquidos, regras atuais de tamanho e tick,
volume histórico aproximado por contratos x tamanho atual x preço, spread e
slippage modelados e livro não observado. Não há dados históricos de preço
justo ou execução tick a tick. Saída diária usa o fechamento H1 que termina
no horário de saída. Gaps adversos no stop são cobrados no preço de abertura;
funding com ordem intrahorária incerta é tratado conservadoramente.

Coleta pública: execução 43653872998, artefato momentum-daily-source-2026-11-14,
sem credenciais de negociação, ordens ou Telegram. Resumo, patrimônio diário
e hashes dos arquivos: docs/relative-momentum-daily-2026-11-14.json.
Código experimental e relatório estão somente na branch de auditoria.

```sh
python -m unittest tests.test_relative_momentum_daily -q
python -m scripts.audit_relative_momentum_daily --source /pasta/artefato-extraido --protocol config/audit-momentum-daily-2026-11-14.json --output /tmp/momentum-results.json
```

Fontes da hipótese: Liu e Tsyvinski, Risks and Returns of Cryptocurrency,
https://www.nber.org/papers/w24877; Liu, Tsyvinski e Wu, Common Risk Factors
in Cryptocurrency, https://www.nber.org/papers/w25882. Esses estudos não
validam diretamente esta parametrização nem os custos e execução assumidos.
