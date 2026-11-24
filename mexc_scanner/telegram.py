from __future__ import annotations

import json
import urllib.error
import urllib.request


class TelegramError(RuntimeError):
    pass


def send_text(token: str, chat_id: str, text: str, transport=None) -> list[int]:
    if not token or not chat_id:
        raise TelegramError("TELEGRAM_NAO_CONFIGURADO")
    chunks = [text[i:i + 3500] for i in range(0, len(text), 3500)] or [text]
    ids = []
    for index, chunk in enumerate(chunks):
        payload = {"chat_id": chat_id, "text": chunk + (f"\nParte {index + 1}/{len(chunks)}" if len(chunks) > 1 else "")}
        try:
            if transport:
                result = transport(payload)
            else:
                request = urllib.request.Request("https://api.telegram.org/bot" + token + "/sendMessage",
                    data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"}, method="POST")
                with urllib.request.urlopen(request, timeout=15) as response:
                    result = json.load(response)
            if not result.get("ok"):
                # Não reproduzir URL, token nem mensagem de erro remota.
                raise TelegramError("TELEGRAM_REJEITOU_MENSAGEM")
            ids.append(int(result["result"]["message_id"]))
        except TelegramError:
            raise
        except (urllib.error.URLError, OSError, ValueError, KeyError) as exc:
            raise TelegramError("TELEGRAM_FALHA_OU_RESULTADO_AMBIGUO: " + type(exc).__name__) from None
    return ids


def allowed_scanner_alert(message: dict) -> bool:
    """Strict delivery allowlist. Old queued messages are NOT grandfathered in.

    Requires an explicit current-format marker AND an exact line layout.
    This protects future scanner changes from accidentally reviving summaries,
    blocked confirmations, debugging output or verbose legacy ENTRY rows.
    """
    content = message.get("text", "")
    if not isinstance(content, str):
        return False
    lines = content.splitlines()
    if (message.get("category") == "ENTRY" and
            message.get("notification_format") == "entry_only_v2"):
        return (len(lines) == 10 and
                lines[0] in {"🟢 SINAL DE ENTRADA • SIMULAÇÃO",
                             "🟢 SINAL DE ENTRADA • EXECUÇÃO MANUAL"} and
                lines[1].startswith("MOEDA: ") and
                lines[2] in {"MOVIMENTO: 📈 LONG (ALTA)",
                             "MOVIMENTO: 📉 SHORT (BAIXA)"} and
                lines[3].startswith("ALAVANCAGEM: ") and
                lines[4] == "" and
                lines[5].startswith("ENTRADA: ") and
                lines[6].startswith("TP1: ") and
                lines[7] == "TP2: não definido (modelo atual tem apenas um alvo técnico)" and
                lines[8] == "" and lines[9].startswith("SL: "))
    return False


def drain_outbox(state: dict, now: int, token: str, chat_id: str, transport=None, *, clock=None, observer=None) -> dict:
    counts = {"sent": 0, "expired": 0, "suppressed": 0, "failed": 0, "configuration": "OK"}
    configured = bool(token and chat_id)
    if not configured:
        counts["configuration"] = "TELEGRAM_NAO_CONFIGURADO"
    # All non-ENTRY rows (including previously pending M1 movement notices)
    # are expired by the allowlist before ANY Telegram transport call.
    messages = sorted(state["outbox"].values(), key=lambda m: (
        0 if m["category"] == "ENTRY" else 1, m["created_at"]))
    def record(event, message, current, **extra):
        if observer:
            fields = {k: message[k] for k in ('plan_id', 'variant', 'signal_at', 'symbol', 'side') if k in message}
            observer(event, event_id=message['id'], created_at=message['created_at'],
                     quote_at=message['quote_at'], expires_at=message['expires_at'],
                     status=message['status'], attempt=message['attempts'], observed_at=current,
                     **fields, **extra)

    for message in messages:
        if message["status"] != "PENDING":
            continue
        current = int(clock()) if clock else now
        if not allowed_scanner_alert(message):
            message["status"] = "EXPIRED"
            counts["suppressed"] += 1
            counts["expired"] += 1
            record("delivery_suppressed_non_signal", message, current)
            pending = state["wallet"].get("pending")
            if (pending and pending.get("delivery_event_id") == message["id"]
                    and message["attempts"] == 0):
                state["wallet"]["pending"] = None
            continue
        if current >= message["expires_at"] or (message["category"] == "ENTRY" and current - message["quote_at"] > 60):
            message["status"] = "EXPIRED"
            counts["expired"] += 1
            record("delivery_expired", message, current)
            pending = state["wallet"].get("pending")
            if pending and pending.get("delivery_event_id") == message["id"] and message["attempts"] == 0:
                state["wallet"]["pending"] = None
            continue
        if not configured:
            continue
        message["attempts"] += 1
        record("delivery_attempt", message, current)
        try:
            message["telegram_ids"] = send_text(token, chat_id, message["text"], transport)
            message["status"], message["sent_at"] = "SENT", int(clock()) if clock else now
            counts["sent"] += 1
            record("delivery_sent", message, message["sent_at"], sent_at=message["sent_at"])
        except TelegramError as exc:
            message["last_error"] = str(exc)
            counts["failed"] += 1
            record("delivery_failed", message, int(clock()) if clock else now,
                   failure_type=str(exc).split(":", 1)[0])
            break
    return counts
