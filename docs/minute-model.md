# Modelo M1 com sustentação de volume

Identificação: m1_volume50_v1. O workflow Scanner MEXC seleciona esse modelo via SCANNER_STRATEGY. CLI: `python -m mexc_scanner scan --model m1_volume50_v1`.

Consolidação: oito candles M15 fechados, largura de1–4ATR14 e ao menos dois toques por borda. Sem supressão de formações sobrepostas, como na comparação histórica. Cada formação tem30min para o primeiro gatilho.

Gatilho: primeiro M1 fecha além da borda por0,10ATR; o M1 imediatamente seguinte fecha também além desse nível e tem volume pelo menos50% do primeiro, com primeiro volume positivo. Sem substituição posterior se falhar. Apenas a variante CONFIRMADA pode ser liberada.

SL, TP e faixa permanecem fixados no primeiro fechamento M1, usando a função anterior de projeção e pivôs H1/H2 conhecidos. Não há TP aumentado nem proteção no zero. Permanecem os filtros financeiros e de liquidação existentes; mode=paper não foi alterado. O programa não envia ordens à exchange.

A configuração ativa usa retorno/risco líquido mínimo de **1:1**, incluindo custos estimados. Esse é um piso para liberar o plano; o TP técnico pode oferecer mais que 1R e não há lucro mínimo fixo de 10% ou 60%. A biblioteca mantém o padrão conservador de 2 para chamadas sem arquivo de configuração; o workflow carrega explicitamente `config/default.toml`, com mínimo 1.

A alavancagem ativa tem piso de **10x** e teto de **20x**. A quantidade e o risco em USDT continuam sendo definidos antes da alavancagem. Contrato, margem e distância da liquidação podem bloquear o plano; o piso não força uma execução nem aumenta o tamanho da posição. O ROI sobre a margem muda com a margem menor, mas o lucro/perda em USDT da mesma posição não aumenta por esse motivo.

Alertas de movimento mostram o cenário bruto indicativo em 10x; entradas viáveis mostram ROI líquido estimado sobre a margem, calculado com a alavancagem efetivamente proposta. A variação sem alavancagem fica separada.

No Telegram, o acompanhamento começa em `MOVIMENTO DETECTADO`: o primeiro M1 fechado já rompeu uma região monitorada. O aviso destaca o lado e o horário observados, além da confirmação pendente; consolidações ainda sem rompimento ficam na análise interna. O movimento é informativo e não altera os planos calculados nem libera entrada antecipada. Entradas confirmadas e financeiramente viáveis mantêm seu alerta próprio. Detalhes em `telegram-waiting-entry.md`.

Gatilhos com mais de120segundos não são liberados como entradas atuais. O prazo de nova entrada expira no máximo120segundos após o segundo fechamento. Toque em SL/TP enquanto espera cancela a tentativa. A cotação, livro e funding são avaliados ao analisar o sinal, sem simular retrospectivamente uma execução perdida.

## Agendamento

No cron-job.org, mudar a expressão do disparo existente para `* * * * *` e manter o corpo POST com ref main e inputs.limit 50. O agendamento GitHub existente de15min permanece apenas como contingência e não reproduz monitoramento por minuto. A fila e a latência de GitHub Actions podem atrasar execuções; gatilhos atrasados são descartados. O tempo de cada rodada e os limites de uso do provedor devem ser acompanhados.

Não foi criado um worker contínuo ou nova assinatura. Uma rodada é executada após a implantação; as demais dependem do agendamento. Frequência de1min pode aumentar o consumo de minutos do GitHub Actions.

## Migração e validação

Na mudança financeira de 2:1 para 1:1, `scripts.run_round` passa `scan --migrate-rr-one`. Essa migração aceita apenas modo paper e apenas a mudança do mínimo 2 para 1, com os demais parâmetros idênticos. Saldo, posição, diário, níveis dos planos, cursores e IDs enviados são preservados. Avaliações financeiras de planos ainda ativos são descartadas e refeitas com cotação atual; indicações pendentes da política antiga expiram. Planos encerrados não são reabertos. O histórico da migração fica em `config_migrations` no estado. Mudanças de taxas, saldo inicial, risco, modo ou outro parâmetro continuam exigindo sua própria migração.

O relatório JSON e seu cabeçalho Markdown informam `minimum_rr`. O modo continua paper, com verificações pessoais de uso real pendentes.

A mudança do piso de alavancagem usa `scan --migrate-leverage-ten`, passado pela rodada. Ela aceita apenas paper, com alteração exclusiva de piso 1 para 10; preserva wallet, diário, posições, níveis, cursores e mensagens enviadas. Expira indicações e acompanhamentos pendentes, e reavalia financeiros ativos. O registro fica em `config_migrations`. Os fingerprints de configurações antigas sem o novo piso continuam compatíveis quando o piso é 1. Relatórios também informam `minimum_leverage` e `max_leverage`.

A primeira rodada do novo modelo encerra planos anteriores para novas entradas e expira seus alertas ENTRY pendentes, preservando wallet, posição registrada, diário e mensagens já enviadas. Novos símbolos e mudanças de modelo começam a observar formações futuras, sem apresentar sinais anteriores à ativação como entradas novas. Lacunas M1 reiniciam a observação a partir do momento atual.

Foram acrescentados testes de fechamento, volume, níveis congelados, simetria, migração, atraso e consistência M1/M15. A validação em branch separada compara as confirmações com a coleta histórica congelada e realiza coleta real sem notificar Telegram antes de ativar main.

O teste retrospectivo teve56% de TP entre25operações encerradas, na amostra filtrada. Esse percentual não é taxa garantida nem demonstra melhora prospectiva sobre a produção. O universo, custos e execução do histórico foram hipotéticos, e as entradas podem ser correlacionadas.
