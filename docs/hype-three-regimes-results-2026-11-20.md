# HYPE: reversão, impulso e tendência gradual — resultado congelado

Data da avaliação: 20/11/2026.
Pré-registro das regras ANTES da simulação:
`docs/hype-three-regimes-preregistered-2026-11-20.md`.
Implementação: `scripts/audit_hype_three_regimes.py`.
Execução GitHub Actions:
https://github.com/VinyRhyu/mexc-futures-scanner/actions/runs/44829892119

**Natureza dos resultados:** somente replay paper com candles históricos públicos do
perpétuo HYPE_USDT na MEXC. Todos os períodos já tinham sido usados em
investigações anteriores; a semana dos oito movimentos foi escolhida
retrospectivamente. Não se pode chamar de validação prospectiva.
Sem alterações em main, scanner, Telegram, automações ou ordens reais.

## Hipóteses

- **REVERSAL:** sweep de mínima/máxima das 24 M5 anteriores com pavio
  e reclaim, confirmação posterior, contra o viés do H1 EMA20.
- **IMPULSE:** H1 EMA20/50 alinhados com slope, fechamento M5 rompendo
  12 candles anteriores, corpo >=0,7 ATR14, volume >=1,2x.
- **GRADUAL:** tendência H1 e M5 EMA20/50 alinhada, toque/retomada
  da EMA20 M5 e rompimento de vela anterior.

Entrada na abertura M5 seguinte; SL estrutural, alvo 1,8R bruto,
RR líquido ex ante >=1,2; no máximo duas horas; custo hipotético
taker 0,06% e slippage 0,02% por lado; 1% hipotético de risco de
conta por trade; uma posição simultânea por modelo; empate entre
modelos de família pela prioridade REVERSAL > IMPULSE > GRADUAL,
antes de selecionar uma posição na combinação.

## Janelas de 42 dias

| Janela | REVERSAL n / ROI | IMPULSE n / ROI | GRADUAL n / ROI | UNIÃO n / ROI | F HYPE n / ROI |
|---|---|---|---|---|---|
| T 05/06–17/07 | 105 / −26,802% | 170 / −21,680% | 88 / −14,692% | 251 / −38,890% | 5 / −0,168% |
| U 17/07–28/08 | 74 / −22,895% | 153 / −15,334% | 56 / −21,398% | 208 / −30,648% | 1 / −1,000% |
| V 28/08–09/10 | 74 / −22,015% | 159 / −27,943% | 50 / −7,489% | 207 / −40,618% | 2 / −1,990% |
| W 09/10–20/11 08h BRT | 76 / −14,669% | 157 / −12,314% | 49 / −15,725% | 209 / −17,514% | 1 / +1,250% |
| **168d compostos** | **329 / −62,442%** | **639 / −58,102%** | **243 / −47,722%** | **875 / −79,241%** | **9 / −1,922%** |

Em quatro janelas, nenhuma família retornou ROI positivo. Reprovam
com folga o critério pré-registrado de retorno, drawdown e frequência.
Os máximos drawdowns individuais por janela superaram 22% para cada
família; no modelo união chegaram a 40,618%. Não é razoável
integrar essas regras no scanner ou liberar sinais reais.

## Semana examinada — segunda 16/11 a sexta 20/11 19h10 BRT

| Modelo | Operações | TP | SL | TIME | ROI |
|---|---:|---:|---:|---:|---:|
| REVERSAL | 12 | 4 | 5 | 3 | +1,789% |
| IMPULSE | 21 | 1 | 7 | 13 | −4,014% |
| GRADUAL | 9 | 1 | 6 | 2 | −3,972% |
| UNIÃO | 28 | 5 | 9 | 14 | +0,106% |
| F original | 0 | 0 | 0 | 0 | 0% |

**Alerta:** a semana sobrepõe W parcialmente e NÃO deve ser somada aos
168 dias como amostra independente. REVERSAL foi positiva em 4,8 dias
escolhidos, mas **negativa em todos os quatro blocos de 42 dias**;
selecionar o positivo e ignorar o restante seria data snooping.

## Os oito movimentos marcados pelo usuário

Para cada caso, verificar se houve um candidato da direção correta
no intervalo; candidato com RR líquido abaixo de 1,2 não entra.
Janelas e direções dadas pelo usuário são classificações
retrospectivas, não predições.

| Movimento | REVERSAL | IMPULSE | GRADUAL |
|---|---|---|---|
| 16/11 SHORT 08h–10h | nenhum | primeiro 09h05 (3 sinais elegíveis) | nenhum |
| 16/11 LONG recuperação 10h–12h15 | nenhum | nenhum | nenhum |
| 16/11 LONG lento 12h15–19h | nenhum | nenhum | nenhum |
| 17/11 SHORT 02h30–06h15 | nenhum | nenhum | nenhum |
| 17/11 SHORT 11h15–12h30 | nenhum | nenhum | nenhum |
| 18/11 SHORT 10h15–13h | nenhum | nenhum | nenhum |
| 19/11 LONG 00h–08h30 | nenhum | nenhum | nenhum |
| 20/11 SHORT 08h–12h30 | nenhum | primeiro 08h05 (8 elegíveis); TP hipotético | 12h10 (1 sinal, tarde) |

**Exemplo 20/11 08h05:** IMPULSE SHORT com entrada hipotética
64,632 USDT, stop 65,46304, TP 63,13614; atingiu o alvo
no replay de candles e gerou +1,4901R líquido simulado. O evento
sozinho não demonstra estratégia rentável, pois na mesma semana
IMPULSE encerrou −4,014%.

**Exemplo 18/11 10h55:** o marcador bruto não filtrado pelo H1 do
estudo anterior produziu SHORT hipotético, mas esta família IMPULSE
exige H1 EMA20/50 alinhadas, portanto não houve sinal autorizado
nesse movimento. A restrição H1 não deve ser removida apenas por
este sucesso retrospectivo.

A classificação também deixa de capturar mudanças graduais e
reversões às quais o H1 reage tarde. Apesar disso, afrouxar regras
após observar o melhor cenário tende a gerar mais falsos sinais,
como demonstrado pela semana inteira.

## Limitações e decisão

Sem livro de ordens/ticks, funding, mínimo de contrato, liquidação ou
fills reais. A escolha dos movimentos foi feita com hindsight, e os
parâmetros das três famílias foram motivados pela semana já inspecionada.
Todas as estatísticas de ROI se referem a carteiras separadas com uma
posição de cada vez, não à soma das três famílias.

**Conclusão:** as três hipóteses são REPROVADAS como estratégias
autorizadas; nenhuma de suas regras deve ser integrada na versão
principal. Continuar estudo com diagnóstico da taxa-base
de eventos e separação DETECÇÃO/ENTRADA, sem tentar ajustar
parâmetros aos oito movimentos observados.
