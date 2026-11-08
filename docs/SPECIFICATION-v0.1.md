# MEXC Futures Scanner — Especificação v0.1

Data: 08/11/2026. Horários apresentados ao usuário: America/Sao_Paulo.

Documento de planejamento. Implementação, acesso real aos dados, entrega de alertas e desempenho das estratégias ainda não foram validados. Os parâmetros numéricos abaixo são hipóteses iniciais de projeto, escolhidas para tornar o método reproduzível. Não representam parâmetros comprovadamente lucrativos.

## 1. Objetivo e decisões estabelecidas

Identificar oportunidades condicionais de LONG e SHORT em futuros perpétuos de cripto na MEXC. Produzir planos com condições observáveis e acompanhar cada plano entre as rodadas. As ordens serão executadas manualmente pelo usuário.

O experimento começa com saldo equivalente a US$ 1 e tem um primeiro marco de revisão em US$ 100. Os cálculos do scanner usam o saldo efetivo em USDT; a conversão entre moedas deverá ser explícita quando necessária. O objetivo posterior de US$ 1.500 não estabelece prazo nem obriga o sistema a produzir entradas.

| Item | Definição |
| --- | --- |
| Repositório | Separado do scanner existente; nome proposto: `mexc-futures-scanner` |
| Processamento | Python, com regras programadas |
| Agendamento | GitHub Actions, a cada 15 minutos |
| Avisos | Telegram |
| Modalidades | Antecipada e confirmada, avaliadas separadamente |
| Padrões iniciais | Continuação após correção; rompimento de consolidação |
| Perda planejada | Até 30% do saldo antes da operação, incluindo custos estimados |
| Ganho desejado | 60% líquido sobre esse saldo, quando a geometria e a execução comportarem |
| Margem | Isolada; uma posição real por vez |
| Alavancagem | A menor que viabilize o tamanho calculado, limitada inicialmente a 20x e ao limite do contrato/conta |
| Validade do plano | Até 30 minutos desde sua criação; pode terminar antes |
| Pausa | 24 horas após consumir integralmente o orçamento de perda de um plano dimensionado próximo do teto de 30% |
| IA em cada rodada | Não é necessária nesta versão |

O teto de 20x, a validade de 30 minutos e a pausa de 24 horas são decisões técnicas provisórias. A perda de 30% continua sendo elevada, e o stop representa uma perda planejada, não uma garantia de execução nesse limite.

## 2. Separar leitura do mercado de viabilidade financeira

Cada plano tem dois resultados independentes:

- **Situação técnica:** existe ou não um padrão válido e qual modalidade cumpriu seu gatilho.
- **Situação financeira/operacional:** a quantidade mínima, os custos, a margem e o preço permitem executar esse plano com o saldo informado.

Um padrão tecnicamente válido que não caiba em USDT 1 continuará registrado como oportunidade técnica, com o motivo financeiro do bloqueio. Ele não será apresentado como entrada real liberada. Isso permite medir oportunidades sem confundir filtros de mercado com limitações da banca.

## 3. Universo e dados

### 3.1 Seleção de contratos

Selecionar até 50 contratos ativos de cripto, perpétuos, cotados e liquidados em USDT, ordenados pelo valor financeiro negociado em 24 horas. Usar o valor financeiro, não a quantidade de contratos, para comparar instrumentos.

Não priorizar ativos citados anteriormente pelo usuário. Excluir contratos de ações, índices, commodities e outros produtos que não sejam cripto. Verificar a classificação pelos metadados disponíveis e por uma lista de classificação versionada; se a classificação for desconhecida, registrar a pendência.

Filtro inicial de liquidez: valor financeiro de 24 horas de pelo menos USDT 5 milhões. Esse valor é uma hipótese, não evidência de liquidez suficiente. O livro e o custo de execução também serão verificados. Se houver menos de 50 elegíveis, analisar a quantidade disponível e informar a cobertura real.

