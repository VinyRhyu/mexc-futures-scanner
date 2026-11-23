# Resultado auditado — ativos líquidos MEXC, regra M1 volume50

**Período:** formações de 08/11 a 21/11/2026 (BRT), com observação até 22/11 para encerrar desfechos. **Pesquisa somente leitura**, sem ordens, Telegram ou alterações em `main`.

[Execução GitHub Actions](https://github.com/VinyRhyu/mexc-futures-scanner/actions/runs/45091438332) · [PR #5](https://github.com/VinyRhyu/mexc-futures-scanner/pull/5)

## Integridade

- 25/25 contratos atualmente elegíveis coletados e analisados; por contrato, 20.460 candles M1, 1.844 M15 e 581 H1, sem lacunas; M1/M15 confrontados por OHLC e fonte com hash.
- 18.648 formações de consolidação, 2.216 registros de confirmações após dois M1 (com **sobreposição de formações**, não eventos independentes).
- 1.309 registros mantidos pela exigência de volume do segundo M1 >= 50% do primeiro; 907 rejeitados por esse filtro.
- Duas políticas fixadas antes da execução, mesma fonte: dois M1 sem volume e os mesmos dois M1 com filtro de volume. Filtros financeiros originais de modo paper (RR mínimo 1, 10–20x, despesas de simulação) e uma posição por vez.
- Auditoria independente do arquivo `result.json`: todos os saldos conciliam com a soma cronológica dos P&Ls, nenhum dos quatro cenários apresenta sobreposição de posições, nenhuma carteira termina com saldo negativo e todas as contagens de arquivos de fontes coincidem com o manifesto.

## Carteiras cronológicas

| Método | Banca inicial | Banca final | Retorno | Trades | TP | Stop | Timeout 4h | Trades de lucro líquido | PF | DD realizado máximo |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Dois M1, sem filtro volume | 50 USDT | 6,25 | **−87,51%** | 106 | 32 | 69 | 5 | 36/106 (34,0%) | 0,70 | 91,58% |
| Dois M1, volume50 | 50 USDT | 7,76 | **−84,48%** | 78 | 21 | 54 | 3 | 24/78 (30,8%) | 0,56 | 88,99% |
| Dois M1, sem filtro volume | 1 USDT | 0,1781 | **−82,19%** | 91 | 26 | 60 | 5 | 31/91 (34,1%) | 0,64 | 89,42% |
| Dois M1, volume50 | 1 USDT | 0,2480 | **−75,20%** | 67 | 18 | 45 | 4 | 22/67 (32,8%) | 0,65 | 81,29% |

No cenário de 50 USDT com volume50, a taxa de TP entre 75 encerramentos por TP/SL é **28,0% (21/75)**, intervalo Wilson descritivo de 95% **19,1%–39,0%**. O fator de lucro é **0,56**, a soma de R de 78 operações é **−15,01R**. O ganho bruto nos trades vencedores foi 54,11 USDT, contra perda bruta de 96,34 USDT.

### Estabilidade e direções (carteira volume50, 50 USDT)

| Segmento | Operações | Alvos | Stops | Saídas por tempo | P&L atribuído |
|---|---:|---:|---:|---:|---:|
| 08–14/11 | 37 | 9 | 27 | 1 | −31,20 USDT |
| 15–21/11 | 41 | 12 | 27 | 2 | −11,04 USDT |
| LONG | 41 | 12 | 27 | 2 | −11,29 USDT |
| SHORT | 37 | 9 | 27 | 1 | −30,95 USDT |

As semanas são segmentos da **mesma carteira contínua**, e não carteiras reiniciadas. O saldo depende do caminho e do limite de uma posição.

## Diagnóstico

1. **O problema não está resolvido:** o filtro atual reduz a frequência, mas o fator de lucro e a taxa de acerto líquido pioraram no grupo de 50 USDT. A perda percentual menor decorre de uma trajetória de exposição diferente; não prova sinal melhor.
2. Resultado isolado antigo de 56% de TP em 25 operações encerradas foi escolhido/avaliado no histórico de 25/10–07/11, com operações simultâneas. Não é comparável diretamente à carteira sequencial atual; a diferença reforça que não se deve tratar o resultado antigo como acerto comprovado.
3. A hipótese de que apenas **selecionar moedas que tiveram lucro** na amostra resolveria o problema é uma seleção retrospectiva. Exemplos: QNT (6 TP/3 stops em 9 operações de carteira isolada), LINK (3 TP/1 stop/2 timeouts em 6) e XRP (3 TP/2 stops/2 timeouts em 7). **Não são ativos aprovados**, pois números são pequenos e foram vistos após o resultado.
4. Não é possível garantir acerto em mercados de futuros. O limiar responsável é demonstrar expectativa líquida positiva e estabilidade em uma coorte prospectiva, com limites de risco.

## Limites do experimento

- Universo selecionado usando volume e elegibilidade de **22/11**, não reconstruído diariamente a partir do passado.
- O estudo enumera formações sobrepostas e depois impõe uma posição por vez; o scanner operacional suprime alguns planos ativos. **Não é replay bit a bit** da produção.
- Entrada na abertura seguinte ao segundo M1 é idealizada; não reproduz cronjob/GitHub Actions, fila, preço FAIR, livro, spread/slippage histórico, funding efetivamente liquidado nem indisponibilidade de fonte.
- Taxa taker hipotética de 0,06% por execução, e risco planejado de até 10% por trade; resultados são de paper com capital de 1 e 50 USDT, **não patrimônio ou operações reais**.
- Os eventos de formações são altamente correlacionados e a amostra de 14 dias não demonstra probabilidade de acerto futura.

## Decisão técnica

**Não promover filtro, símbolo, alavancagem ou redução arbitrária do piso de liquidez para produção.** Preservar `main`.

**Próximo passo, nesta ordem:** (1) validar replay fiel à supressão de planos, atualização por minuto e latências reais; (2) explicar causas de stops e bloqueios sem escolher vencedores retrospectivamente; (3) testar somente uma hipótese causal por vez, congelada antes de uma nova coorte prospectiva, com custos e carteira; (4) depois de expectativa demonstravelmente positiva nas moedas já elegíveis, retomar pesquisa de baixa liquidez, inclusive ORCA.
