# Resultado da validação retroativa A — decisão: **NÃO VALIDADO**

Gerado em 23/11/2026 após executar filtros **congelados** (BASE vs A, sem otimização), em janelas cronológicas fora das duas semanas usadas para discutir originalmente o filtro.

- PR de pesquisa: [#11](https://github.com/VinyRhyu/mexc-futures-scanner/pull/11)
- Execução validada: [GitHub Actions #45105301547](https://github.com/VinyRhyu/mexc-futures-scanner/actions/runs/45105301547)
- Três jobs concluídos com **success**, 12/12 ativos íntegros em cada bloco e comparação OHLC M1/M15 sem divergências.
- Primeira tentativa de bloco 24–31/10 **falhou** por faltar 1.081 candles M1 por ativo (10679/11760 esperados, todos os 12 ativos). Ajuste anunciado/registrado: início em 25/10, data deslocada somente pela disponibilidade dos candles, **não** por lucro observado.

## Três novas janelas não utilizadas no desenvolvimento do filtro A

| Janela UTC (final exclusivo) | BASE: operações / vitórias | BASE (R líquido) | A: operações / vitórias | A (R líquido) | Diferença A−BASE |
| --- | --- | ---: | --- | ---: | ---: |
| 25/10–31/10 (6 dias) | 9 / 7 | +8,4839 | 4 / 4 | +4,8154 | **−3,6686 R** |
| 31/10–07/11 (7 dias) | 6 / 2 | +0,2564 | 5 / 2 | +1,2564 | **+1,0000 R** |
| 14/11 00h–15/11 20h (44h) | 8 / 2 | −2,6707 | 6 / 1 | −3,8119 | **−1,1412 R** |
| **Soma descritiva (reinicia carteira em cada bloco)** | **23 / 11** | **+6,0696** | **15 / 7** | **+2,2598** | **−3,8098 R** |

**Conclusão:** na somatória dos blocos novos, A **perdeu 3,81 R** em relação a BASE. Melhorou apenas um dos três períodos. Não aprovar a regra A em produção com essa evidência.

O intervalo de 25 a 31/10 é o principal contraexemplo: A bloqueou cinco operações da carteira BASE, incluindo **três positivas**:
- S_USDT SHORT em 29/10 23:38 UTC: +1,2036 R;
- SAND_USDT SHORT em 30/10 00:17 UTC: +1,9135 R;
- SAND_USDT LONG em 30/10 04:32 UTC: +2,5514 R, saída por tempo;
- além de dois stops de −1 R.

A regra A reduziu número de operações e apresentou **100% de resultados positivos (4/4)** no intervalo, mas mesmo assim **lucrou menos** do que BASE. É uma demonstração prática de que taxa de acerto sozinha não determina a estratégia superior.

No intervalo de 14 a 15/11, A descartou um SHORT vencedor de SAND (+1,2314 R), um resultado temporal levemente negativo de SAND (−0,0902 R), e um stop de ARB (−1 R); uma entrada substituta SHORT de S (−1 R) entrou após liberar a posição. Portanto, simplesmente remover trade perdedor da lista original produz uma estimativa enganosa.

## Recorte de maior liquidez (giro USDT 24h histórico >=5 milhões)

| Janela | BASE: trades / R | A: trades / R | Diferença |
| --- | ---: | ---: | ---: |
| 25/10–31/10 | 6 / +3,8162 R | 3 / +3,5060 R | −0,3102 R |
| 31/10–07/11 | 3 / +1,4813 R | 3 / +1,4813 R | 0 R |
| 14/11–15/11 | 5 / −2,8119 R | 4 / −1,8119 R | +1,0000 R |
| **Soma descritiva** | **14 / +2,4857 R** | **10 / +3,1754 R** | **+0,6898 R** |

**Atenção:** +0,69 R em 14 trades BASE e 10 trades A, sem reproduzir ranking top-50 nem livro histórico, é **amostra pequena e sinal fraco**, não validação. Não extrapolar a eficiência para produção, nem dizer que A possui expectativa positiva demonstrada.

## As duas semanas previamente estudadas (não são validação independente)

| Janela | BASE trades / R | A trades / R | A−BASE |
| --- | --- | --- | --- |
| 07–14/11 | 12 / −8,4828 R | 8 / −4,4828 R | +4 R |
| 15–22/11 | 14 / −8,4719 R | 9 / −3,4719 R | +5 R |

Essas duas janelas ajudam a **formular a hipótese** A. Elas não podem ser somadas às novas como se fossem cinco confirmações independentes. A discrepância entre as janelas novas e antigas é exatamente o tipo de sobreajuste retrospectivo que buscamos identificar.

## Limitações e decisão

- O modelo M1, o conjunto das 12 moedas e parâmetros de configuração ainda foram influenciados por pesquisas anteriores. Novas janelas não são verdadeiramente cegas para **todo** o desenvolvimento do projeto; são novos blocos para **testar o filtro A**.
- O teste usa M1/M15/H1 públicos, execução hipotética no próximo M1, spread 0,02%, slippage-base 0,02%, taker 0,06% por lado, preços dos contratos atuais e funding geralmente assumido. Falta histórico do livro/mercado, taxas pessoais reais e regras históricas do contrato.
- Resultados em R de carteiras sequenciais **reiniciadas por bloco** podem ser somados apenas como estatística descritiva; não representam P&L monetário nem carteira contínua sem cortes.
- Há apenas 23 operações selecionadas nos três blocos novos e diferentes sinais podem depender do mesmo movimento de preço; alta incerteza estatística.
- **Não implementar A como bloqueio em `main`.** Manter `main`, cronjob.org, Telegram e scanner principal sem alteração.
- Próximo experimento: ampliar universo **realmente elegível em produção**, gerar amostra retroativa maior com OHLC histórico completo ou dados arquivados confiáveis; depois usar separação temporal rígida, sem adaptar parâmetros no mesmo conjunto. Medir lucro líquido, perdas, vítorias descartadas e regimes de mercado. Não priorizar uma regra baseada apenas em vitória percentual.

