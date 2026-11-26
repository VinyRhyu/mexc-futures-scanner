# Teste prospectivo da reversão relativa ao BTC a 2×

O scanner avalia as janelas de quatro horas nos 14 contratos do replay. O
BTC é a referência de retorno em 24 horas. A regra exige deslocamento
relativo, reação do ativo em quatro horas, alinhamento com a direção do BTC
e volume spot de pelo menos 4 milhões de USDT nas últimas 24 horas.
O sinal precisa ser registrado antes da abertura H1 uma hora após a decisão.
Janelas perdidas por atraso constam no diário.

A carteira paper parte de 1.000 USDT. O risco planejado por entrada é de
0,8% da banca e o nocional fica limitado a 75% da banca. O stop acompanha a
volatilidade, limitado de 1,7% a 5,5% do preço, e o alvo fica a 1,8 vez a
distância do stop. A regra permite até uma entrada por dia de Brasília, uma
posição por vez e saída após até 48 horas. O modelo considera custo de 0,30%
ida e volta, funding, preço justo, lote e tick.

O primeiro ciclo coleta 45 dias de decisões. A consulta de mercado termina
após o prazo das últimas posições. O diário em `paper-btc-reversal-state`
armazena as decisões e os resultados paper. O resumo aparece no GitHub
Actions. Os horários do diário são UTC. A coleção prospectiva usa GET
público e uma rotina independente do scanner principal.
