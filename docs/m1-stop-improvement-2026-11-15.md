# Diagnóstico dos 71 stops e dois testes sequenciais de saída

**Conclusão: nenhuma das duas alterações produziu uma melhora satisfatória nesta amostra.** Ambas reduziram stops completos, mas também cortaram ganhos e diminuíram o retorno normalizado. Os dois testes ficaram registrados como rejeitados; não foi alterado o bot em produção.

## Referência mantida

Modelo M1 com sustentação de volume, mesmas 123 entradas hipotéticas, de 25/10 a 07/11/2026, nos 31 ativos da captura original. Preservados os horários de entrada, as quantidades, os alvos e os stops iniciais. O teste anterior tinha 49 TPs, 71 stops e três operações ainda abertas após quatro horas. A trajetória desse controle foi reproduzida, com igualdade de desfechos e dos retornos R, admitindo apenas tolerância decimal de 1e−22.

As mudanças foram avaliadas separadamente e em sequência, com protocolo congelado antes de cada execução. Não foram combinadas nem comparados múltiplos limiares. A segunda hipótese foi definida depois de rejeitar a primeira e observar o diagnóstico. Portanto, a análise é exploratória e reutiliza histórico; não é validação independente.

## Diagnóstico das 71 operações que atingiram stop

| Observação | Quantidade |
|---|---:|
| Voltaram para dentro do limite rompido, por fechamento M1, nos primeiros cinco minutos antes do minuto do stop | 33 |
| Mostraram algum lucro líquido em fechamento M1 antes do minuto do stop | 38 |
| Atingiram pelo menos +0,25R líquido em fechamento M1 | 31 |
| Atingiram pelo menos +0,5R líquido em fechamento M1 | 16 |
| Atingiram pelo menos +1R líquido em fechamento M1 | 4 |
| Tocaram o alvo original em um minuto posterior ao stop, dentro da janela original de quatro horas | 9 |
| Stop nos primeiros cinco minutos | 11 |
| Stop nos primeiros quinze minutos | 25 |
| Stop nos primeiros trinta minutos | 36 |
| Mediana do tempo até o stop | 28 minutos |

Os grupos podem se sobrepor. Para medir lucro anterior à perda, o minuto que contém o stop foi excluído: seu fechamento ou sua máxima posterior não demonstram uma oportunidade anterior ao stop. O alvo posterior foi procurado somente em minutos seguintes ao stop, sem estender a janela de quatro horas. Nove alvos posteriores não demonstram que um stop mais largo teria sido seguro ou vantajoso.

## Primeiro teste: proteger os custos após +0,5R

Regra: depois de um fechamento M1 com lucro líquido modelado de pelo menos +0,5R, mover o stop para o preço que cobre taxas e custos do modelo, arredondado ao tick. O novo stop só vale a partir do próximo minuto. O alvo permanece igual. Não foi usada uma máxima intraminuto para ativar a proteção.

Se o stop original é tocado no minuto da possível ativação, a operação encerra nele e não pode ser reclassificada como protegida. Se stop ativo e alvo são tocados no mesmo minuto, o stop tem prioridade. Gaps podem gerar perda mesmo após a proteção; não se presume lucro zero garantido.

Esse teste transformou 16 stops em saídas protegidas, mas também encerrou cedo 12 operações que atingiriam TP, além das três que ainda estavam abertas na referência. O número de saídas com líquido ligeiramente positivo aumentou, mas o ganho agregado caiu. **Rejeitado.**

## Segundo teste: sair da falha inicial do rompimento

Regra: se um dos cinco primeiros candles M1 mantidos em posição fecha no limite rompido ou de volta para dentro da consolidação, programar saída integral na abertura do minuto seguinte. O stop e o alvo originais continuam valendo antes da saída. Se a abertura seguinte já atravessa stop ou alvo, essa condição tem prioridade. A saída programada não usa a máxima ou mínima futura do minuto.

Esse teste substituiu 33 stops por saídas menores de falha do rompimento, mas também cortou oito operações que posteriormente atingiriam TP e uma que estava aberta. Reduziu o número de stops completos, porém não melhorou o ganho agregado. **Rejeitado.**

