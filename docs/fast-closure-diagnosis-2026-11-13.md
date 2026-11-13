# Diagnóstico dos encerramentos rápidos no Telegram

Estado observado: `9d154b7580c256ab78107d614810b346e85c17c7`, coleta de
13/11/2026 às 19:08:08 BRT, fonte OK, modo paper. O recorte usa mensagens
de movimento marcadas SENT nos 60 minutos mais recentes da coleta, incluindo
os registros de envio dessa mesma rodada. São avisos, não operações executadas.

| Estado dos planos apresentados no recorte | Avisos |
| --- | ---: |
| Não confirmou: volume do segundo M1 abaixo de 50% | 9 |
| Não confirmou: segundo M1 perdeu o rompimento | 3 |
| Alvo do plano tocado durante acompanhamento | 5 |
| Prazo de nova entrada encerrado | 1 |
| Ainda ativo no instante da coleta | 1 |
| Total | 19 |

Dos 19 avisos, 17 eram do primeiro M1, ainda sem confirmação. O intervalo
registrado entre o fechamento desse primeiro candle e o envio variou de
34 a 83 segundos, mediana de 61 segundos. O horário registrado antes da
correção era o início do lote de envio, não um relógio atualizado por mensagem.

A maioria dos encerramentos rápidos não foi causada pelo prazo de 120s.
Os avisos precedem a confirmação e o próximo M1 pode falhar em volume ou
fechamento. Além disso, o atraso podia fazer o primeiro aviso chegar depois
do horário em que o segundo candle já deveria ter fechado.

Toque no alvo de plano sem entrada não é lucro realizado. Falha na condição
de volume não prova que o preço deixará de se mover; significa que o gatilho
não cumpriu a regra de entrada definida.

## Correções de apresentação e entrega

- Primeiro aviso destaca AINDA SEM CONFIRMAÇÃO no título.
- Atualizações informam o motivo efetivo: volume, rompimento, prazo ou toque
  em alvo/stop. A expiração não é apresentada como ordem de saída.
- Avisos do primeiro M1 só são gerados e válidos durante os 60s anteriores ao
  próximo fechamento. Os atrasados são descartados. Isso reduz avisos antigos,
  sem garantir que todo primeiro gatilho será notificado.
- Confirmações técnicas e janela para nova entrada mantêm 120s.
- ENTRY vem primeiro, movimento recente depois, e resumos/atualizações por
  último. A validade é rechecada com o relógio atual antes de cada envio.
- O registro SENT usa o horário após a resposta do Telegram para melhorar
  a medição futura da latência. Não demonstra leitura nem execução manual.

As estratégias, os candles usados na análise, o volume mínimo, TP, SL,
RR mínimo, alavancagem e risco de posição permanecem iguais. Não foi
reduzido um filtro para manter movimentos artificialmente como entradas.
Não há migração de configuração ou reinicialização do diário.

238 testes passaram, incluindo separação de causas, preservação de planos,
validade do primeiro aviso e prioridade/expiração durante o envio. O ajuste
não remove a latência de coleta e da fila do GitHub Actions.
