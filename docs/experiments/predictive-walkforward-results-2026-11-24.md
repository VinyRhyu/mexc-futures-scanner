# Resultados da pesquisa paralela: P(TP antes do SL) no histórico de 2026-10-26 a 2026-11-22

**Executada:** 24/11/2026. Run CI verificado: [#45426233293](https://github.com/VinyRhyu/mexc-futures-scanner/actions/runs/45426233293), **SUCCESS**. Testes: **9 do modelo + 293 regressões do scanner aprovados**. Artefato: `predictive-walkforward-45280197720-45426233293` com relatório JSON, previsões por evento CSV e carteira paper por variante JSON.

**Decisão atual: não existe evidência estatística de vantagem preditiva; o filtro preditivo NÃO deve ser ativado em PRD.**

## Amostra e metodologia

224 eventos viáveis financeiramente no modelo histórico de 24 símbolos congelados, exportados dos mesmos cinco conjuntos do run #45280197720. Partições pré-declaradas: **125 treino (47 TP), 42 validação (8 TP) e 57 teste retrospectivo (14 TP)**, sem uso de rótulos futuros na função de features, sem treino nos períodos de validação/teste e sem busca do melhor threshold. Classificador: regressão logística regularizada L2 e escalonamento apenas no conjunto de treino. Nenhuma ordem foi executada.

### Qualidade probabilística

| Medida | Validação (42 eventos) | Teste retrospectivo (57 eventos) |
|---|---:|---:|
| TP real em até 4h | 8 (19,05%) | 14 (24,56%) |
| TP em treino, usado como baseline fixo | 37,60% | 37,60% |
| Brier modelo (menor é melhor) | **0,2168** | **0,2668** |
| Brier previsão constante a partir do treino | **0,1886** | **0,2023** |
| AUC-ROC (0,5 = ranking aleatório) | **0,4154** | **0,2691** |
| P média atribuída às operações que chegaram ao TP | 34,87% | 28,34% |
| P média atribuída às operações que não chegaram ao TP | 38,63% | 40,06% |

**Falha dupla:** Brier pior que a frequência histórica constante, e ranking AUC inferior a 0,5 em ambos os blocos. No teste, o modelo deu probabilidade maior às entradas **não vencedoras**. Essa observação pode decorrer de mudança de regime, sinais limitados e overfitting; não justifica automaticamente inverter o score em produção porque isso seria reajuste sobre os dados já vistos.

### Resultados financeiros comparados: uma posição por vez

Todos os P&Ls da tabela já são líquidos segundo as hipóteses de execução no CSV histórico original, cada trade usando o **tamanho hipotético fixo definido para 1 USDT em cada evento**. Não compõem a conta, não representam saldo final 1 USDT e não incluem funding real nem fills.

| Regra | Validação: operações | Validação: TP | Validação: P&L fixo | Teste: operações | Teste: TP | Teste: P&L fixo |
|---|---:|---:|---:|---:|---:|---:|
| Confirmação, RR >=1 | 15 | 4 | −0,1057 USDT | 30 | 9 | −0,3699 USDT |
| Confirmação, RR >=1,5 | 8 | 1 | −0,2002 USDT | 7 | 1 | −0,2052 USDT |
| Preditivo, gate expectativa positiva | 7 | **0** | **−0,3653 USDT** | 7 | 2 | **−0,0131 USDT** |
| Híbrido: RR >=1,5 + preditivo | 7 | 0 | −0,3653 USDT | 5 | 1 | −0,0496 USDT |

Embora o preditivo tenha **prejuízo monetário menor** na última janela (7 entradas), ele falhou na validação e o P&L permaneceu negativo. Há uma distinção relevante: no teste o preditivo somou **+0,2697 R** em unidades não monetárias, mas **−0,0131 USDT líquidos** devido às diferenças de tamanho/risco e desfecho de cada posição. Por isso não atribuir lucro em moeda apenas por net_R agregado.

## Interpretação e restrições

1. **Rejeitar a hipótese de edge comprovado neste modelo inicial.** O desempenho preditivo de validação e teste é pior que benchmark simples; nenhum dos cenários atingiu lucro líquido nas duas partições.
2. **Não é modelo pré-rompimento.** Features incluem segundo M1 já confirmado; ainda é um classificador de qualidade de confirmação e não encontra entradas antecipadas. Não trocar tendência por um rótulo de IA.
3. **Histórico já explorado:** o último bloco não era intocado; os 24 símbolos foram congelados no presente. Não atribuir confiabilidade à pequena amostra, nem vender taxa diária ou 35% de ROI sobre margem.
4. **Tamanho de ordem e custos:** a fonte utiliza lotes financeiros de conta papel fixa em 1 USDT, stop-first intrabar, spread/slippage e taxas hipotéticas. Não há capital composto, liquidação real, funding contemporâneo nem livros de ofertas históricos.
5. **Próxima pesquisa com potencial científico:** desenvolver conjunto prospectivo **antes do primeiro rompimento**, com amostragem inclusive de não-eventos e rótulos de movimentos favoráveis/desfavoráveis futuros, múltiplos horizontes 15/30/60min; exige dados históricos completos, custo/risco e teste cronológico realmente não inspecionado. Só então comparar antecipação real contra confirmação convencional em mesmas moedas e mesmos períodos.
6. **Produção intacta:** nada de merge, `main`, `scan.yml`, cronjob.org, carteira, Telegram, RR, TP, SL ou alavancagem. Research/PR permanece **draft**.

Código: `scripts/research_predictive_walkforward.py`; testes `tests/test_research_predictive_walkforward.py`; dados primários source: artifact run #45280197720; resultados reproduzidos em Actions #45426233293.
