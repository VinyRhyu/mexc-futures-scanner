# Shadow A prospectivo — janela fixa de 7 dias (23–30/11/2026)

## Objetivo e separação operacional

Acompanhamento de **observação**, sem alterar filtros, posições, alertas ou Telegram de `scan.yml`. Usa `mexc_scanner.market` apenas para cálculos de preço e `scanner-state/state.json` apenas como **fonte de leitura**. Nunca grava dados em `scanner-state` e não possui código de ordem.

O experimento reproduz o filtro registrado antes dos resultados no PR #7: uma entrada é sinalizada como **possivelmente tardia** se o deslocamento direcional do fechamento M1, ao longo das últimas quatro horas, for >= 2 ATR(14) do último candle M15 fechado na confirmação. A classificação não bloqueia nenhum sinal original.

## Agendamento efetivo

- Programado para GitHub Actions nos minutos **04, 19, 34 e 49 de cada hora UTC**, somente entre os dias **23 e 30 de novembro**.
- **Início exato para novos eventos prospectivos:** 23/11/2026 às **04:00 UTC** (01:00 BRT).
- **Fim exato:** 30/11/2026 às **04:00 UTC** (01:00 BRT). Até oito horas adicionais de acompanhamento técnico podem ser consultadas. Depois, o workflow não faz consultas à fonte operacional ou à MEXC; a cláusula de calendário também impede rodadas periódicas durante os demais meses.
- Agendamentos GitHub podem atrasar ou não executar. Espera-se **aproximadamente** 15 minutos por rodada, sem garantia de pontualidade. Não reconfigurar cronjob.org.
- O processo não preserva token após checkout; `permissions: contents: read`; `concurrency` exclusiva `shadow-a-observation-only`. Histórico publicado somente como artifacts JSON sanitizados de 30 dias, sem branch de dados nova.
- Um sinal pode aparecer em vários artifacts. **Deduplicar por (símbolo, direção, minuto da confirmação)** e conservar a primeira observação elegível. Planos técnicos com TP/SL diferentes ficam preservados; não são múltiplas entradas independentes.

## Critério de observação prospectiva

Cada execução coleta uma janela móvel de oito horas de sinais técnicos confirmados do scanner, com M1/M15/H1 públicos e fechados, mas **somente** marca `new_prospective_observation=true` quando:

1. o sinal ocorreu dentro da janela fixa do experimento;
2. a captura do sinal aconteceu até **20 minutos** após sua confirmação;
3. nenhum candle observado antes da captura havia tocado TP ou SL daquele plano;
4. os candles de contexto eram completos e respeitavam as janelas causais.

Capturas tardias, histórico/bootstrap ou toques prévios a observação permanecem registrados, mas **não** entram como eventos prospectivos válidos. O registro posterior de toque em TP/SL (até quatro horas) é **apenas trajetória de preços**. Não interpreta toque como entrada ou fill: livro, spread, slippage pessoal, funding, tamanho mínimo e viabilidade da carteira não são historicamente verificáveis a partir desses dados.

**Viés explicitado:** capturas em até 20 minutos podem excluir movimentos de TP/SL muito rápidos, por falhas e atrasos do agendamento. Medir a proporção de sinais não capturados e não extrapolar sem correção.

## Validação e decisão

O workflow executa, antes de ler estado, testes que validam cronologia, duplicação, isolamento de saldos privados, não alteração do estado, janelas incompletas e rejeição de informação futura. Se `scanner-state` estiver desatualizado por mais de 30 minutos ou falhar a cobertura MEXC, o job falha sem classificar incorretamente esses dados.

**Não há autorização para alterar filtros do scanner por resultado deste teste.** Após uma semana, devemos consolidar primeira captura de cada sinal, frequência de vetos, cobertura, resultados técnicos posteriores com censura, e onde possível testar custo realista com uma amostra independentemente coletada. Exigiremos evidência de expectativa líquida positiva, não apenas contagem de toques TP/SL.

O único custo operacional adicional é a execução do workflow de pesquisa no Actions e os pequenos artifacts. Ele não mexe no cronjob.org nem no agendamento operacional `scan.yml`.

## Arquivos

- `.github/workflows/shadow-a-prospective.yml`
- `scripts/research_entry_context.py`
- `scripts/research_shadow_a.py`
- `tests/test_research_entry_context.py`
- `tests/test_research_shadow_a.py`
