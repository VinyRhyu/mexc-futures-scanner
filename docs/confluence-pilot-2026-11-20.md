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


## Avaliação ampliada MEXC Futures — 21 dias, 10 contratos

Executada em 20/11/2026 na GitHub Action da PR de pesquisa, usando
scripts/audit_confluence_extended.py --days 21, API pública da MEXC https://api.mexc.com,
janela 2026-10-30T11:00Z a 2026-11-20T11:00Z, M5/H1.
A coleta de todos os 10 ativos cobriu 6.072 candles M5 e 540 candles H1 por ativo
(incluindo warmup). **Nenhuma execução real; resultados hipotéticos**.

| Métrica | Resultado |
| --- | ---: |
| Candidatos técnicos, sem restrição global de carteira | 300 |
| Alvos TP | 41 (13,7%) |
| Stops SL | 56 (18,7%) |
| Saída por 60 min sem TP/SL | 203 (67,7%) |
| Resultado agregado dos sinais (não é portfólio) | -19,519 R |
| Carteira com uma posição por vez (desempate: maior volume relativo ex ante) | 156 operações |
| Soma de R dessa carteira | **-12,329 R** |
| Retorno composto com risco hipotético de 1% da banca por operação | **-11,948%** |
| Drawdown máximo nessa carteira | **14,653%** |
| Dias UTC com resultado líquido agregado positivo/negativo | 5 / 17 (22 datas UTC abrangidas) |

Hipóteses: fee taker 0,06% e slippage 0,02% por lado, fechamento simulado no TP/SL
ou close de timeout de 60 minutos. Funding, order book, tamanho mínimo, execução parcial
e liquidação não estão modelados. Ambiguidade OHLC é perda de 1R no estresse.
Simular 1% de risco não garante execução viável com banca inicial de 1 USDT.

Por ativo: TAO 23 sinais (5 TP, 3 SL, 15 TIME; -2,436 R); SOL 27 (4/3/20; -1,546R);
AVAX 35 (7/5/23; -0,320R); ENA 42 (6/6/30; +4,043R);
DOT 36 (5/11/20; -5,967R); ZEC 29 (5/7/17; +0,351R);
HYPE 47 (2/11/34; -9,847R); AAVE 23 (2/4/17; +1,194R);
BTC 19 (2/1/16; -2,091R); ETH 19 (3/5/11; -2,900R).
Não selecionar ENA/ZEC/AAVE após ver lucros: seria seleção retrospectiva.

### Caso TAO na MEXC, e não OKX

No histórico MEXC do contrato TAO_USDT, sinal M5 confirmado
**19/11 às 22h40 BRT**, entrada hipotética na abertura do próximo
M5 a 191,50 USDT, stop 193,03915 USDT, alvo 189,191275 USDT.
Alvo tocado no candle iniciado às 22h50 BRT; lucro após custos hipotéticos
de +1,0849R. O caso TAO foi usado para escolher os parâmetros
(in-sample); não comprova vantagem preditiva.

### Conclusão

**Não integrar o piloto na produção.** O acerto histórico em TAO não compensou
os resultados dos outros dias/ativos. O excesso de timeouts e a concentração
de sinais simultâneos sinalizam baixa seletividade. A estratégia precisa de nova
hipótese pré-registrada e validação em dados independentes, comparada à baseline
M1 nas mesmas condições, antes de sequer pensar em sinais no Telegram.


## Verificação adicional sem ajuste de parâmetros: 42 dias contínuos

Uma segunda execução da GitHub Action repetiu o mesmo modelo inalterado em uma
janela histórica anterior de 21 dias, contígua à anterior (09/10/2026 a
30/10/2026 11:00 UTC), usando os mesmos dez contratos e mesma metodologia.
As duas janelas tiveram cobertura integral de M5/H1 nos dez símbolos.

| Medida | 09–30/10 (21 dias) | 30/10–20/11 (21 dias) | 42 dias |
| --- | ---: | ---: | ---: |
| Sinais | 224 | 300 | 524 |
| TP | 37 | 41 | 78 |
| SL | 48 | 56 | 104 |
| Timeouts | 139 | 203 | 342 |
| Selecionadas (uma posição por vez) | 115 | 156 | 271 |
| R líquido da carteira | -10,726R | -12,329R | -23,055R |
| ROI composto com 1% de risco/entrada | -10,457% | -11,948% | **-21,156%** |
| Drawdown máximo calculado da carteira contínua | — | — | **24,026%** |

O ROI de 42 dias encadeia sequencialmente as 271 operações selecionadas sem
reiniciar o saldo entre as janelas. Os sinais que se sobrepõem são contabilizados
na contagem de candidatos, mas não são executados simultaneamente no portfólio.
O filtro de seleção de sinais concorrentes é pelo maior volume relativo disponível
no momento do sinal, nunca pelo resultado futuro.
Nas duas análises separadas, 12 resultados diários UTC tiveram R agregado positivo
e 32 negativo (a data de 30/10 participa das duas janelas parciais).
A janela total contém 42 dias completos, e resultados diários não representam
uma carteira única por dia.

**Conclusão reforçada:** o modelo tem expectativa histórica líquida negativa
nas duas janelas. Não ativar em produção. Testar um novo mecanismo apenas com
hipótese explícita, sem selecionar retroativamente o período/moeda vencedores.
As taxas, slippage e risco de 1% são hipóteses; negociações reais podem ser
piores e o tamanho mínimo pode inviabilizar operação com saldo de 1 USDT.

Execução reproduzível: GitHub Actions run 44742303641, associada à pull request
#2 em rascunho.
