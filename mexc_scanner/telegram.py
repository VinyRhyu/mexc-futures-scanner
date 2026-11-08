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


def drain_outbox(state: dict, now: int, token: str, chat_id: str, transport=None) -> dict:
    counts = {"sent": 0, "expired": 0, "failed": 0, "configuration": "OK"}
    configured = bool(token and chat_id)
    if not configured:
        counts["configuration"] = "TELEGRAM_NAO_CONFIGURADO"
    for message in state["outbox"].values():
        if message["status"] != "PENDING":
            continue
        if now >= message["expires_at"] or (message["category"] == "ENTRY" and now - message["quote_at"] > 60):
            message["status"] = "EXPIRED"
            counts["expired"] += 1
            pending = state["wallet"].get("pending")
            if pending and pending.get("delivery_event_id") == message["id"] and message["attempts"] == 0:
                state["wallet"]["pending"] = None
            continue
        if not configured:
            continue
        message["attempts"] += 1
        try:
            message["telegram_ids"] = send_text(token, chat_id, message["text"], transport)
            message["status"], message["sent_at"] = "SENT", now
            counts["sent"] += 1
        except TelegramError as exc:
            message["last_error"] = str(exc)
            counts["failed"] += 1
            break
    return counts
