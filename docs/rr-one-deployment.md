# Ativação de mínimo líquido 1:1 em paper

Alteração solicitada em 13/11/2026 após a comparação histórica de 2, 1,5 e 1.
O workflow passa a usar `minimum_rr="1"` de `config/default.toml`.

- Mantidos TP técnico, SL, dois fechamentos M1 e retenção de volume de 50%.
- Mantida a validade máxima de 120s após a confirmação, com cotação, livro,
  custos, lote, margem e liquidação reavaliados antes de liberar o plano.
- Risco planejado continua limitado a 10% do saldo, teto de 20x, em modo paper.
- Sem alvo fixo de 1R e sem lucro percentual mínimo. Planos com RR maior seguem
  elegíveis. A biblioteca sem arquivo continua com padrão conservador 2.
- `/ajuda` explica o mínimo atual e os relatórios mostram `minimum_rr`.

## Migração

A rodada aplica a opção explícita `--migrate-rr-one` ao carregar o estado.
Ela só aceita a configuração paper anterior que difira exclusivamente por
`minimum_rr="2"`; outras mudanças continuam bloqueadas. É idempotente.

Wallet, posição registrada, diário, preços dos planos e cursores são mantidos.
Planos encerrados não são reabertos. Resultados históricos e mensagens enviadas
são mantidos. Avaliações financeiras de planos ativos são limpas para nova
checagem e mensagens financeiras antigas ainda pendentes expiram. O evento
fica registrado em `config_migrations` com fingerprints anterior e novo.

## Verificação

- Testes completos de configuração, finanças, estados, entrega e estratégias.
- Casos LONG/SHORT que eram rejeitados por RR2 passam por RR1, com SL/TP
  preservados, risco até 10% e mesmas travas de uso real.
- Migração exercitada em cópia do estado consultado: 6.744 planos e 3.409
  mensagens enviadas preservados; wallet, posição, diário e cursores idênticos.
- Demonstração sintética e replay executados sem mensagens ou ordens.

Esta ativação não transforma confirmações paper em entradas validadas para
uso real. Na coleta histórica já explorada, 1:1 teve mais planos e menor
assertividade; isso não prevê o resultado das próximas operações. O agendamento
existente permanece, sujeito à latência e aos limites do provedor.