Na partida, solicitar ao menos 240 candles fechados de 1h e 480 de 15m por contrato. Falta de histórico gera diagnóstico de cobertura, sem preencher preços artificialmente. Ativos já acompanhados continuam sendo atualizados até o encerramento de seus planos, mesmo se saírem da seleção principal.

### 3.2 Períodos e fechamento

- **2h:** contexto e regiões maiores.
- **1h:** estrutura e níveis de referência.
- **15m:** formação e gatilhos das duas modalidades.
- **1m, quando disponível:** reconstrução posterior de eventos ambíguos; não transforma uma coleta de 15 minutos em monitoramento contínuo.

A documentação da MEXC lista 15m e 1h, mas não lista 2h no endpoint de candles. Construir 2h com pares consecutivos e completos de candles de 1h, agrupados a partir de 00h UTC. Abertura do primeiro, máxima do par, mínima do par, fechamento do segundo e soma dos volumes/valores compatíveis. Não publicar um candle de 2h quando faltar qualquer componente.

Uma barra só pode participar dos cálculos após seu fechamento, confirmado pelo horário da fonte, com tolerância inicial de 10 segundos. Guardar separadamente horário do mercado, horário de consulta e horário da análise. O histórico documentado por requisição tem limite; avaliar a profundidade efetivamente recuperável antes de prometer um período de teste.

### 3.3 Integridade e atualidade

Verificar resposta da fonte, símbolo, unidade, ordenação, duplicações conflitantes, continuidade temporal, preços positivos e consistência de abertura/máxima/mínima/fechamento. Uma resposta ausente não representa preço estável.

Antes de liberar execução, consultar bid/ask e condições do contrato novamente. Se passaram mais de 60 segundos entre essa consulta e a montagem do aviso, atualizar a cotação. Não tratar o horário de download como prova de que a informação de mercado está atual. Se a fonte não permitir verificar a atualidade, marcar `DADOS_NAO_VERIFICADOS` e emitir apenas diagnóstico/observação.

Históricos incompletos, cotação inválida ou falha de persistência impedem novas liberações. Preservar os planos anteriores e registrar a falha; não substituí-los por dados inventados.

## 4. Definições comuns das estratégias

### 4.1 Volatilidade e pivôs

Usar ATR de 14 períodos, pelo método de Wilder, sobre candles fechados de 15m. Documentar a inicialização e manter o mesmo cálculo em histórico e acompanhamento. ATR será usado para tolerâncias, não como confirmação direcional.

Um topo pivô tem máxima estritamente maior que as máximas dos dois candles anteriores e dos dois seguintes; fundo pivô usa mínimas estritamente menores. A confirmação só existe após o fechamento do segundo candle seguinte. Empates não formam pivô nesta versão.

Registrar tanto o horário do pivô quanto o horário em que ele se tornou conhecido. No teste, usar somente pivôs que já eram conhecidos no instante da decisão.

Em 1h e 2h, classificar a estrutura pelas duas últimas máximas e duas últimas mínimas pivôs conhecidas: ambas ascendentes = alta; ambas descendentes = baixa; demais combinações = indefinida. Sem pivôs suficientes, contexto desconhecido.

O contexto de 2h será informado e usado para comparação entre candidatos. Não será uma exigência universal de alinhamento. Continuação exige estrutura direcional de 1h; rompimento usa sua própria formação e pode surgir com 1h indefinida.

### 4.2 Congelar a hipótese e preservar revisões

Cada plano armazena símbolo, direção, padrão, níveis de referência, ATR de referência, gatilhos, invalidação, horário de criação e expiração. Formação, níveis, ATR, gatilhos e prazo ficam congelados durante a sua validade. Stop e alvo que ainda dependam do primeiro gatilho serão identificados como provisórios ou indisponíveis. Ao ocorrer esse gatilho, fixar os valores finais em uma revisão explícita, antes de qualquer liberação. Uma correção material exige revisão identificada, preservando a anterior e seu motivo; não pode transformar retroativamente uma entrada inválida em válida.

