"""Конфигурация бота."""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class BotConfig:
    bot_token: str
    api_base_url: str  # backend API
    log_chat_id: int | None = None

    @classmethod
    def from_env(cls) -> "BotConfig":
        token = os.environ.get("BOT_TOKEN")
        if not token:
            raise RuntimeError("BOT_TOKEN is not set")
        return cls(
            bot_token=token,
            api_base_url=os.environ.get("API_BASE_URL", "http://localhost:8000"),
            log_chat_id=int(os.environ["LOG_CHAT_ID"]) if "LOG_CHAT_ID" in os.environ else None,
        )