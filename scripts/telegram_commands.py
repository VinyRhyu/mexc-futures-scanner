"""Responde /ajuda durante a rodada do scanner; cursor salvo na branch de estado."""
from __future__ import annotations

import json
from pathlib import Path
import urllib.error
import urllib.request

from mexc_scanner.telegram import TelegramError, send_text

HELP = """📖 GUIA DOS ALERTAS — MEXC SCANNER

👀 Observação: o ativo merece atenção, mas ainda não há entrada definida.

🟡 Possível entrada: há direção, região, stop e alvo. Aguarde o gatilho indicado.

🟢 Gatilho válido para simular: o plano cumpriu as condições dentro do prazo. Você pode registrar uma operação de teste (paper).

✅ Entrada validada: o gatilho e as verificações para uso real passaram. A decisão de operar continua manual.

🟠 Entrada bloqueada: um limite de risco, custo, tamanho mínimo ou outra condição impediu a entrada.

⚪ Plano expirado ou invalidado: o prazo acabou ou a ideia perdeu validade. Espere uma nova análise.

Cada entrada busca retorno/risco líquido mínimo de 2:1, com risco planejado até 10% do saldo. 30% segue como teto absoluto. Ganhos menores podem somar para a meta diária de 60%; se um plano projetar 60%, ele também pode contribuir sozinho. Meta não é obrigação de operar; projeções não garantem lucro.

O scanner não executa ordens. Atualmente opera em modo paper. Confira sempre horário, preço e validade do alerta antes de agir."""


def process_commands(directory: Path, token: str, chat_id: str, transport=None, sender=None) -> int:
    if not token or not chat_id:
        return 0
    cursor = directory / 'telegram-cursor.json'
    offset = 0
    if cursor.exists():
        data = json.loads(cursor.read_text())
        offset = data['offset']
        if type(offset) is not int or offset < 0:
            raise TelegramError('Cursor Telegram inválido')
    payload = {'offset': offset, 'limit': 100, 'timeout': 0, 'allowed_updates': ['message']}
    try:
        if transport:
            result = transport(payload)
        else:
            request = urllib.request.Request('https://api.telegram.org/bot' + token + '/getUpdates',
                data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'}, method='POST')
            with urllib.request.urlopen(request, timeout=15) as response:
                raw = response.read(2_000_001)
            if len(raw) > 2_000_000:
                raise TelegramError('Resposta Telegram excedeu limite')
            result = json.loads(raw)
        if result.get('ok') is not True or not isinstance(result.get('result'), list):
            raise TelegramError('Consulta Telegram rejeitada')
        count = 0
        for update in result['result']:
            number = update.get('update_id')
            if type(number) is not int or number < offset:
                continue
            message = update.get('message') or {}
            chat = message.get('chat') or {}
            if chat.get('type') == 'private' and str(chat.get('id')) == str(chat_id):
                command = (message.get('text') or '').strip().split(maxsplit=1)[0].split('@')[0].lower()
                if command in ('/ajuda', '/help'):
                    send_text(token, chat_id, HELP, sender)
                    count += 1
            # Salvar após cada resposta: retry não duplica respostas já confirmadas.
            offset = number + 1
            cursor.write_text(json.dumps({'offset': offset}) + '\n')
        return count
    except TelegramError:
        raise
    except (urllib.error.URLError, OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        raise TelegramError('Falha ao consultar comandos: ' + type(exc).__name__) from None
