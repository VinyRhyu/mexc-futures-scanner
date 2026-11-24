# PRD — Telegram somente para entradas confirmadas

Data: 23/11/2026 (São Paulo). Pedido: **parar o excesso de avisos de possíveis entradas e enviar somente sinais de entrada confirmados e financeiramente validados**.

## Única notificação automática autorizada

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

Os preços são **exemplo fictício**, não recomendação de operação. Em SHORT, o movimento aparece como `📉 SHORT (BAIXA)`. A alavancagem continua calculada pelo validador dentro do intervalo de configuração existente (10x–20x), o alvo TP1 é o único alvo técnico do modelo e TP2 continua explicitamente não definido.

Para chegar ao Telegram, o evento deve ter **categoria ENTRY**, ter sido gerado para variante `VALIDA`, plano não expirado e resultado financeiro `VIAVEL_SIMULADO` (paper) ou `VIAVEL_REAL` (se o modo e as verificações reais permitirem), sem restrições adicionais. A camada de entrega ainda valida o esquema exato de **dez linhas** e a marca `entry_only_v2`. A prioridade, cotação válida e TTL permanecem inalterados.

## O que deixa de ser enviado

- **MOVIMENTO DETECTADO • POSSÍVEL ENTRADA**: não mais enfileirado, inclusive após o primeiro fechamento M1. O scanner continua analisando esse estágio internamente para determinar se ocorrerá confirmação.
- Preparações, atualizações, encerramentos de plano, entradas bloqueadas, relatórios diários, erros de coleta, mensagens de diário e amostras fictícias automáticas já estavam bloqueados e permanecem assim.
- **Fila antiga:** qualquer aviso de movimento pendente — inclusive no antigo formato autorizado `movement_only_v2` — é marcado `EXPIRED` pela allowlist de entrega, sem contato com Telegram. Estados `SENT` anteriores permanecem para auditoria; nenhuma mensagem enviada anteriormente pode ser desfeita.

O comando `/ajuda`, quando solicitado diretamente pelo próprio usuário, continua sendo resposta manual, e não notificação automática.

## Fora de escopo

Nenhuma alteração em cronjob.org, `.github/workflows/scan.yml`, carteira paper, indicadores, MEXC Futures, contratos, quantidade de posições, risco, stop, take-profit, critérios financeiros, alavancagem 10x–20x ou Telegram secrets. A ideia futura 20x–50x continua não implementada.

## Verificações

Testes garantem: primeiro fechamento M1 sem mensagem, LONG/SHORT possíveis sem mensagem, segunda confirmação bloqueada sem mensagem, confirmação financeiramente viável com **exatamente uma ENTRY**, idempotência da outbox, movimento antigo pendente suprimido antes do envio, prioridade da entrada, não envio dos avisos legados e testes de integração do scanner. Aplicar em branch dedicada e integrar somente após CI verde.
