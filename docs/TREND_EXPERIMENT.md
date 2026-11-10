# Comparação em paper: estrutura de 1h no rompimento

O experimento compara todos os rompimentos com uma seleção que aceita LONG em
estrutura ALTA de 1h e SHORT em BAIXA. INDEFINIDA/DESCONHECIDA são excluídas.
Usa os 240 candles de 1h fechados disponíveis ao formar cada gatilho, sem esperar
outro fechamento. A classificação de estrutura é a mesma já usada pelo scanner.

Entrada, SL, TP, custos, RR líquido mínimo 2, referência de 1 USDT, risco planejado
até 10% e teto 20x ficam iguais nos dois modelos. O filtro só remove candidatos.
Antecipadas e confirmadas são avaliadas separadamente; os resultados não devem
ser somados como uma carteira.

O período reservado começa após 10/11/2026 10:58:54 UTC (07:58:54 em Brasília),
excluindo o período usado nos ajustes anteriores. A coleta prospectiva começa no
próximo fechamento de 15m após registrar o protocolo e dura 14 dias. Capturas com
mais de 120 segundos de atraso são separadas da comparação prospectiva principal.
Regras, contexto e níveis são congelados na primeira captura. Configurações ou
calculador alterados pausam a coleta; não reinicializam o teste silenciosamente.

Cada sinal tem uma janela de quatro horas. Registra alvos descartados e stops
evitados pelo filtro, além de entradas, perdas, ganhos em R e posições abertas.
Os preenchimentos são hipotéticos na abertura seguinte, com spread de 0,02%,
taxa configurada (inicialmente 0,06% por lado), slippage configurado ou dois ticks,
funding zero e profundidade infinita. Não reproduz latência ou livro históricos.
Não mede todos os movimentos do mercado que o scanner deixou de reconhecer.

O workflow de inicialização só lê dados públicos e o relatório da produção. Nas
rodadas seguintes, o último passo do workflow Scanner MEXC reutiliza a captura já
coletada. Pode complementar candles públicos se necessário. Uma falha desse passo
não faz a rodada do scanner falhar. O experimento não filtra nem envia alertas.

Resultados e protocolo ficam na branch `trend-experiment`, em `state.json` e
`latest/report.md`. O estado do scanner continua em `scanner-state`. Depois de
14 dias e mais quatro horas, o experimento congela o resultado e encerra novas
atualizações. Esse prazo não garante uma amostra suficiente para conclusão.
