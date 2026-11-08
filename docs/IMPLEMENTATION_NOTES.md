# Decisões e esclarecimentos da implementação

Base: especificação v0.1, de 08/11/2026. Os parâmetros continuam experimentais.

## Duas janelas de 30 minutos

Um teste de comportamento mostrou que a validade única de 30 minutos a partir da preparação tornava a confirmação de rompimento impraticável: o primeiro fechamento ocorria aos 15 minutos e o segundo aos 30, quando o plano já expirava antes do aviso.

A implementação distingue:

- **Preparação:** até 30 minutos após a formação, para surgir o primeiro gatilho.
- **Entrada:** até 30 minutos após o horário de mercado do primeiro gatilho. Esse evento inicia uma fase nova, registrada no plano.

Uma detecção posterior não reinicia a validade. O surgimento da modalidade confirmada também não reinicia a janela de entrada. Sem novo gatilho, uma preparação expirada permanece encerrada. Os campos `formed_at`, `preparation_expires_at`, `entry_started_at` e `expires_at` tornam a mudança auditável.

Essa correção não altera risco, alvo, stop nem alavancagem. A validade continua sendo de entrada; uma posição já aberta segue seu stop e alvo.

## Implementação inicial

- As regras, a coleta e o diário são executados com a biblioteca padrão do Python 3.11+.
- A execução na corretora é manual. Não há cliente de ordens nem chave de negociação.
- Telegram é inicialmente um canal de saída. Entrada, não execução e encerramento são registrados pelo workflow de diário.
- A seleção inicial de cripto usa uma lista de classificação versionada. Ativos desconhecidos aparecem no diagnóstico, para revisão da classificação.
- A taxa de 0,06% por execução do arquivo padrão é uma hipótese de simulação. Ela não é apresentada como a taxa pessoal do usuário.
- Replay de uma captura atual usa hipóteses explicitadas de regras, custos e universo históricos. Isso não constitui validação de rentabilidade fora da amostra.

Consulte o relatório de validação para distinguir testes sintéticos, integração real e verificações ainda pendentes.
