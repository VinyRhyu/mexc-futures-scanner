# V4 — confirmação de falso rompimento (SHORT), hipótese congelada

Data de formulação: 2026-11-20. Este arquivo foi criado **antes** de executar o replay V4. Pesquisa em modo paper: sem integração com Telegram, main ou execução de ordens.

## Base factual

A regra F de rejeição da v3 foi exploratória e terminou em 27 operações selecionadas, 9 TP, 15 SL e 3 TIME, ROI composto -2,237% (risco de 1% do capital por trade) em 28/08–09/10/2026. A proposta é corrigir entradas precoces, sem ajustar seus parâmetros retrospectivamente.

## Única variante pré-registrada: F_confirm_1bar

1. O candle de rejeição M5 original precisa cumprir **todos os requisitos da regra F congelada** em scripts/audit_confluence_v3.py: H1 fechado abaixo EMA20, sweep acima da resistência de 24 M5 anteriores por 0,10 ATR14, fechamento abaixo da resistência e da abertura, pavio superior >=40% da amplitude, true range 0,8–3 ATR, volume financeiro >=1,5x a mediana dos 12 M5 anteriores.
2. Não entrar no próximo open. **Esperar exatamente o próximo M5 fechar**. Confirmar SHORT somente se o M5 seguinte for vermelho e seu fechamento ficar estritamente abaixo da mínima do candle de sweep. Cancelar se a máxima do M5 seguinte já atingir o stop estrutural do setup original. Caso contrário, sem sinal. Não estender o prazo esperando mais candles.
3. O sinal só existe no **fechamento** do M5 confirmador; entrada hipotética no open do M5 seguinte. Stop é **mantido** na máxima do M5 de sweep + 0,10 ATR (congelado no sinal original), TP é 1,8x distância entre entrada simulada e stop, RR líquido ex ante >=1,2, timeout 120 min. Não mover níveis depois.
4. Custos hipotéticos idênticos: taker 0,06% por lado e slippage 0,02% por lado. SL/TP no mesmo M5 OHLC -> AMBIGUOUS, tratar como -1R no portfólio. Uma única posição aberta por vez entre moedas, desempate por maior volume relativo conhecido no momento do sinal; sem reentrada por símbolo até encerramento.
5. Não usar candlestick H1 não fechado, nenhuma barra M5 após o confirmador e nenhum valor futuro para **gerar** o sinal. Futuro apenas para aferir desfecho no replay.
6. Registro adicional: número de sweeps F detectados, quantos confirmaram e quantos sinais F foram cancelados; comportamento de wins/stops/timeouts e custos. Regra F original e F_confirm são testadas **com a mesma fonte MEXC e datas**.

## Datas fixadas antes de rodar

10 ativos fixos: TAO, SOL, AVAX, ENA, DOT, ZEC, HYPE, AAVE, BTC, ETH.

- Período U (menos inspecionado): **2026-07-17 11:00 UTC a 2026-08-28 11:00 UTC**, 42 dias históricos anteriores aos ensaios v3. Exigir candles completos da MEXC para declarar resultado; não preencher lacunas.
- Período V: **2026-08-28 11:00 UTC a 2026-10-09 11:00 UTC**, 42 dias já examinados na v3, apenas comparação.
- Período W: **2026-10-09 11:00 UTC a 2026-11-20 11:00 UTC**, 42 dias já examinados na v2; comparação adicional.

**A data U é histórica, não um verdadeiro teste prospectivo.** Se a API da MEXC não oferecer o período U completo, registrar falha de cobertura e não declarar validação independente. Não trocar datas em função da rentabilidade.

## Critérios exploratórios de avanço (não comprovam lucro futuro)

O novo F_confirm_1bar só vira candidato a paper prolongado caso: retorno líquido positivo em U, V e W separadamente; retorno composto positivo na janela completa; pelo menos 30 operações em todos os 126 dias; não mais que 2 operações por dia; drawdown da carteira <=10% com 1% de risco por operação; melhora sobre F original nas mesmas datas; número de stops absoluto e proporcionalmente menor sem reduzir demais a amostra. Uma falha em qualquer critério -> não integrar produção.

Nenhum desses testes compara execução real, funding, liquidação, lotes mínimos e spread durante o sinal; exigem validação específica e teste prospectivo antes de qualquer uso operacional.

## Evidência dos repositórios externos

- Acekiller88/crypto-signal-scanner: conceitos SMC/sweeps e replay causal consultados, **nenhum código incorporado**.
- freqtrade/freqtrade: metodologia de controle de lookahead e avaliação, **não integrado como motor**.
- A hipótese F_confirm é uma regra **original do nosso protótipo**, não um algoritmo validado desses repositórios.

Execução: scripts/audit_confluence_v4.py por GitHub Action isolada da pull request em rascunho.
