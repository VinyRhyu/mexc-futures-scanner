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
