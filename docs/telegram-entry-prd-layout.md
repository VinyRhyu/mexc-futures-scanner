# PRD — Formato enxuto do alerta de ENTRADA (Telegram)

Solicitado em 23/11/2026. Alteração **somente de apresentação** das mensagens de categoria `ENTRY`, quando a entrada já foi validada financeiramente. O modelo e o validador, os candles M1, os limites de stop, a carteira, o cronjob.org, a deduplicação e as regras de autorização permanecem iguais. Alertas informativos de preparação/movimento ou entrada bloqueada continuam identificados, sem se passar por uma entrada executável.

## Modelo

```text
🟢 GATILHO VÁLIDO PARA SIMULAR
MOEDA: BTC/USDT
MOVIMENTO: ALTA (LONG)
ALAVANCAGEM: 10x

ENTRADA: [faixa numérica de preço aprovada]
TP1: [único alvo técnico aprovado] ([ROI líquido estimado sobre a margem])
TP2: não definido (sem segundo alvo técnico validado)
SL: [stop técnico] ([perda líquida estimada sobre a margem])
```

Para SHORT, `MOVIMENTO: BAIXA (SHORT)`. O cabeçalho real é `ENTRADA VALIDADA` **somente** quando já houver viabilidade `VIAVEL_REAL` conforme o validador. O texto abaixo do resumo mantém informações de risco, preço sem alavancagem, taxa, validade, hora do gatilho e ressalvas de simulação. A alavancagem exibida é a **calculada/aprovada em `variant.financial.leverage`**, não o teto do arquivo de configuração nem uma escolha arbitrária.

**TP1** corresponde ao único preço `variant.target` do plano técnico. **TP2 não é calculado na versão atual**; é explicitamente indicado como **não definido**, sem inventar um segundo alvo numérico ou adaptar o stop/TP. Um TP2 verdadeiro exigirá uma hipótese técnica e uma avaliação financeira próprias, proposta e testada separadamente.

## Política de alavancagem (futura, NÃO aplicada)

O usuário sugeriu **20x mínimo e 50x máximo somente quando o scanner atingir estabilidade comprovada**. Essa combinação **NÃO** entra nesta entrega; permanece 10x mínimo e 20x máximo configurados em `config/default.toml` e validados em `mexc_scanner/config.py`. O teto de 20x é atualmente uma proteção na própria validação de configurações. A eventual mudança exigirá pesquisa separada, revisão de limites de contrato, distância à liquidação, margem, risco financeiro, efeito na liquidez e migração explícita do estado, além de nova aprovação para PRD.

## Verificações

- Ordem MOEDA → MOVIMENTO → ALAVANCAGEM → ENTRADA → TP1 → TP2 → SL.
- Mesmos níveis numéricos aprovados pela avaliação financeira; LONG/SHORT e modo paper/real.
- Alerta bloqueado ou restrito não é apresentado como entrada confirmada.
- Sem alteração de objetos de plano, timestamps, regras de avaliação ou de envio.
- Preview fictício continua identificado como **NÃO OPERAR**.
- O merge desta alteração em `main` executa `scan.yml` pelo gatilho já existente no workflow, sem criar rotina adicional. O cronjob.org permanece configurado externamente e não é alterado.
