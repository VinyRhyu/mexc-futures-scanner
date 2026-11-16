# Melhoria operacional: medição antes de otimização

Base de produção: `20c500deb4fbea15573dbced9eaddb6bf5839cae`.

## Etapa 1

- Tempos próprios UTC e duração monotônica para restore, scan, persistências, notify, comandos, catálogo, coleta de candles e avaliação financeira. Cada início/fim é emitido com flush e run/attempt/commit.
- Registro append-only diário em `audit/decisions-YYYY-MM-DD.jsonl`, persistido pela mesma branch serializada: transições técnicas, avaliações financeiras com preços/custos disponíveis, fila, tentativas, expiração e resposta do Telegram.
- O registro copia os dados no instante da decisão. Não depende da avaliação financeira que uma rodada posterior pode substituir. O estado e o diário financeiro existentes continuam preservados.
- Campos permitidos explicitamente; sem texto de mensagens, IDs de chat, IDs do Telegram ou credenciais. Horários de APIs preservam a unidade original; campos `signal_at`, `observed_at`, `sent_at` e `expires_at` são segundos Unix.
- A ordem de persistir antes de notificar, proteção de concorrência, validade dos sinais e filtros financeiros continuam em uso. Os eventos de confirmação são sinais simulados, não ordens.

Validação local: 303 testes aprovados, incluindo 12 novos testes de medição, privacidade, cópia imutável, falha de entrega, bloqueio de writer obsoleto e scan incompleto. Foram usados transportes falsos nos testes; não houve envio manual ao Telegram.

## Critérios para as próximas etapas

1. Capturar tempos reais antes de otimizar. Comparar a mesma fase após a mudança e informar tamanho da amostra, cobertura e falhas. Meta operacional inicial: rodada abaixo de 60 s, preservando checks de atualidade e gravação serializada; uma única rodada não comprova P95.
2. Alterar um fator por vez, com equivalência das decisões em capturas fixas quando a mudança for apenas operacional. Não aumentar a validade para ocultar atraso.
3. Antes de aprovar estratégia, fixar regras, custos, sizing e períodos. Separar desenvolvimento, validação e observação futura, pois períodos já consultados para escolher regras não são teste independente.
4. Exigir expectativa líquida positiva, perdas e drawdown documentados e repetição em janelas cronológicas. Apresentar sensibilidade a taxas/slippage/funding; uma semana positiva, taxa de acerto alta ou mais alertas não bastam.
5. Não apresentar rentabilidade hipotética como dinheiro realizado, não executar ordens e não garantir lucro. A autorização para continuar testes não torna resultados futuros positivos garantidos.

A instrumentação não muda TP, SL, alavancagem, frequência do cron ou estratégia. O crescimento dos arquivos de auditoria deverá ser medido; não há descarte de histórico nesta etapa.

## Etapa 2: recuperar somente o snapshot atual

