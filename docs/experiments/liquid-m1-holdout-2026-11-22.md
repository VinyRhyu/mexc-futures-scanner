# Prioridade: validar acertos em ativos já elegíveis — M1 (22/11/2026)

## Pergunta
A configuração ativa \`m1_volume50_v1\` apresenta ganho líquido e acerto aceitável em uma janela posterior à usada na escolha do filtro, quando o capital realmente impede posições simultâneas?

## Desenho congelado antes da execução

- Janela de formações: **08/11/2026 00h até 22/11/2026 00h BRT (fim exclusivo)**. Observação por mais 5h para primeiro gatilho + saída em até 4h.
- Contratos: todos os perpétuos cripto/USDT atualmente elegíveis na MEXC pelo filtro do scanner, volume de giro >= 5 milhões USDT, até 50 maiores; nenhum ativo adicionado para o experimento.
- Comparações predefinidas: (A) dois fechamentos M1 além do nível e (B) os mesmos dois fechamentos **mais volume do segundo >= 50% do primeiro**. Exatamente a regra atual, sem alterar thresholds depois de ver o resultado.
- Dados MEXC Min1/Min15/Min60, série M1 integral e validação OHLC M1 vs M15; histórico H1 conhecido antes de cada gatilho; custos e TP/SL congelados.
- Entrada hipotética na abertura imediatamente após o segundo fechamento e execução idealizada; stop primeiro em candle ambíguo; saída após 4 horas com taxas; uma posição por vez, desempate cronológico/alfa.
- Carteiras separadas de **1 USDT (saldo configurado no paper)** e **50 USDT (sensibilidade de lote/capital)**, saldo inicial atualizado após cada encerramento; nenhuma soma de oportunidades simultâneas como se fossem uma carteira.
- RR líquido mínimo 1:1, alavancagem simulada 10x–20x, risco e margens atuais; taxas 0,06% por execução, slippage e spread simulados; funding=0. Sem contas reais, credenciais, Telegram, ordens, trade real ou merge.
- Métricas: trades executáveis, TP, SL, timeout, taxa de acerto líquida, taxa de TP em encerradas, lucro líquido, fator de lucro, R, drawdown realizado, bloqueios e completude, cortes por semana e símbolo (diagnósticos, não ranking de vencedores).

## Antes de considerar alteração de produção

1. Fonte completa e regras de causalidade verificadas. Se um dos contratos atuais falhar, reportar a falha e **não considerar a carteira parcial como evidência favorável**.
2. Resultado líquido após custos para uma posição por vez; se negativo, estratégia não aprovada.
3. Amostra suficiente, estimativas de incerteza e estabilidade semanal. Duas semanas ou poucos trades não bastam para reivindicar acerto duradouro; não usar ranking retrospectivo de símbolo para otimização.
4. Coorte prospectiva congelada adiante e taxas/execução reais para avaliar desvios entre backtest e operação antes de qualquer autorização de modo real.

## Limitações esperadas

A seleção por liquidez é feita **hoje**, e não reconstruída diariamente no passado (viés de sobrevivência); planos ativos sobrepostos do scanner de produção não são suprimidos pela coleta histórica, mas uma única posição é imposta na simulação. A janela vem depois da usada no principal estudo de volume, porém não é rigorosamente prospectiva e pode ter sido parcialmente explorada por pesquisas paralelas. Livro e spreads antigos não foram observados; fills e latência são hipóteses. A probabilidade verdadeira de acerto não pode ser garantida.

O filtro de baixa liquidez (como ORCA) fica para depois dessa auditoria dos ativos já elegíveis.
