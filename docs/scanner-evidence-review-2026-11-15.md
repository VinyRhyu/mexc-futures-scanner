# Estudos e evidências para melhorar o scanner MEXC

**Levantamento de 15/11/2026: oito estudos e sete documentos técnicos primários.** Escopo: fundamentar as próximas decisões antes de testar outra estratégia. Nenhum novo teste, nova captura de mercado ou alteração do bot foi feito nesta etapa.

## Conclusão do levantamento

A evidência consultada é mais sólida para melhorar a qualidade da medição, da execução e da validação do que para escolher imediatamente outro indicador. Existem resultados favoráveis a regras técnicas e também resultados que desaparecem depois de custos, controles estatísticos ou mudança de período. Nenhuma fonte consultada valida diretamente nosso conjunto de regras de rompimento M1 com sustentação de volume 50%.

Este levantamento é dirigido, não uma revisão sistemática exaustiva nem uma meta-análise. Três textos integrais abertos foram consultados; nos outros cinco estudos, a análise se limita a resumos editoriais, metadados e trechos acessíveis. Não foram contornados paywalls. O catálogo JSON registra os limites de acesso, DOI, links e escopo de cada fonte.

## Matriz dos estudos

| Fonte primária | Mercado e frequência | Achado relevante | Limite para nosso scanner |
|---|---|---|---|
| [P01 — Hudson e Urquhart (2021)](https://link.springer.com/article/10.1007/s10479-019-03357-1) | BTC em duas fontes, ETH, LTC e XRP; preços diários até 2017, com avaliação fora da amostra. | Examina 14.919 regras, incluindo rompimentos de canais, e encontra resultados positivos após controles estatísticos. O desempenho de Bitcoin não se mantém na avaliação fora da amostra. | É evidência sobre regras diárias e dados antigos; não valida o rompimento M1 de altcoins na MEXC. |
| [P02 — Anghel (2021)](https://www.sciencedirect.com/science/article/pii/S1544612320304414) | Regras técnicas e aprendizado de máquina em cripto; detalhes completos de amostra não conferidos. | Depois de controlar tentativas múltiplas e fricções de mercado, retornos excedentes positivos estatisticamente significativos aparecem raramente. | Contrapõe conclusões otimistas, mas o resumo não permite escolher um filtro, algoritmo ou timeframe vencedor. |
| [P03 — Wen e colaboradores (2022)](https://www.sciencedirect.com/science/article/abs/pii/S1062940822000833) | BTC 2013–2020; relações entre retornos horários; verificações também em ETH, LTC, XRP. | Observa continuação e reversão intradiárias; os padrões variam com saltos de preço, liquidez, anúncios do FOMC e períodos de estresse. | Sustenta investigar condicionantes de mercado, não assumir que dois pivôs H1/H2 ou uma EMA representam esses regimes. Não testa nosso gatilho M1. |
| [P04 — Fieberg, Liedtke e Zaremba (2024)](https://www.sciencedirect.com/science/article/pii/S1057521924001509) | Quase 4.000 criptomoedas, 2014–2022; carteiras por características, não rompimentos M1. | A negociabilidade altera as anomalias: tamanho, volume, custos, lado SHORT e período de mercado importam; parte dos resultados perde força em anos recentes. | Não permite copiar posições vendidas hipotéticas como futuros executáveis. Frequência e reequilíbrio detalhados não foram conferidos no integral. |
| [P05 — Silantyev (2019)](https://link.springer.com/article/10.1007/s42521-019-00007-w) | Negócios e cotações do perpétuo XBTUSD na BitMEX; período detalhado não conferido. | O desequilíbrio do fluxo de negócios explica variações contemporâneas de preço melhor que o desequilíbrio agregado de ordens nessa amostra. | Explicar movimento simultâneo não prova previsão futura nem lucro líquido. Volume total de candle não mede a mesma coisa que fluxo com direção. |
| [P06 — Shanaev, Vasenin e Stepanov (2023)](https://pmc.ncbi.nlm.nih.gov/articles/PMC10015199/) | BTC em sete exchanges, dados M1 até 2021 e verificação Bitfinex em 2022. | Documenta padrão em minutos de virada M15. A simulação econômica considera custos e descontos por volume; o resultado depende fortemente das condições de execução. | Bitfinex 2021, capital e tabela de taxas particulares não se transferem para MEXC ou saldo pequeno. Não é evidência para entrar em todo fechamento M15. |
| [P07 — Bailey e colaboradores (2017)](https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf) | Metodologia estatística de seleção de estratégias; não demonstra uma estratégia de cripto. | Repetir tentativas no mesmo histórico eleva o risco de selecionar ruído. Um holdout isolado não controla automaticamente esse problema; propõe PBO/CSCV. | Não calculamos PBO neste levantamento. Tampouco o artigo torna walk-forward ou um número fixo de trades garantia de validação. |
| [P08 — Kaminski e Lo (2014)](https://dspace.mit.edu/entities/publication/bb69ca4b-0cdc-487f-831d-63b2e84fafee) | Políticas de redução de exposição em futuros de índices, dados diários; publicação 2014. | Formaliza condições em que políticas de stop acrescentam ou retiram valor; algumas políticas ajudam em frequências mais longas. | Não valida break-even após 0,5R, trailing M1 ou remoção de stop em futuros alavancados. A ligação com nossas saídas é conceitual. |

P01 e P02 não devem ser tratados como uma confirmação única: seus resultados sobre regras técnicas diferem. Isso reforça a necessidade de verificar instrumento, horizonte, seleção de regras, custos e validação de cada estudo. Não há suporte para concluir que toda análise técnica funciona ou que nenhuma funciona.

P03 justifica estudar a alternância entre continuação e reversão, mas seus condicionantes não são equivalentes ao nosso classificador de dois pivôs H1/H2. P05 explica variação contemporânea de preços; não demonstrou aqui um sinal negociável com antecedência. Essas diferenças impedem transformar diretamente um achado em filtro.

P06 oferece evidência em M1, mas com mercado, época e tabela de taxas específicos. O capital de US$ 5.000 citado pelo artigo é resultado de uma simulação Bitfinex, não um piso universal para operar nem uma recomendação para a conta do usuário. P08 trata políticas de exposição em outro mercado e prazo; não sustenta retirar o stop de uma posição alavancada.

## Evidência técnica e lacunas concretas

| Documento oficial | O que foi confirmado | Implicação para o projeto — interpretação nossa |
|---|---|---|
| [D01 — GitHub Actions — Troubleshooting workflows](https://docs.github.com/en/actions/how-tos/troubleshoot-workflows) | Eventos schedule podem atrasar ou ser descartados sob carga. | Aviso refere-se a schedule; não prova atraso do nosso workflow_dispatch externo. |
| [D02 — MEXC Futures — Deal WebSocket](https://www.mexc.com/api-docs/futures/websocket-api/deal) | Trades públicos incluem preço,volume,lado e timestamps; há agregação padrão. | Confirmar semântica do lado e agregação antes de inferir agressão. |
| [D03 — MEXC Futures — Order book depth](https://www.mexc.com/api-docs/futures/websocket-api/order-book-depth) | Documenta atualizações de profundidade e versões por WebSocket. | Disponibilidade de dados não demonstra vantagem preditiva. |
| [D04 — MEXC Futures — Incremental order book maintenance](https://www.mexc.com/api-docs/futures/websocket-api/incremental-order-book-maintenance-mechanism) | Snapshot,aplicação de atualizações e recuperação de lacunas são necessários. | Livro inconsistente não serve como medida confiável de liquidez. |
| [D05 — MEXC Futures — Get Fair Price Candles](https://www.mexc.com/api-docs/futures/market-endpoints/get-fair-price-candles) | Endpoint documenta Min1 e paginação temporal com limite 2.000 pontos. | Precisamos verificar cobertura real por ativo; não coletamos agora. |
| [D06 — MEXC Futures — Get Funding Rate History](https://www.mexc.com/api-docs/futures/market-endpoints/get-funding-rate-history) | Histórico contém taxa, horário de cobrança/pagamento e ciclo. | Aplicar só os eventos mantidos em posição,sem descontar duas vezes. |
| [D07 — MEXC — FAQ on Index Price, Fair Price, and Last Price](https://www.mexc.com/support/article/faq-on-index-price-fair-price-and-last-price-7950960183961) | Fair Price e Last Price têm funções distintas na execução e liquidação. | Respeitar o gatilho de stop configurado por contrato/ordem. |

**Latência:** o código atual expira a entrada após 120 segundos. O alerta de atraso na documentação do GitHub refere-se a eventos schedule; nosso cron externo usa workflow_dispatch. Portanto, não prova que esse caminho esteja atrasando nem explica as perdas observadas. A proposta é medir a cadeia real: fechamento do sinal, coleta, fim da análise, aceite do envio pelo Telegram e execução informada pelo usuário. Aceite do Telegram não prova leitura ou execução. Um eventual processo contínuo é uma decisão operacional a avaliar depois dessas medidas, sem promessa de rentabilidade. [D01; código do projeto]

**Preço e funding:** o replay M1 usou trajetória Last, funding zero e livro sintético. D05–D07 mostram caminhos documentados para obter Fair M1 e eventos de funding, distinguindo execução, gatilho do stop e liquidação. Isso corrige lacunas de validade da simulação; não torna uma estratégia automaticamente lucrativa. A cobertura dos endpoints por ativo ainda teria de ser verificada.

**Fluxo e livro:** D02–D04 permitem planejar uma coleta pública mais informativa. Antes de calcular desequilíbrio, seria necessário validar a semântica de lado, agregação, timestamps e continuidade do livro. Volume total do candle não informa sozinho quem iniciou os negócios nem intenção de compra/venda. Isso é uma hipótese de dados futuros; não acrescentamos um filtro neste levantamento. [P05,D02–D04]

## O que muda na nossa forma de pesquisar

1. **Tratar as semanas já exploradas como desenvolvimento.** Registrar todas as tentativas, inclusive as negativas, antes de considerar outra descoberta. Uma semana antes chamada de teste deixa de ser uma verificação independente quando voltamos a escolhê-la para ajustar regras. [P07]

2. **Comparar execução viável com a hipótese de entrada imediata.** Medir preços realmente disponíveis e tempo até o sinal, sem atribuir previamente as perdas à infraestrutura. A evidência de lucro deve sobreviver ao custo e atraso observados. [P02,P04,D01]

3. **Separar contexto de mercado de confirmação tardia.** Investigar condições observáveis antes da entrada — liquidez, volatilidade e saltos — para formular uma hipótese de continuação ou reversão. Não derivar uma regra de regime apenas do resultado da operação nem converter um estudo horário em gatilho M1. [P03]

4. **Avaliar uma carteira e incerteza, além da taxa de acerto.** Somar riscos normalizados de sinais simultâneos não é ROI. A futura avaliação precisa explicitar capital, margem, quantidade, custos, eventos de funding, posições abertas e restrições de execução. As operações sobrepostas devem ser tratadas como dependentes; propomos avaliação por blocos temporais/movimentos e separação das janelas de desfecho no corte dos dados. Isso é desenho nosso de pesquisa, não um resultado calculado neste documento.

5. **Reservar dados realmente novos para uma regra congelada.** A validação deve usar vários períodos e cenários de custo predefinidos, com hipóteses e critério de abandono claros. Não foi calculado PBO, significância estatística ou intervalo de confiança dos nossos resultados nesta etapa. Nenhum tamanho fixo de amostra é garantia universal. [P01,P02,P07]

## Prioridades propostas, sem implementação

| Prioridade | Entregável necessário antes de outra opção | Motivo |
|---|---|---|
| 1 | Diagnóstico de dados e execução: clocks, atraso até alerta, preços negociáveis, custo real da conta, Fair e funding | Diferenciar falha de estratégia de erro de simulação ou sinal inexequível. |
| 2 | Protocolo único para M1, ledger de todas as hipóteses e conjuntos de dados reservados | Reduzir seleção de regras por resultados de amostras pequenas e reutilizadas. |
| 3 | Especificação de contexto para continuação versus reversão, sem escolher parâmetros agora | A literatura intradiária é condicional, não uma regra única de seguir ou contrariar a tendência. |
| 4 | Plano de coleta de negócios/livro, somente se houver justificativa após itens anteriores | Não substituir volume bruto por outra variável sem demonstrar informação futura e custo viável. |

Consideramos de maior suporte as melhorias de integridade, execução e validação. A escolha de um novo setup continua aberta. Não há evidência suficiente neste conjunto para prometer que outro número de candles, outra relação TP/SL ou maior alavancagem resolverá o problema.

## Ligação com as evidências do próprio projeto

- [Última verificação histórica](m1-short-progress-validation-2026-11-15.md): no período 08–14/11, a referência teve 25 TPs, 65 stops e 17 abertas nos 29 ativos completos; o filtro proposto piorou o resultado. Os dois ativos sem histórico permaneceram excluídos de forma explícita. Esse é um resultado local, não uma afirmação sobre todos os mercados ou todos os futuros.
- [Testes de gestão de saída](m1-stop-improvement-2026-11-15.md): as duas saídas dinâmicas reduziram stops completos e cortaram ganhos. A literatura de políticas de stop não autoriza chamar a redução de stops de melhora econômica sem medir o retorno total.
- [Contexto H1/H2](m1-trend-context-2026-11-15.md): o teste desse classificador não sustenta bloquear automaticamente todas as entradas contrárias. Isso não refuta outras definições de regime.

## Estado e limites desta entrega

Pesquisa documental realizada em 15/11/2026. Documentação oficial consultada nessa data; APIs e regras podem mudar. Estudos de períodos anteriores não comprovam vantagem atual em futuros MEXC, e estudos de outros mercados/horizontes foram identificados como evidência indireta. Não coletamos novas cotações, não executamos novos backtests, não alteramos parâmetros, rotinas, mensagens, ordens ou a branch de produção.

Versão de produção conferida: `20c500deb4fbea15573dbced9eaddb6bf5839cae`. Base do histórico de pesquisa: `260281f618808ab6e795bf2a0969c05574b2d444`.
