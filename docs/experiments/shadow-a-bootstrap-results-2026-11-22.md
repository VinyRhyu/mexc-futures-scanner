# Resultado da primeira execução do observador shadow A

Execução validada: [GitHub Actions #45102996176](https://github.com/VinyRhyu/mexc-futures-scanner/actions/runs/45102996176), commit `88abead988ce79e3a79a337430bcf29d110bd571`. Snapshot calculado em **2026-11-23 02:56:14 UTC** (22/11, 23h56 BRT), usando a branch operacional `scanner-state` somente como fonte de leitura.

## Cobertura e contagem

- 19 testes unitários e de integração sintética passaram.
- Coleta GET pública MEXC + estado: **COMPLETE**, nenhum símbolo sem histórico necessário ou com OHLC M1/M15 divergente.
- Janela de observação dos sinais já registrados: últimas 12 horas. Sinais encontrados entre **22/11 12h18 e 23h39 BRT**.
- **39 registros de planos** com variante `CONFIRMADA`; **32 eventos distintos** por (símbolo, direção, minuto de confirmação). Sete registros de plano extras são duplicações técnicas do mesmo evento. Cinco grupos duplicados têm stop ou alvo ligeiramente diferentes; os níveis individuais continuam preservados no JSON.
- Filtro A aplicado às 32 oportunidades distintas: **7 classificadas como POSSÍVEL ENTRADA TARDIA** e **25 como SEM VETO A**. Contagem em planos: 8 vetos / 31 sem veto.
- Observação posterior dos candles, **sem simulação de ordem, fill ou taxa**: dentre os 7 eventos com veto, 4 tocaram o SL antes do TP e 3 tocaram o TP antes do SL; dentre os 25 sem veto, 15 tocaram o SL antes do TP e 10 tocaram o TP antes do SL. Não houve divergência de classificação dos caminhos entre planos duplicados nesta rodada.
- O observador não consulta carteira, ordens, Telegram, credenciais, saldo ou permissão de trade; **não alterou alertas, cronjob.org, `main`, nem `scanner-state`**.

## Limitações críticas

1. **Bootstrap retrospectivo, não amostra prospectiva.** Os sinais históricos já existiam quando o observador foi executado. Nenhum desempenho futuro está demonstrado.
2. A ocorrência do toque no TP/SL não comprova execução de uma ordem real ou mesmo uma entrada financeira viável; a faixa, o livro, a taxa e a situação da carteira naquele momento não foram avaliados. Nunca apresentar 10/25 ou 3/7 como taxa de acerto real.
3. Os planos confirmados podem já estar expirados no estado consultado; não filtramos por status posterior, para evitar viés de resultado.
4. Somente 32 eventos; amostra pequena, dependente e restrita às moedas que entraram no estado operacional recente. Não confundir com as coortes anteriores de 12 ativos.
5. Como alguns eventos possuem vários planos com stops e alvos diferentes, uma futura simulação executável deve escolher uma política de plano **antes** de observar o desfecho, para não favorecer retrospectivamente o que acertou.
6. Cronjob.org e o scanner principal continuam separados do observador. Para testar de verdade em modo sombra prospectivo, é necessário ativar execução periódica própria, com carimbo de data de início, persistência independente e deduplicação ao longo do tempo. **Isso ainda não está ativo neste PR**.

## Decisão

Validação técnica do observador passou: regras A e janelas causais reproduzidas, fonte íntegra e duplicidades diagnosticadas. A qualidade financeira do filtro A continua **INCONCLUSIVA**; não há autorização científica para bloquear sinais em produção.

