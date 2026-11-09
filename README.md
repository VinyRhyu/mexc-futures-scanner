# MEXC Futures Scanner

Scanner de futuros perpétuos USDT da MEXC, com regras programadas, planos persistentes e alertas no Telegram. **As ordens são manuais. O projeto começa em simulação.**

A primeira versão identifica continuação após correção e rompimento de consolidação, para LONG e SHORT. Cada padrão tem modalidades antecipada e confirmada independentes. Um sinal técnico continua visível quando o lote, o preço ou os custos não permitem executá-lo com o saldo informado.

## O que está implementado

- Coleta pública de contratos, valor financeiro negociado, candles, ticker, livro e funding.
- Candles fechados de 15m/1h e agregação de 2h alinhada a UTC.
- Pivôs com horário de confirmação, sem usar candles futuros na decisão.
- Planos com níveis congelados, faixa de entrada, invalidação e prazos por fase.
- Dimensionamento em contratos, custo estimado, retorno/risco no pior preço, margem e limite de 20x.
- Estado e fila de mensagens persistidos na branch `scanner-state`; proteção contra gravação de estado antigo.
- Alertas, resumo diário e diário de execução manual.
- Testes automáticos, demonstração sintética e replay exploratório.

Sem integração para colocar, alterar ou cancelar ordens. Não é necessário fornecer chave de negociação da MEXC.

## Executar localmente

Requisito: **Python 3.11 ou posterior**. O scanner usa somente a biblioteca padrão; não precisa instalar pacotes para os comandos abaixo.

Na pasta do projeto:

```bash
python -m unittest discover -s tests -v
python -m mexc_scanner demo
python -m mexc_scanner replay reports/demo/snapshot.json --output reports/demo-replay
```

`demo` usa o ativo fictício `DEMO_USDT`, não consulta a MEXC e não envia mensagens. Seus resultados não são desempenho de mercado.

Para consultar a fonte real e analisar inicialmente até cinco contratos:

```bash
python -m mexc_scanner scan --init --limit 5
```

`--init` cria um estado novo somente se ele não existir, e somente em modo paper. Um estado existente corrompido nunca é reinicializado automaticamente.

Saídas: `.scanner-state/latest/report.md`, `report.json` e `snapshot.json`. A captura de candles é temporária e não é regravada na branch de estado a cada rodada.

## Primeiro teste no GitHub

1. Criar um repositório separado chamado `mexc-futures-scanner` e enviar os arquivos preservando as pastas, inclusive `.github/workflows`. Se receber o projeto em ZIP, extraí-lo antes: subir apenas o ZIP não instala os workflows.
2. Manter `main` como branch padrão. O workflow **Testes** executa testes sem rede, demonstração e replay sintéticos. A publicação de `integration-smoke.yml` também inicia **Testar coleta MEXC**: consulta cinco contratos e, se passar, executa duas rodadas de até 50 contratos para verificar a persistência na branch de estado. Todos esses testes usam simulação e não enviam Telegram, mesmo que existam segredos configurados no repositório. Esse workflow também pode ser iniciado manualmente.
3. Em **Actions → Scanner MEXC → Run workflow**, selecionar `5`. Esse teste consulta a API real e publica o diagnóstico no resumo da execução. Funciona mesmo sem Telegram configurado; nesse caso o envio fica identificado como não configurado.
4. Conferir a branch `scanner-state`, o resumo, a cobertura e eventuais motivos de falha. Não considerar uma execução com falha da fonte como teste de mercado bem-sucedido.
5. Configurar os dois segredos do Telegram e executar **Testar Telegram**.
6. Somente depois de conferir as primeiras rodadas, criar a variável de Actions `SCANNER_ENABLED` com valor `true`. O agendamento passará a tentar executar nos minutos 02, 17, 32 e 47 de cada hora, analisando até 50 contratos.

Para publicar a partir da pasta extraída usando Git e GitHub CLI, após autenticar sua própria sessão com `gh auth login`:

```bash
git init -b main
git add .
git commit -m "Implement scanner and paper validation"
gh repo create VinyRhyu/mexc-futures-scanner --private --source=. --remote=origin --push
```

Esses comandos são para um repositório novo e ainda inexistente. Se criar o repositório vazio pela interface do GitHub, usar o endereço dele como remote e fazer push, sem repetir `gh repo create`. O repositório anterior `altcoin-scanner` não é alterado.

