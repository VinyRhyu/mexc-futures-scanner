# HYPE_USDT — replay detalhado da estratégia F — 16 a 20/11/2026

**Papel:** evidência retrospectiva para validação manual de sinais, não recomendação de entrada.

**Origem:** candles históricos públicos da API de contratos MEXC obtidos com `scripts/audit_confluence_extended.py`; replay em `scripts/audit_hype_week_20261120.py` com a estratégia F imutável (H1 EMA20 + rejeição de máxima M5). Execução GitHub Actions concluída: https://github.com/VinyRhyu/mexc-futures-scanner/actions/runs/44827384932

**Janela local fixa:** segunda 16/11/2026 00h00 a sexta 20/11/2026 19h10 (America/Sao_Paulo). Últimos candles fechados M5 até 19h10, H1 até 19h00. 1.382 M5 correspondentes a essa janela; 1.437 M5 incluindo aquecimento; 275 H1 com aquecimento. Não há candles faltantes no segmento buscado. Resultados simulados, nenhum trade real.

## Resultado com regras congeladas

- **Sinais de padrão F:** 1.
- **Sinais F com entrada permitida:** **0**.
- **Operações autorizadas com TP/SL:** **nenhuma**.
- **Motivo da rejeição única:** razão risco-retorno líquida estimada 0,934 versus mínimo exigido 1,20.

## Sinal F identificado, mas NÃO AUTORIZADO — quarta 18/11

| Campo | Valor |
|---|---|
| Fechamento do candle que confirma sinal | 18/11/2026 04h20 BRT |
| Direção | SHORT |
| Abertura seguinte, que SERIA entrada hipotética | 18/11/2026 04h20 BRT |
| Preço hipotético de entrada | 69,008 USDT |
| Stop original calculado | 69,25467857 USDT |
| TP original com 1,8R bruto | 68,56397857 USDT |
| RR líquido ex-ante | 0,934 : 1 (**abaixo do piso 1,20**) |
| Resultado de simulação contrafactual SE ignorasse o bloqueio | TP |
| Candle que toca TP | 18/11 05h10–05h15 BRT, instante exato intrabar desconhecido |
| Movimento bruto entrada até TP | +0,6434% favorável ao SHORT |
| Máxima excursão favorável até encerramento | +0,9477% (não é TP executado; candle pode ter varrido além) |
| Máxima excursão adversa até encerramento | 0,2536% |
| SL | Não foi atingido ANTES da saída hipotética por TP |

**Esta operação NÃO integra a estratégia selecionada e NÃO deve ser contada como vitória de F.** Foi observada somente para conferir como o preço evoluiu após um sinal que o filtro correto recusou. Mesmo atingindo o alvo na retrospectiva, aceitá-la reduzindo RR mínimo após ver o resultado caracterizaria sobreajuste.

**Custos modelados:** Taker 0,06% por lado; slippage hipotético 0,02% por lado; 0,16% total da posição (sem funding). Com o preço de entrada, TP teórico líquido de custos representa cerca de +0,4834% do notional de SHORT, antes de funding. O custo e o desfecho são modelos baseados em OHLC, não execuções reais.

## Evolução HYPE_USDT por dia, preço do contrato futuro em USDT

| Dia BRT | Abertura | Máxima intradia | Mínima intradia | Fechamento até corte | Retorno abertura-fechamento |
|---|---:|---:|---:|---:|---:|
| 16/11 | 66,807 | 71,010 | 64,831 | 68,789 | +2,967% |
| 17/11 | 68,789 | 70,734 | 67,300 | 68,600 | -0,275% |
| 18/11 | 68,600 | 69,310 | 65,061 | 66,630 | -2,872% |
| 19/11 | 66,630 | 70,209 | 64,481 | 66,016 | -0,922% |
| 20/11 até 19h10 | 66,016 | 66,373 | 59,763 | 61,421 | -6,960% |

A forte queda de sexta não foi capturada por F até o horário de corte: F procura rejeição de rompimento para SHORT, não continuidade generalizada de baixa. Isso não deve ser contabilizado como sinal que não existiu.

## Limites de auditoria

Horas de TP/SL são intervalos de candles M5 OHLC, não ticks. Não assumimos fills reais, spread/profundidade, funding, condições específicas de conta, limite de lote nem liquidação. Não alteramos produção, Telegram, alavancagem nem critérios originais de operação.

**Decisão:** manter F congelada; semana estudada registra zero operação autorizada e um candidato bloqueado que, se ignorado o filtro retrospectivamente, teria TP. A amostra desta semana não basta para mudar o limite de risco-retorno.