Após uma execução, nunca ampliar o stop nem recalcular o alvo para ocultar falha da hipótese. A v0.1 não usa preço médio contra a posição, martingale, saídas parciais ou trailing stop.

Modalidade e estado são dimensões separadas. As condições `antecipada_valida` e `confirmada_valida` podem ser avaliadas sem obrigar uma sequência de execução. Estar confirmado significa que o gatilho daquela regra ocorreu, sem probabilidade de lucro presumida.

Cada modalidade tem sua própria faixa, alvo e dimensionamento, calculados com a informação disponível no seu gatilho. O surgimento da confirmada não altera uma posição já executada pela antecipada. Um stop compartilhado entre as modalidades permanece congelado.

Um aviso POSSIVEL anterior não é requisito para liberar um gatilho. Formação e gatilho podem ser reconhecidos na mesma rodada, desde que a formação seja reconstruída somente com dados que já existiam antes do candle de gatilho e a cotação atual continue permitida. Registrar separadamente o instante da formação e o instante de detecção. A validade termina 30 minutos após a formação elegível; uma descoberta tardia não reinicia o relógio. Não simular uma execução anterior ao instante em que o aviso poderia ter sido recebido.

## 5. Estratégia A — Continuação após correção

### 5.1 LONG

**Formação:** estrutura de alta em 1h. Identificar o rompimento mais recente de um topo pivô conhecido, ocorrido nas últimas 12 barras fechadas de 1h. O rompimento exige fechamento anterior no nível ou abaixo dele e fechamento seguinte acima. O topo precisa ter sido conhecido antes do rompimento. O nível rompido será `L`.

Fixar `A`, o ATR de 15m conhecido na formação do plano. Região de interesse: `L ± 0,25A`. A aproximação pelo lado superior, até `L + 0,75A`, permite emitir preparação, mantendo a estrutura de referência. O primeiro candle que alcance essa faixa de aproximação define a formação elegível e inicia a validade de 30 minutos. Se o próprio candle de reação for o primeiro a alcançar a faixa, ele pode formar e ativar o plano na mesma análise; usar o ATR e a estrutura conhecidos antes de sua abertura. Uma preparação anterior não é obrigatória. Antes da reação, o stop é apenas indicativo: o menor valor entre a mínima das oito barras anteriores menos `0,10A` e `L − 0,35A`.

**Gatilho antecipado:** um candle fechado de 15m toca a região e fecha acima de `L + 0,25A`, sem invalidação anterior do plano. Tocar significa que sua máxima e mínima interceptaram a região. Esse candle é o candle de reação. Uma mínima intrabar abaixo da região seguida de recuperação não constitui, sozinha, invalidação por fechamento.

**Gatilho confirmado:** depois da reação, um candle fechado de 15m fecha acima da máxima do candle de reação, sem invalidação intermediária. Se essa condição não ocorrer dentro da validade, a modalidade confirmada expira; a antecipada não depende dela.

**Stop:** no fechamento da reação, fixar o menor valor entre a mínima da reação e a mínima das sete barras de 15m imediatamente anteriores, menos `0,10A`. Registrar a revisão do valor indicativo para o definitivo. Depois desse instante, o stop é compartilhado pelas modalidades e não será ampliado. Um toque posterior ao gatilho e anterior à entrada encerra a possibilidade de executar esse plano. Não contar uma mínima anterior ao fechamento que criou o stop como uma saída de posição inexistente.

**Alvo técnico:** no gatilho de cada modalidade, calcular uma projeção inicial de 2,5 vezes a distância entre o fechamento do gatilho e o stop. Se houver topo pivô conhecido de 1h/2h acima do fechamento e antes da projeção, usar a região mais próxima, reduzida de `0,10A`. Identificar explicitamente se o alvo veio de uma região observada ou de uma projeção. A verificação financeira poderá bloquear um alvo sem retorno líquido suficiente.

