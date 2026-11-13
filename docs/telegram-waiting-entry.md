# Telegram: movimento detectado

A apresentação foi ajustada em 13/11/2026 para avisar quando o rompimento já
foi observado, em vez de anunciar toda consolidação como possível entrada.
A análise dos dois lados, TP, SL, RR mínimo 1:1, volume e confirmação continuam
iguais. O modo permanece paper; nenhum primeiro gatilho libera uma entrada.

## Quando chega o aviso

- MOVIMENTO DETECTADO • ALTA (LONG) ou BAIXA (SHORT) exige um primeiro
  candle M1 fechado além do gatilho da região monitorada pelo modelo atual.
- O aviso mostra horário do candle da etapa, referência do primeiro gatilho,
  faixa/SL/TP em estudo e a confirmação que ainda falta.
- Se a confirmação técnica já foi identificada, mas o financeiro bloqueou a
  entrada, a condição pendente aparece explicitamente no aviso informativo.
- Planos sem primeiro rompimento continuam na análise e nos relatórios, mas
  não geram mais acompanhamentos neutros de LONG/SHORT no Telegram.
- Uma entrada confirmada e financeiramente viável mantém seu próprio alerta
  ENTRY, com prioridade sobre o acompanhamento do mesmo ativo.

O movimento é o rompimento das regiões monitoradas pela estratégia. Não é
um detector de toda oscilação do mercado nem de eventos anteriores ao primeiro
fechamento M1. O candle observado pode ter revertido após fechar; o aviso não
afirma que o preço atual ainda seja igual à referência.

## Direção, repetição e validade

Cada ativo apresenta somente a direção do gatilho observado mais recente.
Entre contextos no mesmo horário, considera-se a formação mais recente e a
etapa técnica disponível. Se ainda houver contextos opostos exatamente
empatados, não é emitida uma direção arbitrária. Todos os planos continuam
sendo processados normalmente e podem aparecer no relatório completo.

O ID do aviso usa ativo/lado/horário do movimento/etapa. Formações sobrepostas
do mesmo evento não produzem vários avisos; uma mudança de etapa ou outro
movimento pode gerar atualização. O limite de observações por rodada permanece.

O gatilho precisa ter menos de 120s no momento da geração do aviso, e a validade
da mensagem também termina no máximo 120s após o horário observado. Mensagens
pendentes antigas, neutras, substituídas ou sem coleta validada são expiradas.
Na falha da fonte, acompanhamentos pendentes não são entregues. Mensagens já
enviadas mantêm seu histórico; encerramentos continuam sendo reconhecidos.

O cron e a fila do GitHub podem atrasar a entrega. Não há garantia de notificar
todo primeiro candle: uma rodada pode já receber a confirmação ou invalidação.
O processamento continua por candles fechados, sem promessa de alerta intrabar.

## Separação da entrada

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

Testes cobrem ausência de aviso sem rompimento, sinal de primeiro M1, direção
mais recente, conflitos empatados, idade do gatilho, deduplicação entre
formações, expiração dos avisos neutros, bloqueios financeiros, prioridade de
ENTRY, fontes inválidas e não alteração dos planos calculados. Demonstração
e replay também passam.