## Comparação das mesmas 123 entradas

| Resultado | Referência | Proteção após +0,5R | Saída de falha em até 5min |
|---|---:|---:|---:|
| TP | 49 | 37 | 41 |
| Stops completos | 71 | 55 | 38 |
| Saídas protegidas | 0 | 31 | 0 |
| Saídas por falha de rompimento | 0 | 0 | 42 |
| Abertas após quatro horas | 3 | 0 | 2 |
| Soma R das encerradas | +16,283R | +10,781R | +12,820R |
| Soma R incluindo marcação das abertas em 4h | +17,668R | +10,781R | +13,354R |
| Fator de lucro das encerradas | 1,229 | 1,196 | 1,209 |

R é o risco inicial normalizado de cada posição. A soma desses valores não é ROI de carteira nem dinheiro realizado; há operações simultâneas e correlacionadas sem restrição compartilhada de capital. Saída protegida com resíduo positivo por arredondamento não é um TP nem demonstra aumento útil de assertividade. A marcação das abertas é um cálculo hipotético de saída em quatro horas com o mesmo modelo de custo, separado do resultado encerrado.

## Divisão por semana

| Semana | Referência: R com marcações | Proteção: R com marcações | Falha: R com marcações |
|---|---:|---:|---:|
| 25–31/10 | +15.826R | +10.785R | +11.532R |
| 01–07/11 | +1.842R | -0.004R | +1.823R |

Critério registrado: para ser promissora, uma alteração precisaria melhorar retorno R com as marcações e fator de lucro no total, sem piorar o retorno marcado em nenhuma das duas semanas. As duas alterações falharam. A proteção após +0,5R prejudicou as duas semanas; a saída da falha também ficou abaixo do controle em ambas.

## Interpretação

A captura mistura recuos que precedem perdas com recuos que precedem alvos. Reagir de forma uniforme ao pequeno lucro ou ao primeiro retorno ao limite descartou operações que ainda tinham resultado favorável. Isso não demonstra que toda gestão dinâmica seja ruim; rejeita essas duas regras específicas, nos limiares e janelas previamente definidos.

O diagnóstico desloca a investigação para a seleção e a qualidade do rompimento. Não há evidência suficiente aqui para aumentar risco, alargar stops ou promover uma das duas saídas. Uma próxima hipótese precisa distinguir os casos antes de observar seu resultado e ser verificada em dados ainda não usados para escolhê-la.

## Custos, testes e limites

- Mesma execução hipotética do replay anterior: entrada na abertura M1 seguinte, ajustada em ±0,01%; taxa de 0,06% em cada execução; slippage igual ao maior entre dois ticks e o configurado. Saídas seguem o modelo original, sem livro histórico ou reconstrução completa de bid/ask.
- Funding zero e contratos congelados na captura. Não há Fair M1 para reconstruir liquidação efetiva. Não representa a execução real da conta.
- Não reproduz fila do GitHub, latência de coleta/Telegram, aceitação manual, restrição de uma posição única ou carteira de US$ 100.
- Sete testes direcionados passaram: custo e arredondamento do stop para LONG/SHORT; ativação somente no próximo minuto; precedência do stop; gaps adversos; saída de falha na abertura seguinte sem consultar o restante do candle.
- Os arquivos brutos foram carregados com validação de checksum e continuidade. A referência das 123 entradas foi reconciliada integralmente.
- Fonte: [run 42879077420](https://github.com/VinyRhyu/mexc-futures-scanner/actions/runs/42879077420). Protocolos em `config/audit-m1-profit-protection-2026-11-15.json` e `config/audit-m1-failed-break-2026-11-15.json`. Operações, transições, regras congeladas e resultados completos no JSON adjacente.
- Alterações somente em arquivos de auditoria; produção, Telegram e ordens reais não foram alterados.

```sh
python -m unittest tests.test_m1_profit_protection -q
python -m scripts.audit_m1_profit_protection --source SOURCE_DIR --baseline M1_TREND_RESULTS --protocol config/audit-m1-profit-protection-2026-11-15.json --failed-protocol config/audit-m1-failed-break-2026-11-15.json --output results.json
```
