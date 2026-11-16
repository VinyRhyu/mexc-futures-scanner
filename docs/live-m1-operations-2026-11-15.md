# Auditoria operacional do scanner M1

**Janela: 15/11/2026, 15h às 21h, Brasília.** Inspeção dos disparos reais do GitHub, do estado persistido e do envio ao Telegram. Não é backtest de estratégia, simulação de ROI ou análise de ordens reais.

**Conclusão:** o ciclo operacional é maior que o disparo de um minuto, e parte das confirmações é descartada por atraso. Existem também bloqueios financeiros. Os cinco alertas de entrada simulada encontrados tiveram envio confirmado pela API do Telegram; isso não demonstra leitura, execução manual ou lucro. Nenhum parâmetro ou serviço foi alterado.

## Fontes e amostragem

- Produção conferida em `20c500deb4fbea15573dbced9eaddb6bf5839cae`.
- Estado congelado em `da2f28f427c6cd13f8bc77233d6cd85c38baf350`; última análise registrada às 21:05:01 de 15/11. O estado foi observado alguns minutos depois do fim da janela.
- Todas as 361 execuções do workflow Scanner MEXC criadas entre 18h UTC de 15/11 e 00h UTC de 16/11, após deduplicar IDs de quatro páginas capturadas enquanto novas execuções continuavam chegando.
- Amostra uniforme no tempo de 24 execuções bem-sucedidas para duração de jobs/etapas; oito canceladas para verificar existência de job; todas as seis falhas tiveram seus logs examinados.
- Quatro execuções bem-sucedidas foram amostradas para tentar reconstruir as fases internas.
- Percentis por interpolação linear. Estatísticas de jobs se referem à amostra, não a todos os 187 jobs bem-sucedidos.

## Frequência e cancelamentos

| Resultado | Execuções | Percentual |
|---|---:|---:|
| Sucesso | 187 | 51,80% |
| Cancelamento | 168 | 46,54% |
| Falha | 6 | 1,66% |
| Total | 361 | 100% |

Dos 361 disparos, 360 foram workflow_dispatch e um foi schedule. Nos oito cancelados amostrados não existia job iniciado. O workflow usa um grupo serializado, com cancel-in-progress=false e fila padrão. A documentação informa que uma nova execução pendente substitui a pendente anterior por padrão, mesmo sem cancelar a execução ativa. A configuração e os resultados são compatíveis com esse mecanismo; a API não fornece o motivo individual de todos os 168 cancelamentos.

