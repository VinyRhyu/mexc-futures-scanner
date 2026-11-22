# Auditoria de cobertura do universo — ORCA (22/11/2026)

**Status:** branch de pesquisa, sem merge e sem mudança de regras de sinais, risco, execução ou notificações. Não representa validação de lucratividade.

## Diagnóstico reproduzível

- O cadastro de criptoativos em `config/crypto-assets.json` continha 179 ativos, mas não ORCA.
- `mexc_scanner/cli.py` carrega esse cadastro e `select_universe` rejeita qualquer base ausente com `CLASSIFICACAO_PENDENTE`, mesmo quando o contrato aparece no catálogo MEXC.
- A MEXC possui uma página oficial de futuros perpétuos ORCA_USDT: https://www.mexc.com/futures/ORCA_USDT.
- Portanto, no código anterior, ORCA_USDT nunca entrava na seleção principal enquanto ORCA não estivesse reconhecido. Isso por si só não demonstra que ORCA teria sido um sinal financeiro viável nem que cumpria liquidez no horário do exemplo.

## Alteração experimental

O cadastro versionado passa a incluir ORCA. Permanecem inalterados:
- contrato regular, ativo, perpétuo cripto com cotação e liquidação USDT;
- volume financeiro mínimo em 24h de 5.000.000 USDT (usando `amount24`);
- limite de até 50 elegíveis, ordenados por giro;
- regras M1 de dois fechamentos e volume, SL/TP, custo, janela temporal, tamanho de posição, piso de RR 1:1, alavancagem máxima 20x e somente modo paper.

O teste `test_orca_asset_preserves_contract_and_liquidity_gates` cobre inclusão condicional e exclusão por baixo giro, contrato inativo ou classificação não cripto.

## Contexto quantitativo disponível

- Na produção (amostra das dez rodadas de 22/11 entre 19:15 e 19:24 BRT), cada execução concluiu com `source_status=OK` e `coverage=23/23`. Duraram aproximadamente 21 a 28 segundos e reportaram 17 mensagens enviadas, 0 falhas de envio; mensagens não equivalem a entradas ou lucros.
- O replay de carteira de 25/10 a 07/11 do modelo anterior de dois M1 fechados resultou em 50,00 -> 45,87 USDT (-8,25%) com 16 operações; não demonstra rentabilidade. Ver `docs/experiments/portfolio-50-history.md`.
- Pesquisas adicionais em 21/11 não encontraram melhora robusta ao usar OI/agressão ou priorização de sinais no mesmo minuto (`research-oi-taker-20261121`).
- A operação vencedora de ORCA relatada externamente em 21/11 é **um exemplo**, não uma amostra estatística suficiente. O scanner não operava 30x como nesse exemplo (teto de simulação 20x).

## Validação pendente antes de considerar merge

1. Rodar a suíte completa de testes da branch em CI.
2. Consultar em uma coleta isolada, sem notificar, se a MEXC retorna ORCA_USDT como ativo USDT perpétuo, qual o `amount24` real e o motivo preciso de inclusão/exclusão.
3. Verificar se ORCA entra no limite dos 50 maiores elegíveis; não forçar a seleção.
4. Medir cobertura e viés de universo sem selecionar parâmetros a partir de uma operação vencedora conhecida.
5. Manter acompanhamento prospectivo e backtest causal com amostra de 60 dias, *se* for possível obter histórico consistente de 1m; separar treino/teste e simular uma posição por vez, custos e atrasos.
6. Não promover a estratégia como lucrativa sem expectativa líquida positiva e verificação fora da amostra.

**Não alterar a branch `main` com base apenas no caso ORCA.**

## Resultado do teste real (22/11/2026, 20h03 BRT)

- [GitHub Actions: consulta pública sem ordens nem Telegram](https://github.com/VinyRhyu/mexc-futures-scanner/actions/runs/45081102022): concluído com sucesso.
- [GitHub Actions: suíte de regressão](https://github.com/VinyRhyu/mexc-futures-scanner/actions/runs/45081022352): aprovado na revisão que introduziu o histórico. A suíte será reexecutada para alterações posteriores.
- `ORCA_USDT` existe no catálogo da MEXC e aparece ativo, perpétuo regular, cripto, cotado e liquidado em USDT.
- Ticker `amount24`: **400.032,532 USDT**, abaixo dos **5.000.000 USDT** exigidos. Resultado com ORCA reconhecida: `VOLUME_FINANCEIRO_INSUFICIENTE`, não selecionada.
- Resultado sem reconhecimento de ORCA: `CLASSIFICACAO_PENDENTE`, também não selecionada.
- Amostras recentes: 120 M1, 480 M15 e 240 H1 íntegros e fechados.
- Volume histórico: somatório de 1.440 candles M1 na janela 20/11/2026 10h45 até 21/11/2026 10h45 BRT, anterior à entrada relatada, **388.605,637** no campo `amount` da MEXC; série completa sem lacunas. **Também abaixo do limiar de USDT 5 milhões**.
- Verificação de unidade: série M1 das 24h atuais somou **399.831,761** e o ticker em horário praticamente igual apontou **400.032,532 USDT** (razão 0,999498). Isso confirma empiricamente que o campo agregado `amount` é compatível com o giro em USDT do ticker, na precisão dessa consulta.
- Testes de disponibilidade histórica de M1: 60/60 candles na amostra 14 dias atrás, 60/60 na amostra 30 dias atrás, **0/60** na amostra 60 dias atrás. Isso **não** valida 30 dias íntegros, nem permite rodar já um backtest completo de 60 dias da ORCA por essa fonte. A causa de zero candles antigos (listagem, retenção ou limites da API) ainda não foi determinada.

### Decisão após o teste

A correção de classificação tem sentido técnico, mas **não desbloqueia ORCA atualmente**. Também não desbloquearia o contrato no horário aproximado da operação vencedora de 21/11, se a política de giro mínimo de 5 milhões fosse aplicada a esse histórico. Não reduziremos o limiar de liquidez apenas para incluir um caso vencedor. A rentabilidade de 30x informada é uma observação externa e não altera o teto da estratégia operacional de 20x.

**O PR continua rascunho, a `main` intacta.** Antes de reconsiderar a cobertura operacional, estudar o impacto de diferentes faixas de liquidez, slippage e custos com coortes causais e operações perdedoras, preservando a avaliação fora da amostra.
