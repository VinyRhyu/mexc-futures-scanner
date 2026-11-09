# Validação da versão 0.1

Data: 8 de novembro de 2026. Ambiente local: Python 3.12.14.

## Verificações concluídas

Revisão dos alertas: a suíte foi ampliada para **59 testes**, aprovados localmente. Os oito casos adicionais verificam preservação dos preços e do estado, distinção de bloqueio/validação, restrições da carteira, expiração sem novos gatilhos, direção SHORT, agrupamento dos planos conhecidos, prioridade de entrega e rotulagem da amostra fictícia. O workflow de testes e o envio dessa amostra são executados novamente ao publicar a revisão.

**51 testes automatizados passaram, localmente e no GitHub Actions.** Foram exercitados:

- Integridade, atualidade e fechamento de candles; agregação UTC de 2h; pivôs conhecidos somente depois da confirmação.
- Entradas antecipadas e confirmadas, direção LONG/SHORT, expiração sem renovar gatilho antigo, stop e candles ambíguos.
- Cálculo com banca de 1 USDT, quantidade mínima, arredondamento, faixa admissível, taxas, funding, profundidade, margem, limite de alavancagem e gates de uso real.
- Estado corrompido, alterações de configuração, diário idempotente, contabilização de taxas, horário real separado do registro e pausa após stop.
- Entrega simulada, expiração de mensagens, ausência de segredos, repetição e remoção de tokens de mensagens de erro.
- Identificação do chat privado do Telegram: filtragem de grupos, preservação de atualizações e ocultação de token em erros. Foram usados transportes simulados, sem consultar um bot real.
- Persistência entre checkouts usando um repositório Git bare temporário; rejeição de gravação concorrente com base antiga.
- Tratamento de resposta HTML como falha de fonte; nenhuma ordem é enviada.

Os seis arquivos de workflow foram analisados como YAML. Os arquivos Python passaram pela análise de sintaxe e os arquivos TOML foram carregados. O workflow de testes executou a suíte, a demonstração e o replay na infraestrutura do GitHub. A identificação de chat e o teste de mensagem do Telegram ainda não foram executados com credenciais reais.

## Demonstração e replay

A demonstração usa exclusivamente `DEMO_USDT`, com candles e livro sintéticos. Foram obtidas modalidades antecipada e confirmada classificadas como financeiramente viáveis para saldo de 1 USDT dentro das hipóteses configuradas. Isso verifica os cálculos nesses exemplos; não prova que a mesma condição estará disponível na MEXC.

O replay exploratório da demonstração também foi executado. Não foi calculada nem validada uma taxa de acerto em mercado. Não há estimativa comprovada de tempo para atingir 100 ou 1.500 USDT.

Comandos de reprodução:

```bash
python -m unittest discover -s tests -v
python -m mexc_scanner demo --output reports/demo
python -m mexc_scanner replay reports/demo/snapshot.json --output reports/demo-replay
```

## Tentativa com dados reais

Foi executado:

```bash
python -m mexc_scanner scan --init --limit 5 --state reports/live-probe/state.json --output reports/live-probe
```

Resultado: **FALHA**, cobertura `0/0`, nenhum plano. A fonte retornou conteúdo não JSON neste ambiente. O scanner registrou o diagnóstico e não criou sinais a partir dessa resposta. Não é possível concluir, desse teste, que a MEXC está indisponível para outros ambientes.

## Validação no GitHub

O projeto foi publicado no repositório privado `VinyRhyu/mexc-futures-scanner`, separado de `altcoin-scanner`.

- [Testes automáticos](https://github.com/VinyRhyu/mexc-futures-scanner/actions/runs/42536223801): 51 testes, demonstração e replay concluídos com sucesso.
- [Teste da integração pública e persistência](https://github.com/VinyRhyu/mexc-futures-scanner/actions/runs/42536223700): coleta inicial de cinco contratos e rodadas de até 50 contratos, sem Telegram.
- A MEXC respondeu em JSON corretamente a partir do GitHub. Foram observadas rodadas com cobertura **29/29 contratos elegíveis**, sem diagnósticos de falha de dados. O limite é de até 50, preservando os filtros de liquidez e classificação.
- O estado foi gravado na branch `scanner-state`, recuperado em pasta nova e processado novamente. A carteira permaneceu com saldo registrado de 1 USDT, nenhuma posição e nenhum registro de operação. Os dados de mercado e planos são reais; a carteira permanece em simulação.

A falha local de acesso à fonte, descrita acima, continua sendo um resultado daquele ambiente e não invalida a coleta observada no GitHub.

## Integrações ainda pendentes

- Configuração de `TELEGRAM_BOT_TOKEN` e `TELEGRAM_CHAT_ID` e recebimento real de uma mensagem de teste.
- Conferência de lotes, timestamps, volume financeiro, livro e parâmetros de stop com a interface da corretora.
- Acompanhamento prospectivo das duas estratégias e modalidades, inclusive sinais descartados, custos e entradas que expiraram.
- Verificação da taxa pessoal, regras da conta e comportamento do gatilho de stop antes de considerar modo real.

O agendamento está condicionado a `SCANNER_ENABLED=true`. Publicar os arquivos não ativa as coletas periódicas automaticamente. Nenhuma operação de mercado ou mensagem real no Telegram foi executada nesta validação.
