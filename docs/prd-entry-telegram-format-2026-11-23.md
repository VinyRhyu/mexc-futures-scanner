# Layout de ENTRY no Telegram — atualização de apresentação para PRD

Data: 23/11/2026. Escopo: **somente mensagem de entrada**, sem mudança no modelo do scanner, quantidade, stop, target, margem, ordens, risco ou configuração.

## Estrutura solicitada

Apenas quando o plano é **financeiramente viável**, com `variant.status = VALIDA` e sem bloqueio de carteira, a notificação de categoria `ENTRY` apresenta os campos, nesta ordem:

```text
🟢 SINAL DE ENTRADA • SIMULAÇÃO
MOEDA: DEMO/USDT
MOVIMENTO: 📈 LONG (ALTA)
ALAVANCAGEM: 10x

ENTRADA: <mínimo validado> a <máximo validado>
TP1: <alvo técnico atual> (<ROI líquido estimado sobre a margem>)
TP2: não definido (modelo atual tem apenas um alvo técnico)

SL: <stop técnico atual> (<ROI líquido estimado sobre a margem>)
```

*Os preços no exemplo acima são placeholders, não sinais reais.*

- **MOEDA:** ativo USDT da proposta.
- **MOVIMENTO:** LONG (ALTA) ou SHORT (BAIXA).
- **ALAVANCAGEM:** somente `financial.leverage` calculada pelo avaliador financeiro após verificações de contrato, margem e risco; **não apresentar 20x ou 50x como alavancagem executável sem aprovação**.
- **ENTRADA:** faixa financeira viável exata, preservando todas as casas decimais, nunca um preço genérico do gatilho.
- **TP1:** único alvo existente `Variant.target`. Este é o alvo técnico integral atual; **nenhuma saída parcial em TP1 foi implementada**. Seu ROI, quando disponível, é estimado usando `gain_usdt / margin_usdt`, sem prometer um retorno fixo.
- **TP2:** marcado explicitamente como **não definido**. O motor atual tem apenas um alvo, e criar uma distância arbitrária seria operacionalmente enganoso. TP2 poderá ser introduzido posteriormente com **regra técnica formalizada, risco/custos e validação independente**.
- **SL:** stop técnico original `Variant.stop`, com perda estimada `-loss_usdt / margin_usdt` para deixar claro o risco de cada operação.

O rodapé mantém aviso de simulação, custos, relação retorno/risco, margem, validade do sinal e identificador do plano. Em **real**, mantém "EXECUÇÃO MANUAL" e verificações, nunca uma ordem automática. Em mensagens bloqueadas, a formatação anterior continua e **não indica uma entrada liberada**. Sinais de movimento/observação/fechamento não são reformulados.

## Faixa futura de alavancagem

O usuário manifestou a **intenção de pesquisar** `minimum_leverage=20` e `max_leverage=50` **após estabilidade estatística e operacional**. **NÃO IMPLEMENTAR AGORA**: o código e configuração PRD permanecem com piso 10x e teto 20x. Elevar para 50x exigiria uma pesquisa separada de limites da conta, política do validador, liquidação, maturidade do instrumento, custos e drawdown, além de autorização explícita para alterar a configuração.

## Critérios de aceite

- Testes de LONG e SHORT, precisão de preços, denominação de ROI sobre margem, bloqueios e fonte do valor da alavancagem.
- Teste integrado com `DemoClient`: ENTRY na outbox, sem envio; moeda, movimento, alavancagem, entrada, TP1, TP2 e SL aparecem nesta ordem.
- Preview `python -m scripts.telegram_preview` continua **fictício** e não envia mensagens sem `--send`.
- **Sem alteração** de `config/default.toml`, `mexc_scanner/finance.py`, `mexc_scanner/models.py`, `mexc_scanner/minute_breakout.py`, `mexc_scanner/state.py`, `.github/workflows/scan.yml` ou cronjob.org. Os eventos ENTRY e IDs, cotação/TTL e política de entrega permanecem idênticos.