Os agendamentos do GitHub podem atrasar ou ser descartados. A execução manual permanece disponível. O scanner reconcilia os candles recebidos e não renova a validade de um gatilho antigo por tê-lo detectado tarde.

O processamento em runners padrão de repositórios públicos tem condições de gratuidade; repositórios privados têm franquias e limites da conta. Verificar o consumo antes de ativar o agendamento. Os workflows vêm com o agendamento condicionado à variável, para que publicar o código não inicie 96 coletas diárias automaticamente.

## Telegram

Criar o bot pelo [BotFather oficial](https://t.me/BotFather), abrir a conversa com o próprio bot e enviar `/start`.

Configurar em **Settings → Secrets and variables → Actions**:

| Segredo | Conteúdo |
| --- | --- |
| `TELEGRAM_BOT_TOKEN` | Token fornecido pelo BotFather |
| `TELEGRAM_CHAT_ID` | Identificador do chat que receberá os avisos |

Inserir os valores diretamente nos segredos do GitHub; não adicioná-los aos arquivos do projeto ou às mensagens de suporte. O workflow **Testar Telegram** envia uma mensagem de conexão ao destino configurado.

Se ainda não souber seu `TELEGRAM_CHAT_ID`, salve primeiro somente `TELEGRAM_BOT_TOKEN`, envie `/start` ao seu bot e execute **Actions → Identificar chat Telegram → Run workflow**. No resumo aparecerá o ID da conversa privada. Salve-o como segundo segredo e execute **Testar Telegram**. A identificação funciona somente em repositório privado; não imprime token, nome nem texto das mensagens e não escolhe automaticamente entre vários chats.

O bot é inicialmente um canal de saída. Ele não interpreta respostas de operação nesta versão. Registrar a execução pelo workflow de diário.

### Formato dos alertas

O início da mensagem informa a ação possível: **possível entrada / aguardar gatilho**, **entrada bloqueada**, **gatilho válido para simular**, ou **apenas acompanhamento**. Simulação e uso real são identificados separadamente. Cada alerta destaca ativo e direção, modalidade, faixa de entrada, stop, alvo e prazo. Quando viável, apresenta quantidade, margem, alavancagem, risco em USDT e porcentagem da banca, ganho projetado e custos.

Preços executáveis preservam a precisão original. Somente regiões de atenção ainda sem gatilho aparecem aproximadas (`≈`); valores financeiros estimados e percentuais são arredondados para leitura. Os cálculos e os motivos completos continuam disponíveis no relatório JSON.

Encerramentos são agrupados em uma atualização curta, somente para planos já notificados (ou com tentativa de entrega ambígua). Indicações atuais têm prioridade de envio sobre acompanhamentos e resumos. IDs dos planos permanecem visíveis para uso no diário. Uma pausa ou indicação pendente nunca é apresentada com o título de entrada validada.

**Testar Telegram** agora envia uma amostra com o ativo fictício `DEMO_USDT`, explicitamente marcada como **EXEMPLO FICTÍCIO — NÃO OPERAR**. Pode ser iniciado manualmente e também roda quando o formato ou seu script de amostra é atualizado em `main`; executa os testes antes de enviar uma única demonstração. Para visualizar sem enviar:

```bash
python -m scripts.telegram_preview
```

## Diário de operações

Em **Actions → Registrar operação → Run workflow**, escolher:

| Ação | Uso |
| --- | --- |
| `enter` | Registrar entrada realmente executada, ID, modalidade, preço, número de contratos e taxa em USDT |
| `skip` | Informar que a indicação não foi executada |
| `close` | Registrar encerramento total, preço, taxa e funding líquido pago (negativo se recebido) |
| `balance` | Conciliar saldo quando não houver posição/indicação pendente; a diferença não é contabilizada como lucro |

O workflow usa o identificador da execução como chave de idempotência: repetir a mesma execução não duplica o registro. Os preços e as quantidades são fatos informados pelo usuário; o scanner não confirma fills na corretora.

Informar `executed_at` com data, hora e fuso da execução, por exemplo `2026-11-08T20:00:00-03:00`. Se ficar vazio, o horário do registro será usado e essa hipótese ficará identificada no diário. Um registro tardio com horário real informado preserva a hora da operação; a pausa é contada a partir do encerramento informado.

Uma posição registrada impede outra posição no mesmo diário. Em modo real, uma indicação sem registro permanece pendente mesmo quando o plano expira. Um resultado de entrega ambíguo não é interpretado como prova de não execução.

## Configuração e limites iniciais

O arquivo `config/default.toml` começa com saldo de **USDT 1**, perda planejada de até **30%**, ganho desejado de **60%**, retorno/risco líquido mínimo de 2 e alavancagem limitada a **20x**. São hipóteses iniciais; não demonstram rentabilidade.

A taxa padrão de 0,06% por execução é uma **hipótese de simulação**, não a taxa pessoal da conta. Taxas de execução manual devem ser verificadas antes de avaliar uso real. O programa não afasta o alvo ou aproxima o stop apenas para viabilizar o saldo.

O dimensionamento reduz a faixa de entrada quando necessário para preservar RR, quantidade permitida, risco e custo. A quantidade escolhida é a menor que projeta o ganho desejado dentro dos limites. O mínimo de lote pode impedir determinadas combinações, mas um sinal técnico válido não desaparece do relatório por essa razão.

Há duas janelas: até 30 minutos para a preparação gerar o primeiro gatilho e até 30 minutos para entrada a partir desse gatilho. A confirmação posterior e uma consulta tardia não reiniciam a janela. Esse esclarecimento corrige um conflito encontrado no teste da especificação; veja [as notas da implementação](docs/IMPLEMENTATION_NOTES.md).

## Estado, privacidade e continuidade

Os workflows de coleta e diário compartilham o mesmo grupo de concorrência. Recuperam o estado, processam, fazem push do estado, enviam as mensagens pendentes e persistem as confirmações de entrega. Uma falha ao salvar impede o envio de novas mensagens daquela transação.

O Telegram não fornece entrega exatamente uma vez para esse fluxo. Uma resposta ambígua pode levar a repetição, sempre com o mesmo ID. Mensagens de entrada com cotação antiga são descartadas antes do envio.

Branches de repositórios públicos são públicas. Manter apenas simulação/dados públicos em um repositório público. O código bloqueia diário e modo real sem a confirmação de destino privado `REPOSITORY_IS_PRIVATE=true`; isso não cria privacidade por si só, apenas verifica a configuração declarada.

Uma mudança de configuração altera sua identificação e interrompe a leitura automática do estado antigo. Revisar e migrar deliberadamente; não apagar `scanner-state` para esconder resultados ou reiniciar uma banca perdida.

## Testes de desempenho

`replay` é exploratório: usa OHLC, regras do contrato da captura e hipóteses de spread, profundidade e funding. Não trata livro ou taxas atuais como se fossem dados históricos observados. Mantém quatro carteiras separadas (duas estratégias × duas modalidades), uma posição por carteira e a pausa definida. Não somar seus resultados como se fossem uma única banca.

Quando um candle contém stop e alvo, o cenário pessimista usa o stop primeiro e marca a ambiguidade. A queda reportada é a do saldo realizado, não uma medição completa de todo o caminho intraposição. Uma captura não substitui teste fora da amostra e acompanhamento prospectivo.

Consulte [o relatório de validação](docs/VALIDATION.md) para saber o que foi executado e o que ainda depende de integração real. Não há prazo validado para alcançar US$ 100.

## Referências

- [Especificação de planejamento](docs/SPECIFICATION-v0.1.md)
- [MEXC Futures API](https://www.mexc.com/api-docs/futures/integration-guide)
- [GitHub Actions: agendamento](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)
- [GitHub Actions: cobrança e franquias](https://docs.github.com/en/actions/concepts/billing-and-usage)
- [Telegram Bot API](https://core.telegram.org/bots/api)

### Comando `/ajuda` no Telegram

Envie `/ajuda` em conversa privada com o bot. O comando é consultado ao fim de cada rodada agendada do scanner (até cerca de 15 minutos, mais eventuais atrasos). A resposta explica classificações, risco e meta projetada. Somente o `TELEGRAM_CHAT_ID` configurado recebe a resposta. O cursor das mensagens fica na branch `scanner-state` para evitar respostas repetidas. O bot não recebe comandos em tempo real e não executa ordens.