**Invalidação de novas entradas:** após fixado, toque no stop; fechamento de 15m abaixo de `L − 0,25A`; perda da estrutura de 1h; expiração. Caso os critérios de invalidação já existentes e um novo gatilho apareçam no mesmo candle, prevalece a invalidação. Um candle que iniciou a formação não será invalidado retroativamente por um stop que ainda não existia.

### 5.2 SHORT

Aplicar as condições espelhadas: estrutura de baixa em 1h; rompimento descendente de fundo pivô conhecido; retorno à região pelo lado inferior; reação fechando abaixo da região; confirmação abaixo da mínima da reação. Stop definitivo acima da maior máxima entre o candle de reação e as sete barras anteriores, mais `0,10A`; alvo e invalidação com sinais invertidos.

## 6. Estratégia B — Rompimento de consolidação

### 6.1 Formação e plano possível

Avaliar janelas de oito candles fechados de 15m. Definir teto `U`, piso `D` e largura `W = U − D`. Com ATR de referência `A`, exigir largura entre `1A` e `4A`, pelo menos dois candles com máxima a até `0,25A` de `U` e dois com mínima a até `0,25A` de `D`. Um candle pode contribuir para ambos os lados.

Essas são regras de formação do padrão, não indicadores adicionais de confirmação. Congelar a primeira janela que qualificar e registrar planos possíveis para os dois sentidos, com a mesma identificação da faixa. Priorizar o aviso de preparação quando a cotação estiver a até `0,50A` de uma borda. Não recriar a faixa a cada candle para acompanhar o preço.

### 6.2 LONG

**Gatilho antecipado:** primeiro candle posterior à formação fecha acima de `U + 0,10A`.

**Gatilho confirmado:** o candle imediatamente seguinte também fecha acima de `U + 0,10A`, sem atingir o stop nesse intervalo. Não exigir reteste. Se falhar, a modalidade confirmada daquele rompimento é encerrada.

**Stop:** `U − 0,50A`, congelado desde a formação.

**Alvo técnico:** projeção `U + W`, limitada pela região contrária conhecida mais próxima de 1h/2h, com margem de `0,10A` antes dela. Se a entrada já estiver próxima do alvo e a relação líquida não couber, registrar o sinal como tardio ou financeiramente inviável.

**Invalidação de novas entradas:** após o fechamento que gerou o primeiro rompimento, toque no stop ou fechamento de 15m de volta no nível `U` ou abaixo dele; expiração. Antes do primeiro gatilho, o stop projetado não invalida uma posição que ainda não foi formada. Assim, a mínima do candle que rompeu não será interpretada como stop ocorrido antes de uma entrada pelo seu fechamento. A avaliação do SHORT é independente enquanto sua própria formação permanecer válida.

### 6.3 SHORT

Espelhar as condições: fechamento abaixo de `D − 0,10A`, segundo fechamento para a modalidade confirmada, stop `D + 0,50A`, projeção `D − W` e invalidação pelo retorno fechado ao nível `D` ou acima dele, toque no stop ou expiração.

## 7. Faixa de entrada e prevenção de atraso

Para cada modalidade, o fechamento de seu candle de gatilho será o preço de referência `E0`. A faixa inicial é `E0 ± 0,25A`.

No LONG, o limite inferior também deve ficar acima do nível recuperado/rompido exigido pelo gatilho, com pelo menos um incremento mínimo de preço. No SHORT, aplicar o limite superior espelhado. Em ambos, a faixa deverá ser reduzida se necessário para preservar o retorno/risco líquido e a viabilidade no pior preço permitido.

Uma faixa vazia gera `PRECO_FORA_DO_PLANO`. Uma faixa não vazia não dispensa cotação atual: verificar ask para LONG e bid para SHORT, profundidade e quantidade. Valores do stop/alvo e quantidades devem respeitar os incrementos do contrato.

Se o gatilho ocorreu entre duas rodadas, recuperar os candles faltantes e verificar invalidações intermediárias. Um gatilho que já atingiu alvo/stop antes da notificação será registrado como evento passado, nunca como entrada executada pelo usuário. Se a ordem dos eventos for desconhecida, marcar ambiguidade e não liberar o plano antigo.

