# Validação retroativa do filtro A — protocolo congelado em 23/11/2026

## Correção de direção metodológica

A validação solicitada é **backtesting retrospectivo**, não aguardar alertas futuros. O monitoramento recorrente Shadow A da `main` foi **desativado** em PR #10 (o workflow de observação manual permanece). Este trabalho **não modifica `scan.yml`, `engine.py`, `cronjob.org`, Telegram, configuração de produção, saldos ou ordens**.

## Hipótese congelada antes de ler os novos resultados

- **BASE**: regra atual M1, com rompimento de consolidação M15, segunda confirmação M1 de volume ≥50%, entrada simulada na abertura do próximo candle dentro da faixa, TP e SL originais, máximo 4h de duração.
- **A**: descartar o sinal quando o deslocamento do fechamento do candle M1 ao fechamento de exatamente 4 horas antes **na direção da operação** for pelo menos **2× ATR(14) M15** conhecido naquele fechamento. Sem alterar TP, SL, critérios financeiros, direção, moedas, configurações nem janelas após ver resultados.
- **B** e **A+B** continuam no relatório técnico comparativo como controle, mas a decisão proposta diz respeito somente a **A**; nenhum parâmetro será otimizado nessas novas semanas.
- Portfólio sequencial com uma posição de cada vez, **recalculado integralmente** em BASE/A para não contar sinais que se sobrepõem; custos taker estimados 0,06% por lado, spread sintético e slippage base 0,02% por ponta, stress 0,10%.
- Mesmo conjunto congelado de 12 ativos do estudo original: ORCA, S, NEO, FLOKI, TRB, SAND, ONDO, ARB, TIA, DOT, AVAX e UNI. Isso preserva comparabilidade, mas há viés de seleção e sobrevivência.
- Grupo operacional de interesse: sinais com giro USDT histórico de 24h ≥5M no momento do sinal; o backtest **não** reproduz integralmente o universo top-50 e nem profundidade histórica do livro.
- Apenas M1/M15/H1 públicos e **sem lacunas**. Resultados de M1 devem concordar com OHLC M15. Se qualquer ativo falhar, o período é marcado **INCONCLUSIVO**, sem remover a moeda difícil do denominador.

## Blocos de validação (UTC, fim exclusivo), sem interseção com os dois períodos já medidos

| Bloco | Início | Fim | Duração |
|---|---|---|---|
| H1 | 2026-10-31 00:00 | 2026-11-07 00:00 | 7 dias |
| H2 | 2026-11-14 00:00 | 2026-11-15 20:00 | 44h |
| H3, disponibilidade de histórico mais profundo | 2026-10-24 00:00 | 2026-10-31 00:00 | 7 dias |

**Importante:** o modelo M1 original já foi investigado com outros períodos, de modo que isto é um **holdout temporal para o filtro A**, mas não um teste totalmente cego e independente do desenvolvimento da estratégia. Essa distinção precisa acompanhar qualquer conclusão. A janela H3 é especialmente sensível ao limite de retenção M1 da MEXC; se não houver 100% dos candles exigidos, registrar a inviabilidade sem preencher, interpolar ou imputar.

## Critérios de decisão

Para cada bloco elegível reportar: total de operações, taxa de trades líquidos positivos, R médio e total, máxima queda realizada em R, vencedores eliminados pelo filtro, perdedores evitados, novas entradas liberadas por alterações na carteira, sensibilidade aos custos e comparação apenas do grupo ≥5M.

Uma hipótese de melhora consistente requer simultaneamente:
1. A reduz perda líquida em R contra BASE em mais de um período cronologicamente separado e preserva vitórias relevantes;
2. há **amostra quantitativamente suficiente** para discutir incerteza; períodos com poucas operações são descritivos;
3. nenhuma versão é anunciada como lucrativa enquanto a expectativa líquida continuar negativa;
4. métodos e parâmetros permanecem congelados durante a análise.

Sempre indicar se um resultado provém de sinais **financeiramente viáveis na simulação**, versus sinais técnicos isolados. MEXC OHLC não demonstra book/fill/taxas reais; estoques, financiamento e impactos de mercado permanecem hipotéticos.

## Reprodução

PR de pesquisa baseado no PR #7, sem merge na `main`. GitHub Actions `.github/workflows/research-historical-holdout.yml` executa três jobs separados, com mesma lista de moedas, carimbo UTC congelado e artefatos completos. Resultado bruto `result.json`, `contexto_viaveis.csv`, `portfolio_selecionadas.csv`, `sem_extensao_4h.csv`, etc.
