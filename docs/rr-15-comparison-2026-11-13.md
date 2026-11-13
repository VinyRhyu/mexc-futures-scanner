# Retorno/risco líquido: 2:1 versus 1,5:1

Teste exploratório executado em 13/11/2026. Nenhuma alteração no scanner ativo,
nos alertas do Telegram ou no modo paper. Código-base:
`a04aaea446d8510b32023242139cab9bed53b3f4`.

## Método

- Período: 25/10 a 07/11/2026, 14 dias no horário de Brasília.
- Mesmos 31 contratos e 23.174 formações da coleta congelada original.
- Única alteração: retorno/risco líquido mínimo de 2 para 1,5.
- Mantidos os dois fechamentos M1, retenção de volume de 50%, SL, TP técnico,
  validade, dimensionamento e demais critérios financeiros.
- Nenhum filtro mínimo de ROI de 10% foi adicionado. O scanner já não exige
  lucro de 60% por entrada; 60% permanece uma meta de acompanhamento.
- O avaliador pode ampliar a faixa admissível e recalcular a quantidade quando
  muda o RR mínimo; SL, TP e preço de abertura observado permanecem iguais.
- Entrada hipotética na abertura imediatamente seguinte; acompanhamento de 4h.
- Taxa assumida de 0,06% por execução, spread de 0,02%, deslizamento configurado
  ou dois ticks, funding zero e livro hipotético com profundidade infinita.
- Stop primeiro quando um mesmo candle tocar SL e TP. Execuções idênticas
  deduplicadas; movimentos correlacionados e operações sobrepostas permanecem.
- Checksums e integridade dos candles conferidos. Referência anterior de
  28 entradas / 14 TP / 11 SL / 3 abertas / +25,4175958R reproduzida.

## Resultado

| Métrica | RR mínimo 2:1 | RR mínimo 1,5:1 |
| --- | ---: | ---: |
| Entradas únicas | 28 | 57 |
| Eventos distintos de ativo/lado/minuto | 25 | 46 |
| TP | 14 | 28 |
| SL | 11 | 26 |
| Abertas após 4h | 3 | 3 |
| TP entre encerradas | 56,0% | 51,9% |
| Resultado das encerradas | +25,42R | +34,80R |
| Encerradas + marcação hipotética das abertas em 4h | +26,80R | +36,18R |

As 28 entradas originais foram preservadas, com os mesmos desfechos. As 29
adicionais tiveram 14 TP e 15 SL, contribuindo com +9,38R. Assim, o teste
aumentou a frequência e o retorno agregado, mas reduziu a taxa de acerto.

| Período | Resultado encerrado em 2:1 | Resultado encerrado em 1,5:1 |
| --- | ---: | ---: |
| 25–31/10 | +19,35R | +25,27R |
| 01–07/11 | +6,07R | +9,53R |

| Direção | Entradas em 2:1 | Entradas em 1,5:1 | R em 2:1 | R em 1,5:1 |
| --- | ---: | ---: | ---: | ---: |
| LONG | 20 | 39 | +21,35 | +32,38 |
| SHORT | 8 | 18 | +4,07 | +2,42 |

O ganho adicional concentrou-se nos LONGs. O resultado dos SHORTs diminuiu.
Esta observação posterior não autoriza escolher um filtro direcional vencedor
no mesmo histórico e apresentá-lo como validação independente.

## Limites e conclusão

R representa o risco inicial líquido de cada operação independente. A soma não
é dinheiro nem ROI de uma carteira executável. A marcação das abertas em 4h é
um encerramento hipotético, separado da contagem de TP/SL.

Este é o mesmo histórico já usado em vários diagnósticos, não uma validação
fora da amostra. A composição do universo e as regras de contrato refletem a
coleta original. Preenchimentos imediatos e custos sintéticos não demonstram
execução ou rentabilidade real; o agendamento pode perder essas entradas.

O resultado justifica observar 1,5:1 em simulação paralela com dados novos.
Não justifica prometer maior assertividade ou mudar automaticamente o modo
para real. O piso de validação da configuração de produção continua em 2.

No Telegram, “GATILHO VÁLIDO PARA SIMULAR” significa que a confirmação técnica
e as avaliações estimadas do modo paper passaram. As taxas pessoais, regras
da conta e eventuais gatilhos Fair continuam sujeitos à validação própria.
“Confirmada” não significa lucro garantido, ordem enviada ou posição aberta.

## Reprodução

Fonte: artefato `13792493410` da execução `42879077420`.

```sh
python -m scripts.audit_rr_15 --source CAMINHO_DA_COLETA --output reports/rr-15
```

O script usa uma substituição de configuração somente para o experimento;
não altera `Config.validate`, configurações de produção, estado ou Telegram.
O JSON anexo conserva métricas, hashes e os casos com entradas de ao menos
um cenário. A execução completa também gera os registros rejeitados.