Não aplicar uma espera universal de vários candles depois de um plano terminal. Exigir um novo evento observável: outra reação após uma nova aproximação à região na estratégia A, ou uma nova janela de consolidação seguida de novo rompimento na estratégia B. Um gatilho antigo não pode ser reapresentado com novo horário para renovar sua validade. Vincular formações relacionadas à mesma família de eventos para evitar contagem duplicada de oportunidades.

## 8. Dimensionamento, custos e limites

### 8.1 Orçamento

Usar `B`, o saldo disponível verificado antes da operação. Orçamento máximo de perda: `0,30B`; ganho desejado: `0,60B`. O alvo técnico nasce do padrão, sem ser afastado apenas para produzir a porcentagem desejada.

No pior preço da faixa, estimar para cada quantidade permitida: perda no stop, ganho no alvo, taxas de abertura/fechamento, diferença de execução, margem necessária e custo de funding no cenário de permanência. A quantidade deve respeitar todos os incrementos e mínimos.

Escolher a menor quantidade permitida que projete ganho líquido de pelo menos `0,60B`, desde que sua perda projetada seja no máximo `0,30B`, seu retorno/risco líquido seja pelo menos 2 e ela caiba na margem disponível. Se nenhuma quantidade satisfizer o conjunto, preservar a leitura técnica e marcar `INVIAVEL_PARA_BANCA`.

Isso pode resultar em risco menor que 30%. A redução de exposição e seu efeito no ganho serão mostrados explicitamente. Não prometer ganho de 60% se a quantidade escolhida projetar menos.

### 8.2 Hipóteses de custo

Usar as taxas aplicáveis à execução manual na conta, incluindo o tipo de ordem esperado. Metadados públicos e promoções não serão automaticamente tratados como a taxa pessoal do usuário. Sem taxa verificada, produzir somente avaliação simulada com a hipótese de custo explicitada; não liberar execução real.

Para a primeira simulação, considerar execução taker na entrada e nas saídas. Em cada lado, usar a execução estimada no livro e um acréscimo adverso de pelo menos dois incrementos de preço ou 0,02% do preço, o que for maior. Esse acréscimo é uma hipótese de simulação e será submetido a cenários de custo maiores; não limita o deslizamento real.

Adotar seis horas como horizonte inicial da estimativa de funding, informando a taxa, a periodicidade consultada e a hipótese de manutenção dessa taxa. Não antecipar recebimentos de funding como lucro garantido. Taxas futuras podem mudar. O horizonte de custo não é uma promessa de duração da operação; se ele for ultrapassado, avisar para reavaliação e contabilizar o custo real disponível.

Se o custo total projetado de execução e funding consumir mais de 10% do orçamento de perda, bloquear a execução na configuração inicial, mantendo o diagnóstico técnico. Essa tolerância também será avaliada em testes.

### 8.3 Margem e alavancagem

Depois de determinar a quantidade, selecionar a menor alavancagem permitida que comporte margem e reserva para custos. Respeitar simultaneamente teto de 20x, regras da conta, região e contrato. Verificar o preço de liquidação usando os parâmetros aplicáveis, incluindo manutenção e taxas relevantes.

Exigir que o stop fique antes da liquidação e que a distância da entrada à liquidação seja pelo menos 1,5 vez a distância da entrada ao stop. Esse fator é uma margem de projeto provisória, não uma garantia contra liquidação. Sem informação suficiente para verificar a condição, bloquear execução real.

Informar o tipo de preço que dispara TP/SL. Usar o último preço somente quando permitido pelo contrato; se ele exigir preço justo, indicar essa exigência e usar a série compatível para verificar o disparo. Não pressupor que último preço e preço justo coincidam. Sem dados para essa verificação, os resultados de execução permanecerão identificados como estimativas.

