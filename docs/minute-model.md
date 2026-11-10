# Modelo M1 com sustentação de volume

Identificação: m1_volume50_v1. O workflow Scanner MEXC seleciona esse modelo via SCANNER_STRATEGY. CLI: `python -m mexc_scanner scan --model m1_volume50_v1`.

Consolidação: oito candles M15 fechados, largura de1–4ATR14 e ao menos dois toques por borda. Sem supressão de formações sobrepostas, como na comparação histórica. Cada formação tem30min para o primeiro gatilho.

Gatilho: primeiro M1 fecha além da borda por0,10ATR; o M1 imediatamente seguinte fecha também além desse nível e tem volume pelo menos50% do primeiro, com primeiro volume positivo. Sem substituição posterior se falhar. Apenas a variante CONFIRMADA pode ser liberada.

SL, TP e faixa permanecem fixados no primeiro fechamento M1, usando a função anterior de projeção e pivôs H1/H2 conhecidos. Não há TP aumentado nem proteção no zero. Permanecem os filtros financeiros e de liquidação existentes; mode=paper não foi alterado. O programa não envia ordens à exchange.

Gatilhos com mais de120segundos não são liberados como entradas atuais. O prazo de nova entrada expira no máximo120segundos após o segundo fechamento. Toque em SL/TP enquanto espera cancela a tentativa. A cotação, livro e funding são avaliados ao analisar o sinal, sem simular retrospectivamente uma execução perdida.

## Agendamento

No cron-job.org, mudar a expressão do disparo existente para `* * * * *` e manter o corpo POST com ref main e inputs.limit 50. O agendamento GitHub existente de15min permanece apenas como contingência e não reproduz monitoramento por minuto. A fila e a latência de GitHub Actions podem atrasar execuções; gatilhos atrasados são descartados. O tempo de cada rodada e os limites de uso do provedor devem ser acompanhados.

Não foi criado um worker contínuo ou nova assinatura. Uma rodada é executada após a implantação; as demais dependem do agendamento. Frequência de1min pode aumentar o consumo de minutos do GitHub Actions.

## Migração e validação

A primeira rodada do novo modelo encerra planos anteriores para novas entradas e expira seus alertas ENTRY pendentes, preservando wallet, posição registrada, diário e mensagens já enviadas. Novos símbolos e mudanças de modelo começam a observar formações futuras, sem apresentar sinais anteriores à ativação como entradas novas. Lacunas M1 reiniciam a observação a partir do momento atual.

Foram acrescentados testes de fechamento, volume, níveis congelados, simetria, migração, atraso e consistência M1/M15. A validação em branch separada compara as confirmações com a coleta histórica congelada e realiza coleta real sem notificar Telegram antes de ativar main.

O teste retrospectivo teve56% de TP entre25operações encerradas, na amostra filtrada. Esse percentual não é taxa garantida nem demonstra melhora prospectiva sobre a produção. O universo, custos e execução do histórico foram hipotéticos, e as entradas podem ser correlacionadas.
