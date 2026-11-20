# Piloto de confluência SHORT: TAO em 19/11/2026

Status: **pesquisa isolada; não ativa o scanner nem o Telegram; não executa ordens**.

## Evidência e origem

Fonte: snapshot com candles fechados do par TAO-USDT-SWAP na **OKX**, capturado em 2026-11-20T07:37:55Z e preservado em tests/fixtures/tao_okx_20261120.json. Arquivo original: VinyRhyu/altcoin-scanner, branch market-data, coins/TAO-USDT-SWAP.json.

**Importante**: os parâmetros foram escolhidos DEPOIS de olhar a queda de TAO. O caso TAO é um estudo retrospectivo (in-sample) e não comprova capacidade preditiva. A fonte não é a MEXC; custos, spread, marcas, execução, funding e gaps da MEXC não foram validados.

### Inspiração técnica

- Acekiller88/crypto-signal-scanner, MIT: estrutura H4/H1/M15, confluência, liquidez, regras de rejeição e replay causal. Nenhum código externo foi copiado para este piloto.
- freqtrade/freqtrade: metodologia para procurar lookahead bias e backtesting realista. Nenhum código GPL foi copiado.

## Regras do protótipo

- Contexto H1: último H1 fechado com close abaixo da EMA20 e abaixo do H1 anterior.
- Proximidade de topo: máxima dos seis M5 anteriores ao candle sob avaliação a até 0,4% da máxima dos vinte M5 anteriores.
- Pré-alerta: candle M5 vermelho fechando pelo menos 0,2% abaixo daquele máximo, mais contexto H1 e proximidade de topo.
- Confirmação de SHORT: todos os itens acima, fechamento M5 abaixo das mínimas dos três M5 anteriores, volume financeiro do M5 >= 1,2x mediana dos doze M5 anteriores, TR do M5 <= 2x ATR14 anterior.
- Entrada SIMULADA: abertura do próximo M5 após a confirmação. Stop: maior máxima dos seis M5 anteriores + candle de confirmação, com buffer de 1bp do preço de entrada.
- Alvo: 1,5R bruto; exige RR líquido ex ante de ao menos 1:1 com custos hipotéticos de 0,06% taker + 0,02% slippage por lado. Timeout: doze candles (60 minutos).
- Conservadorismo de OHLC: TP e SL na mesma barra -> AMBIGUOUS, sem contar vitória. Não há envio de ordem.

## Replay TAO (BRT)

| Etapa | Horário | Resultado |
| --- | --- | --- |
| Pré-alerta | 22:15 | Contexto H1 baixista + rejeição perto de topo |
| Gatilho confirmado | 22:40 | M5 fecha abaixo de mínimas recentes com volume relativo >= 1,2 |
| Entrada simulada | 22:40 | 191,53 |
| Stop simulado | — | ~193,109 |
| TP simulado | — | ~189,161 |
| TP tocado | No candle das 22:50 | Baixa de 188,02 no M5 |

O evento das 22:50 ocorreu em vários ativos simultaneamente; o replay em 18 ativos (janela curta de cerca de oito horas) produziu 15 candidatos, 10 TPs e 5 saídas por tempo, sem SL observado nessa amostra. Esses resultados são fortemente correlacionados e **não** são taxa de acerto fora da amostra. Não somar 10 acertos como se fossem 10 experimentos independentes; não supor carteira com posições simultâneas.

## Executar testes (sem rede)

    python -m unittest tests.test_audit_confluence_pilot -v

## Executar replay local (sem rede)

    python -m scripts.audit_confluence_pilot --input tests/fixtures/tao_okx_20261120.json

A saída contém prealerts, trades, net_rr_ex_ante, gross_r, net_r e outcomes. Para atualizar os dados com o arquivo público original (fora do teste):

    python -m scripts.audit_confluence_pilot --url https://raw.githubusercontent.com/VinyRhyu/altcoin-scanner/market-data/coins/TAO-USDT-SWAP.json

## Antes de ativar qualquer alerta

1. Coletar dados MEXC Min5/Min60 verdadeiros e validar a correspondência de candles, relógio e volume.
2. Congelar as regras e testar walk-forward em vários dias e ativos, incluindo dias sem grandes quedas. Exigir amostras suficientes, intervalo de confiança e expectativa líquida positiva depois de custos reais.
3. Comparar com a estratégia M1 atual sob o mesmo período e mesmo universo. Registrar falsos positivos, alertas perdidos, atraso e cancelamentos.
4. Para operação com uma posição por vez, simular seleção entre sinais simultâneos antes de calcular ROI composto.
5. Só depois considerar integração opcional, feature flag, alertas de observação e testes paper; manter modo real bloqueado.

O módulo não muda os sinais ativos na branch main.


## Checagem exploratória em janelas históricas distintas

Mesmo conjunto de filtros aplicado sem ajuste posterior em outros snapshots de aproximadamente 8h, cada um com 16 ativos. Os arquivos históricos são recuperáveis do repositório VinyRhyu/altcoin-scanner nos seguintes commits:

| Snapshot (coleta UTC aproximada) | Commit | Sinais | TP | SL | TIME |
| --- | --- | ---: | ---: | ---: | ---: |
| 12/11 03:36 | ddd13ec22487 | 13 | 8 | 2 | 3 |
| 15/11 04:50 | 869f36aff43b | 1 | 0 | 0 | 1 |
| 18/11 02:32 | 3002b5d01898 | 0 | 0 | 0 | 0 |

Estes números são triagem exploratória dos snapshots, não auditoria definitiva de fills reais. Uma janela de 8h pode começar no dia anterior à data da coleta. A concentração dos TPs do dia 12 em ativos relacionados ao mesmo movimento de mercado é um risco de correlação. Os timeouts podem ganhar ou perder após custos; não os contar como ganhos nem como perdas fixas.

Próximos critérios: backtest sobre históricos MEXC mais longos, comparação em janelas independentes e mensuração de expectativa líquida com somente uma posição simultânea por carteira; depois validação prospectiva em paper.