Não aproximar o stop técnico nem elevar o teto de alavancagem para fazer um contrato caber em USDT 1. Desativar acréscimo automático de margem no plano operacional; a configuração real da plataforma precisa ser verificada pelo usuário.

### 8.4 Pausa e marco de revisão

O orçamento de perda e o saldo de referência ficam registrados em USDT. Um stop integral de uma operação que tenha sido dimensionada para consumir ao menos 95% do teto de perda de 30%, ou uma perda real igual/superior a 30% do saldo anterior à operação, ativa pausa de 24 horas para novas entradas reais. A tolerância de 95% identifica arredondamentos de lote próximos do orçamento integral; não aumenta o teto de perda.

Durante a pausa, continuar coletando e avaliando sinais em simulação. Não recuperar perdas aumentando a exposição. Ao completar a pausa, verificar dados, saldo e ausência de posição antes de voltar a avaliar execução real.

Ao alcançar o equivalente a US$ 100 com posições encerradas, marcar `REVISAO_DA_FASE` e suspender a reutilização automática deste modelo de risco até estabelecer os parâmetros da próxima fase.

## 9. Estados, continuidade e posição real

| Estado técnico | Significado |
| --- | --- |
| POSSIVEL | Formação identificada; gatilhos ainda pendentes |
| ATIVO | Uma ou ambas as modalidades cumpriram suas regras |
| INVALIDADO | A hipótese perdeu a validade |
| EXPIRADO | O prazo terminou |
| EVENTO_PASSADO | Gatilho ocorreu, mas não é uma entrada atual |
| AMBIGUO | Dados não permitem resolver a sequência necessária |

Além do estado, guardar modalidade, motivo, viabilidade, modo de avaliação (simulado/real) e situação de execução.

Planos possíveis válidos são preservados entre rodadas. Invalidado/expirado não volta a ativo; uma formação nova recebe nova identificação. A passagem do tempo não adiciona confirmações obrigatórias.

O scanner de dados públicos não sabe se o usuário executou uma ordem. Para a v0.1, o registro manual será feito por uma execução específica do GitHub Actions com entradas estruturadas: identificação do plano, entrada executada ou não executada, quantidade, preço e horário. Saídas informam preço, quantidade, resultado e taxas reais. O Telegram será inicialmente um canal de saída; comandos recebidos por ele exigiriam outro fluxo e ficam fora da primeira implementação.

Uma indicação selecionada para execução real ficará com situação `AGUARDANDO_REGISTRO`. Sem confirmação de entrada ou de não execução, não liberar uma segunda indicação como disponível para a mesma banca. Continuar mostrando candidatos como observações. O vencimento do sinal não será interpretado como prova de que não houve execução.

Quando uma posição for registrada, suspender novas liberações reais até registrar encerramento. Cancelar alternativas pendentes para execução real; preservá-las apenas no acompanhamento comparativo simulado. O scanner não cancela ordens na corretora nesta versão: o usuário deve cancelar as pendências que tiver criado.

A validade de 30 minutos refere-se ao plano de entrada. Não encerra uma posição já aberta. Após entrar, os níveis originalmente registrados de stop e alvo prevalecem; avisos posteriores de contexto serão identificados como reavaliações, sem alterar os níveis silenciosamente.

## 10. Alertas do Telegram

Usar aviso de preparação quando surgir um plano possível, aviso de mudança quando uma modalidade cumprir o gatilho e aviso terminal na invalidação/expiração. Não repetir a mesma mensagem em toda rodada.

Todos os avisos exibem modo SIMULAÇÃO ou REAL, identificação e revisão, símbolo, direção, padrão, modalidade, horário da análise e horário dos dados. Mostrar critérios cumpridos, condição pendente, faixa de preço, stop, alvo técnico/projetado, validade, viabilidade e motivo de eventual bloqueio.

Para execução real disponível, acrescentar quantidade, margem estimada, alavancagem, ganho/perda em USDT e percentuais do saldo, taxas usadas, hipótese de funding e retorno/risco líquido no pior preço. Se não houver dado necessário, mostrar o campo como indisponível e manter o bloqueio correspondente.