A primeira rodada instrumentada ([43786050654](https://github.com/VinyRhyu/mexc-futures-scanner/actions/runs/43786050654)) concluiu com coleta 25/25 e nove mensagens enviadas, sem falha de envio. Durou 98,028 s: restore 66,170 s, scan 20,032 s, persistência anterior ao envio 2,516 s e notify 6,145 s. A duração de restore foi 67,5% da rodada. É uma observação, não uma estimativa de P95 ou de rentabilidade.

Única otimização: adicionar `--depth=1` ao fetch da branch scanner-state. O runner recupera o commit e arquivos atuais, sem baixar todos os snapshots históricos. O histórico remoto não é apagado; o commit-base continua conferido antes da gravação, e o push segue normal, sem force.

Validação antes de publicar: 305 testes aprovados. Os dois casos adicionais verificam que só um ancestral é acessível no checkout raso, o saldo atual é restaurado, uma nova gravação acrescenta um commit sem remover os ancestrais remotos e o histórico de decisões é restaurado e acrescido. Os testes anteriores de writer obsoleto continuam aprovados.

A medição após a implantação será comparada a esta base, informando o número de rodadas e a diferença de carga. Nenhum resultado financeiro foi inferido desses tempos.

## Resultado após a implantação

Comparação de todas as três rodadas instrumentadas anteriores com as primeiras dez execuções cronológicas do scanner no commit otimizado. Rodadas criadas de 22:29:04 até 22:38:05 de 15/11/2026, Brasília; a última rodada terminou às 22:38:38. A primeira ainda aguardou a execução antiga encerrar.

| Medida | Antes (3 rodadas) | Depois (10 rodadas) |
|---|---:|---:|
| Rodada, mediana | 103.74 s | 27.15 s |
| Recuperação do estado, mediana | 73.12 s | 1.09 s |
| Coleta e análise, mediana | 20.03 s | 19.92 s |
| Rodada, mínimo–máximo | 98.03–119.66 s | 24.77–28.84 s |
| Cobertura por rodada | 25/25 | 25/25 |

A mediana de recuperação caiu 98,5%; a da rodada caiu 73,8%. Todas as dez execuções concluíram com sucesso, ficaram abaixo de 60 s e tiveram coleta OK. Não houve cancelamento ou falha nessas dez execuções. A checagem observada atende à meta operacional na amostra. Não é uma estimativa de confiabilidade/P95 de longo prazo.

Os horários de criação do workflow e de início da rodada são diferentes. A espera mediana entre eles caiu de 59,64 s para 7,33 s; a primeira rodada otimizada ainda aguardou 68,48 s, pois havia execução antiga em andamento. Rodada abaixo de 60 s não significa sinal recebido 60 s após surgir.

As três rodadas anteriores enviaram 17 mensagens; as dez posteriores enviaram 11. São mensagens de acompanhamento/alertas, não operações. A carga variou, de modo que a redução total não deve ser atribuída exclusivamente ao fetch. A fase isolada de restore e os testes de histórico confirmam a mudança pretendida; a fase de análise ficou praticamente igual.

O registro congelado em `c5ac764592f69387beadd28072f6c7a1cb59a010` tem 83 eventos e 46.222 bytes. Seu prefixo de 57 eventos previamente capturado foi preservado byte a byte; campos privados de Telegram não estão presentes. Essa verificação de persistência foi capturada separadamente da janela completa de tempos.

Validação final local: **307 testes aprovados**. Os dois últimos exercitam o modelo M1 completo, verificando preço/horário preservados na confirmação pontual e o registro do motivo GATILHO_M1_ATRASADO na confirmação vencida.

**Situação financeira:** continua não validada. Nenhuma nova regra de TP/SL, alavancagem, prazo ou filtro foi selecionada por esses tempos. Nenhuma ordem foi executada pelo scanner. O histórico atual permitirá avaliar futuros sinais com decisões e tempos preservados; a melhoria operacional não demonstra maior taxa de acerto ou lucro.

Fontes e resultado: [medições sanitizadas](operational-rollout-source-2026-11-15.json), [agregados](operational-rollout-results-2026-11-15.json). Exemplos: [primeira rodada anterior](https://github.com/VinyRhyu/mexc-futures-scanner/actions/runs/43786050654), [primeira otimizada](https://github.com/VinyRhyu/mexc-futures-scanner/actions/runs/43786520829), [décima otimizada](https://github.com/VinyRhyu/mexc-futures-scanner/actions/runs/43787404369).

```sh
python -m scripts.summarize_operational_rollout --source docs/operational-rollout-source-2026-11-15.json --output results.json
```

## Consistência entre decisão e mensagem pendente

A revisão posterior encontrou um caso no código, reproduzido em teste: uma ENTRY pendente podia sobreviver a uma nova avaliação bloqueada enquanto a cotação anterior ainda tinha menos de 60 s. A mensagem agora é retirada antes da etapa de envio quando o plano/modalidade deixa de estar válido e financeiramente viável na rodada atual. A associação também funciona para mensagens antigas sem metadados de plano, por meio do ID de evento já existente.

A autorização retirada fica EXPIRED, conforme a política existente de expiração; não é reenviada automaticamente com o mesmo ID. Mensagens já enviadas permanecem SENT. Uma tentativa anterior com resultado ambíguo conserva a indicação da carteira para reconciliação; apenas uma indicação ainda não tentada pode ser liberada automaticamente.

Falhas parciais e totais de fonte passam a registrar os respectivos bloqueios no histórico de decisões. Os sete testes adicionais cobrem preço fora do plano com cotação antiga ainda recente, coleta parcial, falha total, formato antigo de mensagem, autorização ainda válida, mensagem já enviada e preservação de tentativa ambígua/indicação da carteira.

Validação local após essa correção: **314 testes aprovados**. A suíte local também contém testes de pesquisa mantidos na branch de auditoria, por isso sua contagem é maior que a suíte de produção no GitHub. Os dez tempos da tabela anterior foram medidos antes desta correção de consistência e permanecem identificados pelo respectivo commit; não foram substituídos por uma seleção posterior de rodadas.

Critérios técnicos, TP, SL, alavancagem, cron e modo paper permanecem os mesmos. A mudança de entrega impede que uma avaliação antiga seja apresentada como autorização atual.
