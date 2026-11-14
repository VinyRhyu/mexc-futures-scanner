# Telegram: preparação e movimento detectado

A apresentação voltou a incluir planos em preparação em 14/11/2026, antes
do primeiro rompimento. Eles são distintos dos avisos de movimento detectado.
A análise dos dois lados, TP, SL, RR mínimo 1:1, volume e confirmação continuam
iguais. O modo permanece paper; nenhum primeiro gatilho libera uma entrada.

## Quando chega o aviso

- PLANO EM PREPARAÇÃO • AGUARDANDO GATILHO mostra a região e os limiares
  condicionais do modelo. LONG e SHORT da formação mais recente são agrupados
  em uma única mensagem por ativo: são cenários alternativos, não duas entradas.
  TP, SL e percentuais só são apresentados após a definição no primeiro gatilho.
  A preparação mantém seu prazo original, sem o limite de 60s do primeiro M1.
- MOVIMENTO DETECTADO • ALTA (LONG) ou BAIXA (SHORT) exige um primeiro
  candle M1 fechado além do gatilho da região monitorada pelo modelo atual.
- O aviso mostra horário do candle da etapa, referência do primeiro gatilho,
  faixa/SL/TP em estudo e a confirmação que ainda falta.
- Se a confirmação técnica já foi identificada, mas o financeiro bloqueou a
  entrada, a condição pendente aparece explicitamente no aviso informativo.
- Planos sem primeiro rompimento voltam a gerar acompanhamento no Telegram.
  Apenas ativos com coleta validada nesta rodada podem gerar preparação.
- Uma entrada confirmada e financeiramente viável mantém seu próprio alerta
  ENTRY, com prioridade sobre o acompanhamento do mesmo ativo.

O movimento é o rompimento das regiões monitoradas pela estratégia. Não é
um detector de toda oscilação do mercado nem de eventos anteriores ao primeiro
fechamento M1. O candle observado pode ter revertido após fechar; o aviso não
afirma que o preço atual ainda seja igual à referência.

## Direção, repetição e validade

Quando existe movimento elegível, cada ativo apresenta somente a direção
do gatilho observado mais recente, com prioridade sobre a preparação.
Um movimento envelhecido não é substituído por preparação do lado oposto.
Entre contextos no mesmo horário, considera-se a formação mais recente e a
etapa técnica disponível. Se ainda houver contextos opostos exatamente
empatados, não é emitida uma direção arbitrária. Todos os planos continuam
sendo processados normalmente e podem aparecer no relatório completo.

O ID do aviso usa ativo/lado/horário do movimento/etapa. Formações sobrepostas
do mesmo evento não produzem vários avisos; uma mudança de etapa ou outro
movimento pode gerar atualização. O limite de observações por rodada permanece.
Preparações usam um ID próprio baseado nos planos da formação selecionada:
não se repetem a cada coleta; uma nova formação pode gerar novo aviso.
Uma mudança de etapa substitui a preparação pendente do ativo. Histórico de
envios, encerramentos e planos calculados são preservados.

O aviso do primeiro M1 só é gerado e válido nos 60s seguintes ao candle:
depois disso, o segundo M1 já deveria estar disponível para validação. Alertas
de confirmação técnica mantêm até 120s. Isso não altera a janela de nova
entrada do modelo, que continua em 120s após a confirmação. Mensagens
pendentes antigas, substituídas ou sem coleta validada são expiradas.
Na falha da fonte, acompanhamentos pendentes não são entregues. Mensagens já
enviadas mantêm seu histórico; encerramentos continuam sendo reconhecidos.

No envio, ENTRY tem prioridade, seguido por movimento recente, preparação e
resumos/atualizações. Alertas não ficam atrás de resumos antigos.
O horário é rechecado antes de cada envio, para que o tempo gasto entregando
mensagens anteriores não permita enviar um alerta que já venceu. O registro
de envio usa o horário observado após a resposta do Telegram.

O cron e a fila do GitHub podem atrasar a entrega. Não há garantia de notificar
todo primeiro candle: uma rodada pode já receber a confirmação ou invalidação.
O processamento continua por candles fechados, sem promessa de alerta intrabar.

## Separação da entrada

O primeiro aviso destaca `AINDA SEM CONFIRMAÇÃO` no título. Nas atualizações,
o motivo efetivo é informado: volume insuficiente, perda do rompimento,
prazo de nova entrada encerrado ou toque em alvo/stop. Expiração da janela
para nova entrada não é uma ordem de encerrar uma posição já aberta. Toque
no alvo de um plano observado não comprova lucro de uma operação executada.

O alerta é categoria INFO, com texto explícito de que não existe entrada
liberada. A regra de entrada continua exigindo o segundo fechamento M1,
volume do segundo de pelo menos 50% do primeiro e aprovação dos filtros
financeiros. Nenhuma configuração de risco ou cálculo de estratégia foi mudado.

Metadados watch_symbol, watch_stage, movement_at, movement_side e plan_ids
na outbox permitem auditar a apresentação. Não há migração de configuração
ou reinicialização de saldo/diário. /ajuda explica o formato.

## Percentuais de TP e SL

Nos avisos de movimento, os percentuais principais do TP e SL são um cenário
bruto indicativo em 10x, ainda sem validação de custos, margem e liquidação.
A base é o primeiro gatilho e a variação sem alavancagem aparece separada.
Os sinais seguem o lado da operação: TP abaixo da entrada de SHORT é positivo;
SL acima dela é negativo. Os preços técnicos não são deslocados.

Nas entradas viáveis, os percentuais ao lado do TP e SL mostram o ROI líquido
estimado sobre a margem, usando a alavancagem proposta (piso 10x, teto 20x):
ganho líquido estimado dividido pela margem, e perda líquida estimada dividida
pela margem, com sinal negativo para o SL. Esses valores já usam os custos
assumidos pelo avaliador e são distintos da variação sem alavancagem e do
retorno sobre o saldo total. A referência do movimento sem alavancagem é o pior
preço admissível do financeiro. Sem margem validada, não é inventado um ROI
líquido. A alavancagem muda a margem necessária; a quantidade e o risco em
USDT continuam definidos pelo plano e não aumentam para inflar o percentual.

## Verificação

Testes verificam simetria LONG/SHORT, denominador da pior entrada, separação
entre margem e saldo, referências inválidas, pequenas variações e preservação
dos níveis e do estado.

Testes cobrem preparação sem rompimento, sinal de primeiro M1, direção
mais recente, conflitos empatados, idade do gatilho, deduplicação entre
formações, substituição das preparações pendentes, bloqueios financeiros, prioridade de
ENTRY, fontes inválidas e não alteração dos planos calculados. Demonstração
e replay também passam.
