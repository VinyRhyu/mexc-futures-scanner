# Experimento solicitado: mínimo líquido de 1:1

Teste executado em 13/11/2026 sobre a coleta congelada de 25/10 a 07/11/2026:
14 dias, 31 instrumentos e 23.174 formações. Configuração e notificações de
produção permanecem inalteradas.

## O que foi alterado

Apenas o mínimo líquido de ganho/perda aceito pelo avaliador passou para 1.
TP técnico, SL, dois fechamentos M1 e retenção de volume de 50% foram
preservados. O TP não foi deslocado para produzir exatamente +1R, nem foi
adicionado um mínimo de lucro percentual. Entradas com RR maior continuam
elegíveis. O avaliador pode ampliar a faixa financeira admissível e recalcular
a quantidade conforme o novo mínimo.

Como nos experimentos anteriores, o valor menor é passado ao avaliador por
uma configuração isolada do teste. O piso de `Config.validate` continua 2;
nenhuma liberação de uso real foi feita.

## Entrada imediatamente após a confirmação

| Mínimo líquido | Planos | Eventos ativo/lado/minuto | TP | SL | Abertas em 4h | Acerto entre encerradas | R encerradas |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2:1 | 28 | 25 | 14 | 11 | 3 | 56,0% | +25,42 |
| 1,5:1 | 57 | 46 | 28 | 26 | 3 | 51,9% | +34,80 |
| 1:1 | 123 | 102 | 49 | 71 | 3 | 40,8% | +16,28 |

O mínimo de 1:1 preserva as 57 entradas de 1,5:1 e adiciona 66:
21 TP e 45 SL, com contribuição de -18,51R. Os resultados das execuções
compartilhadas foram conferidos, preservando o desfecho e o retorno normalizado.

A taxa de 40,8% pode coexistir com resultado positivo porque 1:1 é o mínimo
exigido: os alvos técnicos vencedores podem render mais de 1R.

## Entrada com atraso hipotético de um minuto

| Mínimo líquido | Planos viáveis | Eventos distintos | TP | SL | Abertas em 4h | Acerto entre encerradas | R encerradas |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2:1 | 17 | 15 | 12 | 3 | 2 | 80,0% | +25,28 |
| 1,5:1 | 34 | 28 | 21 | 11 | 2 | 65,6% | +35,21 |
| 1:1 | 71 | 57 | 38 | 31 | 2 | 55,1% | +39,09 |

Em 1:1, 52 dos 123 planos ficam fora da faixa de entrada no minuto seguinte.
Os 71 sobreviventes distribuem-se por 11 datas de confirmação; os 123 da
referência imediata se distribuem por 13 datas. Isso não representa frequência
garantida nem todas as oportunidades de mercado.

Com a marcação hipotética das abertas no final da janela de 4h, os totais são:

| Mínimo | Imediato: R encerradas + marcação | +1min: R encerradas + marcação |
| --- | ---: | ---: |
| 2:1 | +26,80 | +26,81 |
| 1,5:1 | +36,18 | +36,74 |
| 1:1 | +17,67 | +40,62 |

As marcações são saídas hipotéticas, não TP nem operações comprovadamente
realizadas. O atraso de um minuto foi fixado antes de observar este resultado,
seguindo a auditoria anterior, e não significa que esperar deliberadamente
seja melhor. Os planos expiram 120 segundos após a confirmação na produção.

## Robustez descritiva

Na referência imediata, 1:1 produziu +14,98R em 25–31/10 e +1,31R em
01–07/11. Em 1,5:1, foram +25,27R e +9,53R, respectivamente.

Os LONGs imediatos de 1:1 somaram +26,60R e os SHORTs -10,32R. Esses
recortes são descrições posteriores, não critérios autorizados para escolher
retroativamente apenas a direção vencedora.

## Validação e limites

- Referências imediatas de 2:1 e 1,5:1 reproduzidas; também reproduzidas suas
  referências com atraso de um minuto. Retorno comum conferido com tolerância
  de 1e-20 em R para arredondamento decimal.
- Checksums, continuidade e consistência OHLC dos 31 instrumentos conferidos.
- Quarenta testes relevantes de finanças, sustentação, volume e atraso passaram.
- Mesma referência de 1USDT, risco planejado até 10%, teto de 20x; taxas
  hipotéticas de 0,06% por lado, spread de 0,02%, slippage configurado ou dois
  ticks, funding zero e livro hipotético ilimitado. Não são taxas pessoais.
- Entrada na abertura M1 imediatamente após confirmação ou um minuto depois.
  Candles M1 não comprovam cotação exata na chegada do Telegram ou execução
  manual. O tempo real de leitura/envio de ordem não foi medido.
- TP/SL tocados na espera cancelam a entrada atrasada. Janela comum termina
  4h após a confirmação; stop primeiro na ambiguidade. Abertas separadas.
- Apenas execuções idênticas foram deduplicadas. Planos podem se sobrepor e
  compartilhar o movimento; soma R não é dinheiro nem ROI de carteira.
- O mesmo histórico já foi usado em várias análises; não há validação fora
  da amostra. Universo e regras de contrato refletem a coleta original.
- O único novo limiar foi 1, explicitamente solicitado antes da execução.
  Não houve busca adicional de parâmetros nem filtro direcional otimizado.

Conclusão: 1:1 aumenta a frequência e reduz a assertividade. Foi inferior em
retorno imediato; com atraso de um minuto, teve retorno maior por +3,88R,
com mais que o dobro de planos e 31 SL contra 11. O resultado favorece
continuar investigando em simulação, sem declarar 1:1 superior ou ativá-lo
automaticamente em produção.

## Reprodução

Fonte original: artefato GitHub Actions `13792493410`.
Base do experimento anterior: `46670ddbd12d73cebb22d6cefbd273925ab64fe2`.

```sh
python -m scripts.audit_rr_one --source CAMINHO_DA_COLETA --output reports/rr-one
python -m unittest tests.test_rr_delivery tests.test_audit_minute_execution tests.test_audit_sustained_trigger tests.test_volume_retention tests.test_finance
```

O JSON anexo conserva as métricas completas e as execuções únicas de 1:1,
incluindo suas reavaliações em um minuto. O script gera também os casos
com entradas das referências anteriores.
