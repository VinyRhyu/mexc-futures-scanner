# Validação prospectiva de momentum — 30 dias

Protocolo: `config/momentum-forward-v1-2026-11-16.json`. Código e parâmetros são congelados antes dos sinais avaliados. Este acompanhamento não executa ordens, não acessa conta da exchange e não envia Telegram.

## Janela e carteiras

- Primeiro congelamento: **16/11/2026 às 21h de Brasília**, referente ao fechamento de 17/11 00h UTC.
- Horário previsto de entrada simulada: **22h de Brasília**, uma hora após o sinal.
- Trinta decisões, até o sinal de 15/12 às 21h, com entrada de 15/12 às 22h; a última posição pode permanecer até 16/12 às 22h.
- Dados finais disponíveis após o fechamento H1 de **16/12 às 23h de Brasília**. Esse é o primeiro checkpoint, não uma promessa de validação.
- Duas políticas: risco fixo de 1% e proteção 2%/0,5%, com redução após queda de 5% desde o pico e restauração quando a queda recuar a 2,5%.
- Para cada política há uma carteira de custos-base e uma de custos elevados. Cada uma começa com **US$ 100**, margem isolada de **10×**, uma posição global por vez. São quatro carteiras hipotéticas independentes.

## Duas camadas de evidência

**Sinais prospectivos e replay H1 em simulação.** Durante a hora anterior à entrada prevista, o sistema congela candidatos, níveis, escores, direção do Bitcoin e atualizações diárias do stop. O evento é publicado com timestamp e hash antes de observar seu desfecho. Nas verificações posteriores, preços Last/Fair H1 e funding efetivamente observados alimentam um replay com esses eventos congelados. A abertura H1, spread, slippage e saídas continuam sendo hipóteses de execução, não comprovantes de ordens preenchidas.

**Observações de preço no horário.** Na janela de até cinco minutos após 22h, são capturados bid, ask, timestamp e livros dos três candidatos tecnicamente mais fortes. O diário compara o preço de referência da simulação com a cotação efetivamente observada. Uma observação atrasada ou ausente fica marcada; não se busca depois uma cotação histórica para preencher a lacuna. O livro observado não prova fila, disponibilidade futura ou preenchimento.

Uma cotação observada não transforma automaticamente o replay em uma carteira de execução real. O relatório preserva `execution_validated=false` e `approved_for_production=false`.

## Integridade e persistência

O diário usa exclusivamente a branch **`research/momentum-forward-state-v1`**. Os arquivos `state.json`, `journal.jsonl`, `wallets.json`, `status.json` e `status.md` ficam nessa branch, junto de preços por dia, decisões e cotações. Não há escrita em `main` ou `scanner-state`.

O código e os parâmetros têm hashes fixados na inicialização. Se forem alterados, a rodada falha em vez de mudar silenciosamente o teste. As regras de contrato iniciais são fixadas; mudanças posteriores bloqueiam novas entradas do símbolo afetado. Preços e funding guardam a primeira observação: revisões são registradas, sem substituir o passado. O diário tem cadeia de hashes e cada conjunto de dados possui checksum.

Dias sem congelamento tempestivo permanecem perdidos. Posições abertas continuam abertas nos relatórios intermediários. Operações encerradas precisam permanecer idênticas como prefixo do diário seguinte. O salvamento exige o mesmo head remoto recuperado e usa avanço normal de histórico; uma gravação concorrente é rejeitada.

## Verificações e checkpoint

O monitor verifica por hora para congelar os sinais antes do desfecho, observar a janela de preço e atualizar o replay. Resumos diários são solicitados para depois da atualização das 23h de Brasília; falhas relevantes devem ser reportadas antes. O horário de início dos serviços pode variar: qualquer atraso aparece nas métricas de cobertura, sem atribuir preenchimentos ideais.

O primeiro checkpoint exige, para a política avaliada:

- Pelo menos 29 dos 30 dias congelados antes da entrada.
- Pelo menos 20 posições encerradas por carteira.
- Cobertura de cotações válidas de pelo menos 95%, inclusive para os ativos selecionados na simulação.
- Retorno positivo e queda máxima H1 de até 10% nos dois cenários de custo.
- Nenhuma liquidação simulada, nenhuma revisão de fonte e posições encerradas no fim.

Faltar amostra ou cobertura produz resultado inconclusivo. Esses critérios são uma triagem de pesquisa; não medem significância após seleção de estratégias nem substituem taxas reais da conta, dados de execução e observação de mais regimes. Nenhuma política será promovida automaticamente ao bot.

## Operação

O workflow `.github/workflows/momentum-forward-paper.yml` é acionado apenas na branch de pesquisa por atualização do protocolo, código dedicado ou `config/momentum-forward-trigger.json`. O monitor usa esse gatilho; não depende de colocar um agendamento na branch de produção.

Verificação local:

```bash
python -m unittest tests.test_forward_momentum tests.test_forward_state_branch -v
```

Em um ambiente autorizado com acesso público à MEXC, o runner pode ser executado com um diretório isolado:

```bash
python -m scripts.forward_momentum \
  --protocol config/momentum-forward-v1-2026-11-16.json \
  --directory reports/momentum-forward-state
```

Esse comando não faz persistência remota por conta própria. O workflow restaura e salva a branch exclusiva através de `scripts.forward_state_branch.py`, sem force-push.

## Inicialização verificada em 16/11

A [primeira rodada no GitHub Actions](https://github.com/VinyRhyu/mexc-futures-scanner/actions/runs/43879113295) concluiu testes, coleta, gravação e publicação do diário com sucesso. O [estado atual do acompanhamento](https://github.com/VinyRhyu/mexc-futures-scanner/blob/research/momentum-forward-state-v1/status.md) iniciou em WARMUP, com quatro carteiras de US$ 100 e zero operações. Isso verifica a instalação; não constitui resultado de desempenho prospectivo.

O monitor foi ativado com verificações horárias a partir de 16/11 às 11h de Brasília. O resumo diário é solicitado para a verificação das 23h; os horários dos serviços podem variar e atrasos são registrados. O agendamento termina após o primeiro checkpoint de 16/12 às 23h.
