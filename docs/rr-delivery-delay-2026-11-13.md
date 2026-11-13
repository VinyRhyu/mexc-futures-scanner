# Quantas confirmações sobreviveriam ao atraso de execução?

Auditoria em 13/11/2026 das mesmas entradas do experimento de RR 2:1 versus
1,5:1. Período: 25/10–07/11/2026 (14 dias). Nenhuma mudança na produção,
nos alertas, na conta ou no modo paper.

## Resultado principal: RR mínimo de 1,5:1

| Atraso após confirmação | Planos viáveis | Eventos ativo/lado/minuto | TP | SL | Abertas em 4h | R encerradas |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Imediato, referência idealizada | 57 | 46 | 28 | 26 | 3 | +34,80 |
| 1 minuto | 34 | 28 | 21 | 11 | 2 | +35,21 |
| 2 minutos | 0 | 0 | 0 | 0 | 0 | 0 |
| 3 minutos | 0 | 0 | 0 | 0 | 0 | 0 |

Em um minuto, 34/57 planos (59,6%) ainda passam pelos critérios, com
21/32 = 65,6% de TP entre as operações encerradas. Os outros 23 ficam fora
da faixa admissível. São 34 planos com SL/TP potencialmente diferentes,
mas apenas 28 eventos distintos de ativo/lado/minuto. Não tratar os planos
como observações estatisticamente independentes.

Os planos de um minuto se concentram em apenas seis datas de confirmação:

| Data BRT | Planos |
| --- | ---: |
| 25/10 | 1 |
| 29/10 | 6 |
| 30/10 | 16 |
| 31/10 | 4 |
| 03/11 | 3 |
| 05/11 | 4 |

Nos outros oito dias não houve plano dessa amostra que sobrevivesse à
checagem em um minuto. Isto não mede todas as oportunidades de mercado,
nem sinais antes bloqueados que pudessem se tornar elegíveis posteriormente.

## Comparação com o RR atual de 2:1

| Atraso | Planos viáveis | Eventos distintos | TP | SL | Abertas em 4h | R encerradas |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Imediato | 28 | 25 | 14 | 11 | 3 | +25,42 |
| 1 minuto | 17 | 15 | 12 | 3 | 2 | +25,28 |

## O limite de dois minutos é uma regra real do scanner

O modelo de produção usa `MAX_SIGNAL_AGE=120`. A validade para uma nova
entrada termina 120 segundos após o segundo fechamento M1. A cotação
hipotética é avaliada na abertura do minuto atrasado mais um segundo;
portanto, nos cenários de 120s e 180s a entrada já está expirada.

Separadamente, o script calcula um cenário CONTRAFACTUAL que ignora apenas
essa expiração. Em 1,5:1, haveria 17 planos financeiramente viáveis no preço
da abertura de +2min e 19 em +3min; no último caso, cinco outros planos
tocaram o stop durante a espera e foram cancelados. Essas contagens não são
entradas permitidas pelo sistema atual. As contagens não precisam diminuir
sempre: o preço pode voltar à faixa. Não alterar validade com base nesse dado
retrospectivo sem um experimento separado.

## Observação dos envios atuais

O estado consultado tinha oito alertas `ENTRY/SENT` do modelo M1, correspondendo
a sete eventos de ativo/lado/minuto; dois planos de AAVE compartilham o gatilho.
O intervalo entre confirmação e aceitação registrada pelo Telegram foi de
47 a 81 segundos, mediana 56 segundos. Esses são somente os alertas enviados,
não uma amostra dos sinais perdidos, nem confirmação de leitura ou execução.
Com a validade de 120s, restavam de 39 a 73 segundos após esses envios para
uma nova entrada, sempre condicionada ao preço e às demais regras.

## Método e limites

- Coortes congeladas de 28 e 57 execuções, deduplicadas exatamente como no
  experimento anterior. As duas referências imediatas foram reproduzidas.
- Todos os 31 arquivos-fonte tiveram checksum, continuidade e OHLC validados.
- Atrasos fixados em 0/60/120/180 segundos; nenhum foi selecionado para otimizar
  o resultado. Os atrasos são hipóteses, não os tempos históricos dos jobs.
- SL, TP e faixa congelados. Custos, RR, preço, lote, risco, margem e demais
  condições financeiras são reavaliados na abertura atrasada. Nenhum TP/SL é
  deslocado para viabilizar uma entrada.
- Se TP/SL já foi tocado durante a espera, não há entrada atrasada. Stop tem
  precedência na ambiguidade. A janela termina 4h após o sinal original.
- Mesmas taxas hipotéticas de 0,06% por lado, spread 0,02%, slippage configurado
  ou dois ticks, funding zero e livro ilimitado. Sem garantia de preenchimento.
- O preço imediato é uma referência idealizada: a produção exige disponibilidade
  do candle fechado e tempo de coleta. Candles M1 não mostram a cotação exata
  no segundo de chegada do aviso ou da ordem manual.
- R é risco inicial por operação independente; operações se sobrepõem. R não é
  dólar nem ROI de carteira. Abertas não entram no acerto nem em R encerradas;
  o JSON também registra marcação hipotética em 4h, separada de TP/SL.
- Mesmo histórico já explorado, sem validação fora da amostra. A melhora
  retrospectiva com atraso não prova que aguardar um minuto seja uma estratégia
  melhor. Quarenta testes relevantes passaram, além das checagens da coorte.

Conclusão: há oportunidades que sobrevivem a um atraso de um minuto, mas uma
parte relevante sai da faixa e a entrega consome boa parte da validade. O passo
seguinte é medir a sobrevivência em dados novos e o tempo total até execução
manual, preservando a separação entre confirmação técnica e validação real.

## Reprodução

Código-base do experimento: `6e31014742be5df8e0c69d14077b07916d850910`.
Fonte: artefato GitHub Actions `13792493410`.

```sh
python -m scripts.audit_rr_delivery --source CAMINHO_DA_COLETA --cohort docs/rr-15-comparison-2026-11-13.json --output reports/rr-delivery.json
python -m unittest tests.test_rr_delivery tests.test_audit_minute_execution tests.test_audit_sustained_trigger tests.test_volume_retention tests.test_finance
```
