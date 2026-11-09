"""Auditoria histórica, sem ordens, estado, Telegram ou alteração dos sinais ao vivo.

Casos escolhidos após observação do movimento: resultados são exploratórios, não prova
prospectiva. Usa somente candles 15m fechados da MEXC, com stop primeiro em ambiguidade.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from datetime import datetime, timezone

from mexc_scanner.market import atr, parse_candles
from mexc_scanner.mexc import MexcClient
from mexc_scanner.models import Candle, D, floor_step, ceil_step


@dataclass(frozen=True)
class Case:
    symbol: str
    signal: str  # fechamento UTC do gatilho original
    side: str
    entry_low: str
    entry_high: str
    stop: str
    target: str


CASES = (
    Case('HYPE_USDT', '2026-11-09T05:30:00Z', 'SHORT', '74.079', '74.302', '74.582', '74.106'),
    Case('ETH_USDT', '2026-11-09T05:30:00Z', 'SHORT', '2129.67', '2133.62', '2140.39', '2121.52'),
    Case('ENA_USDT', '2026-11-09T05:45:00Z', 'SHORT', '0.15054', '0.15118', '0.15215', '0.14918'),
    Case('ZEC_USDT', '2026-11-09T04:30:00Z', 'SHORT', '1230.52', '1235.44', '1245.93', '1225.64'),
    Case('LINK_USDT', '2026-11-09T11:30:00Z', 'LONG', '10.499', '10.527', '10.450', '10.571'),
    Case('SUI_USDT', '2026-11-09T06:00:00Z', 'SHORT', '0.8237', '0.8241', '0.8276', '0.8116'),
    Case('ONE_USDT', '2026-11-09T08:15:00Z', 'SHORT', '0.0015719', '0.0015837', '0.0015987', '0.0015026'),
    Case('AVAX_USDT', '2026-11-09T02:30:00Z', 'LONG', '8.081', '8.083', '8.042', '8.209'),
)


def ts(iso: str) -> int:
    return int(datetime.fromisoformat(iso.replace('Z', '+00:00')).timestamp())


def outcome(bars: list[Candle], side: str, stop: Decimal, target: Decimal) -> str:
    sign = 1 if side == 'LONG' else -1
    for c in bars:
        bad = c.low <= stop if sign == 1 else c.high >= stop
        good = c.high >= target if sign == 1 else c.low <= target
        if bad and good:
            return 'AMBIGUO_STOP_PRIMEIRO'
        if bad:
            return 'STOP'
        if good:
            return 'ALVO'
    return 'ABERTO_AO_FIM_DA_JANELA'


def next_open(c: Candle, side: str, tick: Decimal) -> Decimal:
    sign = 1 if side == 'LONG' else -1
    # Spread assumido 0,02% e deslizamento 0,02% ou dois ticks.
    return c.open + sign * (c.open * D('0.0001') + max(c.open * D('0.0002'), 2 * tick))


def review_case(case: Case, q: list[Candle], tick: Decimal, horizon: int = 4 * 3600) -> dict:
    closed = ts(case.signal)
    index = next((i for i, c in enumerate(q) if c.end == closed), None)
    if index is None or index < 15 or index + 1 >= len(q):
        return {'symbol': case.symbol, 'error': 'HISTORICO_INCOMPLETO'}
    sign = 1 if case.side == 'LONG' else -1
    later = [c for c in q[index + 1:] if c.ts < closed + horizon]
    first = later[0]
    low, high, stop, target = map(D, (case.entry_low, case.entry_high, case.stop, case.target))
    original_entry = next_open(first, case.side, tick)
    # Candle após gatilho pode abrir fora da faixa: movimento não significa fill.
    original = outcome(later, case.side, stop, target) if low <= original_entry <= high else 'SEM_FILL_NA_ABERTURA_SEGUINTE'
    a = atr(q[:index + 1], 14)[-1]
    trial = {'symbol': case.symbol, 'side': case.side, 'signal': case.signal,
             'original_entry_estimate': str(original_entry), 'original': original,
             'original_gross_rr_worst': str((sign * (target - (high if sign == 1 else low))) /
                                             (sign * ((high if sign == 1 else low) - stop)))}
    # Hipótese ANTES de observar o resultado do próximo candle: primeiro fechamento
    # posterior ao gatilho além do TP antigo; no máximo 2h para não perseguir tarde.
    crossing = next((j for j in range(index + 1, len(q))
                     if q[j].end <= closed + 2 * 3600 and sign * (q[j].close - target) > 0), None)
    if crossing is None or crossing + 1 >= len(q):
        trial['continuation'] = 'SEM_NOVO_GATILHO'
        return trial
    signal_bar = q[crossing]
    # Stop numa estrutura LOCAL conhecida ao fechar o gatilho. Nenhum candle
    # posterior informa o plano; alvos nunca são escolhidos olhando o futuro.
    prior = q[max(0, crossing - 3):crossing + 1]
    local_stop = (min(c.low for c in prior) - D('0.10') * a if sign == 1 else
                  max(c.high for c in prior) + D('0.10') * a)
    local_stop = floor_step(local_stop, tick) if sign == 1 else ceil_step(local_stop, tick)
    after = q[crossing + 1]
    entry = next_open(after, case.side, tick)
    trial.update(continuation_signal=datetime.fromtimestamp(signal_bar.end, timezone.utc).isoformat(),
                 continuation_entry=str(entry), continuation_stop=str(local_stop))
    if sign * (entry - local_stop) <= 0:
        trial['continuation'] = 'GEOMETRIA_INVALIDA'
        return trial
    if abs(entry - signal_bar.close) > a * D('0.25'):
        trial['continuation'] = 'GAP_FORA_DA_FAIXA'
        return trial
    # Taxa de 0,06% por lado + spread/deslizamento hipotéticos. Exige 2:1
    # líquido na abertura, sem usar profundidade ou custo de funding histórico.
    risk = abs(entry - local_stop)
    gross_target = entry + sign * D('2.5') * risk
    gross_target = floor_step(gross_target, tick) if sign == 1 else ceil_step(gross_target, tick)
    friction = D('0.0012') * entry + D('0.0004') * entry + 4 * tick
    net_rr = (abs(gross_target - entry) - friction) / (risk + friction)
    trial.update(continuation_target=str(gross_target), estimated_net_rr=str(net_rr))
    if net_rr < 2:
        trial['continuation'] = 'RR_LIQUIDO_INSUFICIENTE'
        return trial
    if after.ts >= closed + horizon:
        trial['continuation'] = 'JANELA_ENCERRADA'
        return trial
    trial['continuation'] = outcome([c for c in q[crossing + 1:] if c.ts < closed + horizon],
                                    case.side, local_stop, gross_target)
    trial['financial_gate'] = 'NAO_VERIFICADO_LIVRO_MARGEM_LOTE_FUNDING_HISTORICOS'
    return trial


def run(client=None) -> list[dict]:
    client = client or MexcClient()
    now = client.server_time()
    catalog = {c['symbol']: c for c in client.contracts()}
    results = []
    for case in CASES:
        if case.symbol not in catalog:
            results.append({'symbol': case.symbol, 'error': 'CONTRATO_AUSENTE'})
            continue
        try:
            data = client.candles(case.symbol, 'Min15', 480, now)
            q = parse_candles(data, 900, now, 480)
            horizon = min(4 * 3600, max(0, now - ts(case.signal) - 10))
            result = review_case(case, q, D(catalog[case.symbol]['priceUnit']), horizon)
            result['window_complete'] = horizon >= 4 * 3600
            results.append(result)
        except Exception as exc:
            # Sem dados, não inventar resultado nem interromper demais casos.
            results.append({'symbol': case.symbol, 'error': type(exc).__name__})
    return results


if __name__ == '__main__':
    import json
    import os
    results = run()
    print(json.dumps(results, ensure_ascii=False, indent=2))
    lines = ['## Teste exploratório de continuação (sem ordens ou avisos)', '',
             'Casos escolhidos após o movimento. Spread, deslizamento e taxas são hipóteses. '
             'Stop tem precedência em candle ambíguo. Janela incompleta é identificada por caso. Não comprova retorno real nem valida a regra prospectivamente.', '',
             '| Ativo | Plano original | Continuação | R:R líquido estimado |', '| --- | --- | --- | --- |']
    for row in results:
        lines.append('| ' + ' | '.join([row['symbol'], row.get('original', row.get('error', '?')),
                                     row.get('continuation', '—'),
                                     row.get('estimated_net_rr', '—')[:7]]) + ' |')
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as out:
            out.write('\n'.join(lines) + '\n')
