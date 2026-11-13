# Piso de alavancagem de 10x em paper

Alteração solicitada em 13/11/2026. Configuração ativa:
`minimum_leverage=10`, `max_leverage=20`, `minimum_rr="1"`, `mode="paper"`.

O dimensionamento continua usando risco planejado até 10% do saldo, com custos,
lote e quantidades validados. Depois de definir a posição, o avaliador usa o
maior entre 10x e a alavancagem necessária para caber na margem disponível.
Teto global, limite do contrato, tier e distância de segurança da liquidação
continuam obrigatórios. Se não passar, a entrada é bloqueada; SL/TP não mudam.

Para a mesma quantidade, ganho, perda e custos estimados em USDT são os mesmos.
A margem menor muda o ROI percentual sobre a margem. Não é uma melhora na
assertividade nem um aumento do lucro em dinheiro da mesma posição.

## Telegram

- Movimento detectado: os percentuais principais são um cenário bruto
  indicativo em 10x. Não são ROI líquido aprovado nem validação de execução.
- Entrada viável: os percentuais ao lado dos níveis são o ROI líquido
  estimado sobre a margem, usando a alavancagem realmente proposta.
- A variação sem alavancagem e a base de cálculo aparecem separadas.
- O bot não altera a alavancagem de uma posição na MEXC nem envia ordens.

## Migração e compatibilidade

A rodada passa `--migrate-leverage-ten` ao scan. O carregamento aceita apenas
paper e uma mudança exclusiva de piso 1 para 10, com os demais campos iguais.
Wallet, diário, posições, preços dos planos, cursores e mensagens já enviadas
são preservados. Decisões financeiras ativas são limpas para nova checagem;
indicações ENTRY e acompanhamentos pendentes expiram. O histórico é registrado
em `config_migrations`, com os dois fingerprints.

Configurações antigas sem o campo novo continuam com o fingerprint anterior
quando o piso é 1. Isso preserva a leitura dos experimentos congelados. Alterar
modo, taxas ou outros parâmetros junto com o piso continua exigindo migração
própria. A biblioteca sem arquivo de configuração conserva piso 1; a rodada
carrega explicitamente o arquivo ativo com piso 10.

## Verificação e limites

- 230 testes passaram, incluindo preservação de quantidade/ganho/perda em
  USDT, LONG/SHORT, alavancagem acima de 10 quando necessária, limites do
  contrato, stop próximo à liquidação e bloqueios de uso real.
- Migração exercitada em uma cópia do estado atual: 7.092 planos e 3.560
  mensagens enviadas preservados, conferindo wallet, diário, cursores,
  planos encerrados e IDs enviados.
- Demonstração sintética e replay passaram.
- Simulações históricas anteriores foram executadas com o piso antigo. Não
  constituem validação do piso novo; a liquidação mais próxima pode bloquear
  planos antes aceitos. Não foi feita otimização de novos parâmetros.
