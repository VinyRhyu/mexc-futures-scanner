# Validação da versão 0.1

Data: 8 de novembro de 2026. Ambiente local: Python 3.12.14.

## Verificações concluídas

**48 testes automatizados passaram.** Foram exercitados:

- Integridade, atualidade e fechamento de candles; agregação UTC de 2h; pivôs conhecidos somente depois da confirmação.
- Entradas antecipadas e confirmadas, direção LONG/SHORT, expiração sem renovar gatilho antigo, stop e candles ambíguos.
- Cálculo com banca de 1 USDT, quantidade mínima, arredondamento, faixa admissível, taxas, funding, profundidade, margem, limite de alavancagem e gates de uso real.
- Estado corrompido, alterações de configuração, diário idempotente, contabilização de taxas, horário real separado do registro e pausa após stop.
- Entrega simulada, expiração de mensagens, ausência de segredos, repetição e remoção de tokens de mensagens de erro.
- Persistência entre checkouts usando um repositório Git bare temporário; rejeição de gravação concorrente com base antiga.
- Tratamento de resposta HTML como falha de fonte; nenhuma ordem é enviada.

Os quatro arquivos de workflow foram analisados como YAML. Os arquivos Python passaram pela análise de sintaxe e os arquivos TOML foram carregados. Isso não equivale a executar os workflows na infraestrutura do GitHub.

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

## Integrações ainda pendentes

- Publicação no repositório separado e execução efetiva dos workflows no GitHub.
- Primeira coleta com resposta válida da MEXC, inicialmente em cinco contratos; conferência de lotes, timestamps, volume financeiro e livro com a interface da corretora.
- Configuração de `TELEGRAM_BOT_TOKEN` e `TELEGRAM_CHAT_ID` e recebimento real de uma mensagem de teste.
- Acompanhamento prospectivo das duas estratégias e modalidades, inclusive sinais descartados, custos e entradas que expiraram.
- Verificação da taxa pessoal, regras da conta e comportamento do gatilho de stop antes de considerar modo real.

O agendamento está condicionado a `SCANNER_ENABLED=true`. Publicar os arquivos não ativa as coletas periódicas automaticamente. Nenhuma operação de mercado ou mensagem real no Telegram foi executada nesta validação.
