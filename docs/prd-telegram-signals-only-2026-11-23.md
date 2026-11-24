# PRD: Telegram exclusivamente para movimento inicial e entrada validada

Data: 23/11/2026. A pedido do usuário, reduzir **notificações não solicitadas do scanner** a apenas dois eventos:

1. **MOVIMENTO DETECTADO • POSSÍVEL ENTRADA:** o primeiro candle M1 já fechou no sentido do rompimento; aguarda o segundo fechamento e validação financeira. Não é uma autorização de entrada.
2. **SINAL DE ENTRADA • SIMULAÇÃO:** o plano foi confirmado, a cotação e a margem passaram na avaliação financeira; usa somente os preços e a alavancagem aprovados.

## Mensagem exata de entrada

```text
🟢 SINAL DE ENTRADA • SIMULAÇÃO
MOEDA: DEMO/USDT
MOVIMENTO: 📈 LONG (ALTA)
ALAVANCAGEM: 10x

ENTRADA: 102.121 a 102.499
TP1: 106.2 (+34.48% ROI líquido estimado sobre a margem)
TP2: não definido (modelo atual tem apenas um alvo técnico)

SL: 101.4 (-12.31% ROI líquido estimado sobre a margem)
```

Exemplo numérico **fictício**. A mensagem em produção tem **exatamente dez linhas**, sem planos/IDs, rodapé, validade, taxa, custos, relatórios, status extra ou outros campos. Esses detalhes continuam armazenados nos relatórios e no estado interno. SHORT usa `📉 SHORT (BAIXA)`. O ROI é sobre **margem inicial estimada**, já com os custos simulados no P&L, não percentagem sobre a banca e não lucro assegurado.

TP1 é o único alvo técnico `Variant.target`. TP2 permanece **não definido**, sem inventar saída parcial ou preço. Stop e faixa de entrada preservam precisão completa.

## Mensagem de possível entrada (primeiro M1)

```text
🟡 MOVIMENTO DETECTADO • POSSÍVEL ENTRADA
MOEDA: DEMO/USDT
MOVIMENTO: 📈 LONG (ALTA)
STATUS: aguardando segundo fechamento M1 e avaliação financeira.
```

A informação é enviada apenas se um primeiro candle M1 **fechado e recente** foi observado (`AGUARDANDO_CONFIRMACAO`); janela máxima de 60 segundos desde o fechamento e fonte validada. Não alertar consolidações sem primeiro gatilho, segundo candle **bloqueado**, movimentos inválidos, repetidos ou muito antigos.

## Categorias removidas do Telegram automático

Não entregar: plano possível ou preparação sem gatilho, acompanhamento/atualização de plano, confirmação financeira bloqueada, encerramento, invalidação, stop/target/expiração de um plano não executado, resumo diário, erros de coleta, diário de ordens, recomendações, avisos diversos e mensagem de demonstração automatizada.

Todas essas informações **permanecem disponíveis nos diagnósticos, relatórios e observabilidade**, mas não são enfileiradas como alertas. A função central de envio rejeita, com registro de supressão, **inclusive qualquer mensagem antiga** que permaneça pendente no estado persistido: somente evento com marca explícita de novo formato e texto exatamente compatível é permitido. O histórico `SENT` existente não é alterado, nem o estado da banca; somente filas `PENDING` antigas podem virar `EXPIRED`. Mantém expiração por horário e atualização da cotação antes do envio.

O comando `/ajuda`, quando o próprio usuário o solicitar diretamente no Telegram, continua sendo uma resposta solicitada, não uma notificação espontânea do scanner. O workflow de verificação do Telegram passa a executar **pré-visualização sem enviar** o exemplo fictício.

## Escopo operacional e segurança

Somente política de notificação e formatação: sem mudança em `config/default.toml`, `finance.py`, `models.py`, `minute_breakout.py`, conta, contratos, seleção técnica, RR, SL, TP, limites de risco, agendamento do cronjob.org ou execução de ordens. Piso e teto de alavancagem continuam **10x a 20x**; a ideia 20x–50x continua sendo uma possibilidade de pesquisa futura e **NÃO** foi ativada.

Critérios de aceite: testes de LONG/SHORT, 10 linhas exatas, precisão de preços, bloqueios e ausência de validação, anti-duplicação, idade do primeiro M1, qualificação financeira, carteira não disponível, erros de coleta, não entrega de alertas antigos, integração de outbox, não envio de Telegram pelo workflow de testes e suíte CI completa.
