# Telegram: aguardando entrada por moeda

Mudança de apresentação solicitada em 13/11/2026. O cálculo dos sinais,
os dois sentidos da análise, TP, SL, RR mínimo 1:1, volume e confirmação
continuam iguais. O modo permanece paper.

## Acompanhamento

Os planos M1 ainda não liberados são reunidos em um aviso `AGUARDANDO ENTRADA`
por ativo, em vez de alertas individuais de LONG e SHORT para a mesma moeda.
Isso não exige escolher artificialmente uma direção antes do gatilho.

- Sem primeiro gatilho, o aviso informa a região, a direção indefinida e as
  condições alternativas de alta/baixa da consolidação mais recente.
- Com primeiro M1, mostra o lado, a faixa/SL/TP já congelados e o segundo
  fechamento/volume que faltam. Os níveis são de estudo, sem entrada liberada.
- Com confirmação técnica bloqueada pelo financeiro, informa a condição
  pendente. O aviso não recebe categoria ENTRY nem título de entrada válida.
- Havendo entrada financeiramente viável, o alerta ENTRY original tem
  prioridade e o acompanhamento pendente do mesmo ativo é retirado.

Entre formações sobrepostas, a apresentação usa no máximo o plano mais recente
de cada lado na etapa técnica mais avançada disponível. Todos os planos
permanecem na análise e no relatório completo. A seleção visual não estima
qual lado terá lucro.

## Repetição, validade e entrega

A combinação ativo/etapa/planos tem um ID estável. Mensagens já registradas não
são reenviadas em cada rodada; uma etapa ou formação diferente pode produzir
novo aviso. O limite atual de observações por rodada é preservado e os ativos
seguintes são considerados nas próximas rodadas sem ficarem presos aos IDs já
enviados.

Avisos antigos ainda pendentes do formato individual são expirados. Mensagens
já enviadas mantêm seu histórico. Avisos agrupados pendentes que foram
substituídos ou perderam seus planos ativos também expiram. O vencimento do
grupo é o menor vencimento dos planos apresentados.

Novos acompanhamentos só usam símbolos com coleta validada naquela rodada.
Planos encerrados ou fora do prazo não são apresentados como oportunidades.
As atualizações de encerramento reconhecem quais planos foram mostrados em
avisos agrupados. Nenhum plano é reaberto por causa de uma notificação.

Alertas de confirmação viável e seus IDs permanecem independentes dos avisos
de acompanhamento; não houve mudança de regras ou migração de configuração.
Metadados `watch_symbol`, `watch_stage` e `plan_ids` na outbox permitem auditar
a apresentação. `/ajuda` explica o novo formato.

## Verificação

Testes cobrem agrupamento LONG/SHORT, primeiro gatilho, bloqueio financeiro,
prioridade de ENTRY, não alteração dos planos, símbolos sem dados válidos,
deduplicação, limite por rodada, substituição de avisos, encerramento e
tamanho de mensagem. Demonstração e replay mantêm os fluxos anteriores.