Exemplo de preparação — campos entre colchetes são marcadores, não dados de mercado:

```text
SIMULAÇÃO | ENTRADA POSSÍVEL
[ID] • [ATIVO] • [LONG/SHORT] • [PADRÃO]
Dados: [horário BRT] | Análise: [horário BRT]
Região: [limite inferior] a [limite superior]
Antecipada: válida se [condição objetiva].
Confirmada: válida se [condição objetiva].
Invalidação: [preço/condição].
Plano expira: [horário BRT].
Viabilidade para o saldo: [resultado e motivo].
```

Exemplo de liberação:

```text
[SIMULAÇÃO/REAL] | GATILHO CUMPRIDO — [MODALIDADE]
[ID/revisão] • [ATIVO] • [LONG/SHORT]
Motivo: [evento observado e horário].
Entrada permitida: [faixa] | Cotação consultada: [preço/horário].
SL: [preço] | Alvo: [preço e origem].
Quantidade: [contratos/unidade] | Margem: [USDT] | Alavancagem: [x].
Perda planejada: [USDT/%] | Ganho projetado: [USDT/%].
Retorno/risco líquido no pior preço: [valor].
Custos considerados: [hipóteses].
Disponibilidade de execução: [sim/não/motivo].
Válido até [horário], sujeito à faixa e à invalidação.
```

Se houver vários candidatos, informar todos os tecnicamente válidos no relatório e selecionar no máximo uma indicação disponível para a banca. Desempate determinístico: maior retorno/risco líquido no pior preço, menor custo relativo ao risco, menor diferença entre preço atual e referência; persistindo empate, ordem alfabética do símbolo. Não chamar esse ordenamento de probabilidade de sucesso.

Produzir resumo diário, propondo inicialmente 21h de Brasília: cobertura, sinais, falhas, resultados e pendências, inclusive quando não houver entradas. O horário é proposta de projeto, não agendamento criado.

## 11. Execução futura no GitHub

Proposta de horários: minutos 02, 17, 32 e 47 de cada hora, buscando dados após os fechamentos de 15m. O GitHub pode atrasar ou descartar execuções; a estratégia deve tolerar isso sem anunciar sinais vencidos como atuais.

Cada rodada recupera o estado persistido, coleta novos dados, reconcilia os intervalos desde a rodada anterior, avalia todos os contratos elegíveis, aplica regras e custos, grava o estado e então entrega as notificações pendentes. O agendamento precisará estar na branch padrão.

Cada atualização terá identificação idempotente: falhas e novas tentativas não criam planos ou registros de operação duplicados. Usar uma fila persistida de notificações; como a API de mensagens pode responder de forma ambígua após envio, não prometer entrega exatamente uma vez. Usar a mesma identificação em eventual repetição para que o usuário reconheça o aviso.

Preservar apenas uma rodada gravadora por vez e não cancelar uma gravação em andamento para começar outra. Se o estado anterior não puder ser recuperado, interromper novas liberações. Arquivos locais temporários, cache e logs com retenção não serão a única cópia do estado.

Definir a visibilidade do repositório antes da criação. Código e dados públicos de mercado podem ser públicos; saldo real, diário pessoal e credenciais precisam de acesso restrito. Uma branch de um repositório público não oferece privacidade. A solução de persistência dos registros reais será fechada antes de habilitar o modo real.

Configurar token do bot e destino do Telegram em mecanismos apropriados de configuração/segredos quando houver implementação. A coleta pública não requer permissão de ordens. A integração com a conta real não faz parte desta versão.

## 12. Validação e critérios para avançar

