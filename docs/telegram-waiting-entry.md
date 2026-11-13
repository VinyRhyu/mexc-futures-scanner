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

## Verificação

Testes cobrem ausência de aviso sem rompimento, sinal de primeiro M1, direção
mais recente, conflitos empatados, idade do gatilho, deduplicação entre
formações, expiração dos avisos neutros, bloqueios financeiros, prioridade de
ENTRY, fontes inválidas e não alteração dos planos calculados. Demonstração
e replay também passam.
