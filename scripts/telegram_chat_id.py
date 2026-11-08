"""Localizar IDs de conversas privadas sem imprimir token, nomes ou mensagens."""
from __future__ import annotations

import json
import os
from pathlib import Path
import urllib.error
import urllib.request

from mexc_scanner.telegram import TelegramError


def private_chat_ids(token: str, transport=None) -> list[int]:
    if not token:
        raise TelegramError("Configure TELEGRAM_BOT_TOKEN nos segredos do GitHub")
    # Sem offset: não confirmar/apagar atualizações nem alterar webhook.
    payload = {"limit": 100, "timeout": 0}
    try:
        if transport:
            result = transport(payload)
        else:
            request = urllib.request.Request("https://api.telegram.org/bot" + token + "/getUpdates",
                data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(request, timeout=15) as response:
                raw = response.read(2_000_001)
            if len(raw) > 2_000_000:
                raise TelegramError("Resposta excede o limite de configuração")
            result = json.loads(raw)
        if result.get("ok") is not True or not isinstance(result.get("result"), list):
            raise TelegramError("Telegram não confirmou a consulta; confira token e eventual webhook existente")
        ids = set()
        for update in result["result"]:
            chat = update.get("message", {}).get("chat", {})
            chat_id = chat.get("id")
            if chat.get("type") == "private" and type(chat_id) is int and chat_id > 0:
                ids.add(chat_id)
        return sorted(ids)
    except TelegramError:
        raise
    except (urllib.error.URLError, OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        # Nunca reproduzir URL, token ou corpo da resposta.
        raise TelegramError("Consulta do Telegram falhou: " + type(exc).__name__) from None


def main() -> int:
    if os.environ.get("REPOSITORY_IS_PRIVATE", "").lower() != "true":
        print("A identificação do chat exige repositório privado")
        return 1
    try:
        ids = private_chat_ids(os.environ.get("TELEGRAM_BOT_TOKEN", ""))
        if not ids:
            print("Nenhum chat privado encontrado. Envie /start ao seu bot e execute novamente.")
            return 1
        lines = ["## Identificar chat Telegram", "",
                 "IDs de conversas privadas encontrados (sem nomes ou conteúdo de mensagens):", ""]
        lines.extend(f"- `{chat_id}`" for chat_id in ids)
        lines.extend(["", "Confirme seu próprio destino e salve o ID como segredo TELEGRAM_CHAT_ID.",
                      "Se houver mais de um ID, não escolha automaticamente: use um bot exclusivo para este scanner.",
                      "Nenhuma mensagem foi enviada nem configuração do bot alterada."])
        summary = "\n".join(lines) + "\n"
        print(summary)
        if os.environ.get("GITHUB_STEP_SUMMARY"):
            with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as output:
                output.write(summary)
        return 0
    except TelegramError as exc:
        print(str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