[Documentação oficial de concorrência](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#concurrency). Não foi atribuído o problema exclusivamente a cron, runner ou rede. As regras de serialização protegem a persistência do estado e não devem ser removidas sem um desenho equivalente.

## Tempos observados em 24 jobs bem-sucedidos

| Medida | Mediana | P95 | Mínimo–máximo |
|---|---:|---:|---:|
| Criação do disparo até início do job | 25.0s | 54.7s | 5–57s |
| Duração total do job | 114.5s | 129.5s | 81–132s |
| Etapa coletar/persistir/notificar | 109.0s | 124.7s | 76–125s |
| Criação do disparo até início da etapa principal | 28.0s | 56.7s | 7–64s |

O tempo mediano do job foi 114,5s, enquanto o acionamento chega aproximadamente a cada 60s. A etapa principal, sozinha, teve mediana 109s. Aumentar o número de disparos ou acumular uma fila maior não aumenta automaticamente a capacidade de processamento. O intervalo mediano entre os horários de criação dos disparos que terminaram em sucesso foi 120s; isso não é a distância exata entre coletas. Houve um intervalo de 13min sem disparo posteriormente bem-sucedido, mas as execuções com falha nesse trecho ainda coletaram preços: não significa 13min sem análise.

Os logs de restore,scan,persistência e notify aparecem quase no mesmo instante nas quatro amostras, embora a etapa dure mais de um minuto. Esses timestamps de captura de stdout estão concentrados por buffering e não permitem medir a duração real de cada fase. Não foi inferido que restauração, análise ou envio consumiram zero segundos.

## Confirmações técnicas e bloqueios preservados

Foram encontrados 40 planos com confirmação M1 dentro da janela, correspondentes a 32 combinações distintas de moeda/lado/minuto. São contagens por plano, potencialmente correlacionadas.

| Situação preservada no snapshot | Planos |
|---|---:|
| Marcados GATILHO_M1_ATRASADO | 13 |
| Sem marca de atraso, última avaliação financeira bloqueada | 22 |
| Financeiramente viáveis em paper | 5 |

Os 13 casos marcados como atrasados representam 32,5% das confirmações por plano. Os motivos financeiros preservados nos 22 demais bloqueados foram: 13 retorno/risco insuficiente, quatro preço fora do plano, três custo relativo elevado, um coleta não validada e um plano não atual.

Esses motivos são **a última avaliação conservada**, não um histórico imutável da primeira decisão. O código pode substituir avaliações em rodadas seguintes, inclusive quando uma coleta falha. Por isso, a tabela não demonstra que cada motivo foi a causa original da perda de oportunidade; também não permite atribuir todos os bloqueios à latência.

## Envio dos cinco alertas de entrada simulada

Os cinco eventos ENTRY associados às confirmações tiveram status SENT, sem expiração desses cinco eventos na fonte.

| Medida | Mediana | Mínimo–máximo |
|---|---:|---:|
| Confirmação técnica até inserção na fila | 88s | 34–92s |
| Confirmação técnica até resposta de sucesso do Telegram | 94s | 39–98s |
| Inserção na fila até resposta do Telegram | 6s | 5–6s |
| Idade da cotação no instante da resposta | 8s | 7–11s |
| Validade restante no instante da resposta | 26s | 22–81s |

O maior tempo observado nesses cinco casos ocorreu antes de enfileirar a mensagem. O último trecho inclui a persistência anterior ao envio; não mede apenas a rede do Telegram. As cotações desses cinco eventos estavam recentes e os envios ocorreram antes de expirar a validade. Porém, leitura no celular, reação do usuário e envio da ordem ainda ocorreriam depois desses instantes e não foram medidos.

Os alertas foram de HYPE (três), NEAR (um) e TAO (um), em modo paper. Não foi verificado se teriam atingido TP ou SL; não são operações executadas.

## Composição das notificações

Na janela foram criados 430 eventos: 419 INFO enviados, cinco ENTRY enviados e seis INFO expirados. Entre os enviados havia 317 avisos de preparação e 38 avisos de movimento, além dos cinco de entrada. Portanto, a maior parte das mensagens representa acompanhamento, não liberação financeira. Os grupos são eventos de comunicação, não trades independentes.

As seis falhas de execução tiveram coleta de preços OK e falha na etapa notify. O estado preserva quatro mensagens com erro anterior: três TimeoutError e uma URLError; duas terminaram enviadas e duas expiraram. Isso registra falhas de comunicação, mas não comprova indisponibilidade do serviço, limite de taxa, problema de credencial ou causa específica de rede. Não houve falha registrada nesses cinco eventos ENTRY.

## Custos e dados ainda não comprovados

- A configuração usa 0,06% de taxa taker como hipótese e mantém fees_verified=false. A taxa efetiva da conta do usuário não foi consultada nem confirmada.
- O avaliador live consulta o funding atual para planejamento; o replay histórico M1 utilizou funding zero. Nem o planejamento nem esse replay equivalem aos pagamentos efetivos de uma posição real.
- O diário do snapshot tem zero eventos. Não há registro de execução, fees realizadas ou funding realizado para confrontar com os alertas. Isso não afirma que o usuário não operou por fora.
- O último relatório analisou 26/26 ativos selecionados, sem diagnóstico de erro de coleta nessa rodada. Isso não significa que o universo tenha permanecido constante nas seis horas.
- O estado tem 15.356.093 bytes, 10.686 planos e 5.796 eventos de outbox; o último relatório JSON tem 2.115.128 bytes. Esse volume merece medição de restauração/persistência, mas não foi demonstrado como causa da lentidão.

## Correções propostas, em ordem

1. **Medir fases com timestamps próprios e duração monotônica:** restore,coleta/análise,persistência,notify e comandos. Os horários devem ser gravados no momento da ação e emitidos sem buffering, vinculados ao ID do run.
2. **Preservar decisões por evento:** horário de confirmação, coleta, cotação, avaliação, motivo de bloqueio, fila e resposta do Telegram. Separar decisão técnica de decisão financeira para não depender do último estado sobrescrito.
3. **Reduzir o ciclo operacional conservando gravação serializada:** depois das medidas por fase, avaliar um coletor/analisador contínuo ou otimizações da rodada, sem simplesmente ampliar a validade do sinal ou retirar a proteção de concorrência.
4. **Confirmar custos reais e executar shadow com latência observada:** taxa pessoal maker/taker, preço Last/Fair, funding e preço disponível ao usuário. Só então confrontar uma nova hipótese de estratégia.

Nenhuma dessas correções foi implantada nesta auditoria. O entregável é uma base mensurável para a próxima mudança operacional; não é aprovação de estratégia nem promessa de lucro.

## Reprodutibilidade e privacidade

O JSON de resultados contém agregados, hashes e tempos dos eventos. O JSON de fontes contém metadados sanitizados de execuções e as linhas de log necessárias; não contém texto de mensagens, IDs de chat, IDs de mensagens do Telegram, credenciais ou o estado bruto. Os hashes permitem conferir a fonte congelada na branch scanner-state.

Exemplos públicos dos logs examinados: [run 43744246111](https://github.com/VinyRhyu/mexc-futures-scanner/actions/runs/43744246111), [run 43777704408](https://github.com/VinyRhyu/mexc-futures-scanner/actions/runs/43777704408) e [falha 43773791070](https://github.com/VinyRhyu/mexc-futures-scanner/actions/runs/43773791070).

Foram verificadas a reconciliação de 361 execuções, a soma das categorias das 40 confirmações, a validade/idade de cotação nos cinco envios e o fingerprint de configuração. Não foram realizados novos backtests, capturas MEXC, envios Telegram, alterações de agendamento ou mudanças em main/scanner-state.

```sh
python -m scripts.audit_live_m1_operations --source CAPTURED_INPUT_DIR --protocol config/audit-live-m1-operations-2026-11-15.json --output results.json
```