1. Confirmar, em execução real do coletor, acesso à API, unidades, atualidade e histórico efetivamente recuperável. Documentação consultada não substitui esse teste.
2. Confirmar os mínimos e custos relevantes para o saldo inicial. Registrar se a combinação de meta, risco e teto de alavancagem gera alguma quantidade executável.
3. Reproduzir casos sintéticos das duas direções, incluindo gatilho sem reteste, antecipada válida com confirmada pendente, formação e gatilho descobertos na mesma rodada, stop inexistente no início de um candle, plano vencido, quantidade mínima incompatível e evento de alvo/stop anterior ao alerta.
4. Testar em histórico preservando o instante em que cada informação se tornou conhecida. Separar períodos de ajuste e avaliação; registrar o número de variantes testadas. Custos, livro e universo atuais não serão usados como se fossem observações históricas: recuperar os dados da época ou identificar explicitamente as hipóteses e o viés de selecionar somente ativos atuais. Se faltarem dados para avaliação independente, declarar evidência insuficiente.
5. Comparar antecipada e confirmada nas mesmas formações, usando entradas possíveis no momento da decisão e custos explícitos. Fazer também uma simulação de carteira com uma posição por vez e a regra de pausa; não somar lucros de alternativas mutuamente exclusivas.
6. Se um candle atingir stop e alvo, buscar granularidade menor. Persistindo ambiguidade, separar o caso e apresentar um resultado pessimista de sensibilidade; nunca atribuir automaticamente o alvo primeiro.
7. Acompanhar sinais novos em simulação, medindo atrasos, avisos perdidos, faixas já ultrapassadas e diferença entre resultado histórico e operação observável.
8. Antes de utilizar sinais para execução real, verificar taxas da conta, persistência privada, registro de posições, entrega dos alertas e execução de TP/SL com os limites do contrato. Sem evidência de viabilidade, manter a avaliação simulada.

Métricas: cobertura de dados e contratos, quantidade de formações, liberações por modalidade, motivos de bloqueio, ganhos/perdas líquidos, retorno composto, queda máxima, sequência de perdas, custo relativo ao risco, duração e atraso dos sinais, oportunidades antecipadas que falharam e oportunidades que desapareceram enquanto se aguardava confirmação.

Cada filtro adicional será comparado com a versão anterior em dados de avaliação. Não selecionar regras apenas pelas oportunidades que teriam dado lucro. Sem amostra suficiente, não apresentar porcentagem de confiança nem estimar prazo para alcançar US$ 100.

O documento não comprova rentabilidade. Nesta etapa, somente a documentação das interfaces foi consultada; nenhum resultado de backtest, coleta em produção ou entrega de Telegram foi obtido.

## 13. Fontes oficiais consultadas

As fontes documentam interfaces e limitações. Os valores e regras das estratégias são propostas próprias de projeto e não são recomendações ou resultados dessas fontes.

- [MEXC — Introdução da API de futuros](https://www.mexc.com/api-docs/futures/integration-guide): acesso público e privado.
- [MEXC — Candles](https://www.mexc.com/api-docs/futures/market-endpoints/get-candlestick-data): intervalos documentados e limite de pontos por consulta.
- [MEXC — Informações de contratos](https://www.mexc.com/api-docs/futures/market-endpoints/get-contract-info): tamanho, incrementos, taxas e parâmetros de margem.
- [MEXC — Ticker](https://www.mexc.com/api-docs/futures/market-endpoints/get-ticker-contract-market-data): preços, valor financeiro, bid/ask e funding.
- [MEXC — Liquidação em futuros](https://www.mexc.com/support/article/faq-on-liquidation-for-futures-trading-8123281969561): manutenção e liquidação.
- [GitHub — Eventos e agendamentos](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule): atrasos, branch padrão e execução agendada.
- [Telegram — Bot API](https://core.telegram.org/bots/api#sendmessage): entrega de mensagens pelo bot.
- [CME — Plano de negociação](https://www.cmegroup.com/education/courses/building-a-trade-plan/trading-strategies-in-your-trade-plan): critérios de formação, gatilho e saída.
- [CFTC — Limitações de sistemas de negociação e simulações](https://www.cftc.gov/LearnAndProtect/AdvisoriesAndArticles/fraudadv_tradingsystem.html): custos, execução e limites de resultados hipotéticos.
