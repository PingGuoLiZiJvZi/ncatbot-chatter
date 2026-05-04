from __future__ import annotations

import logging
from pathlib import Path

import yaml

from conf.schema import BotConfig
from memory.schemas import MemoryContext
from memory.short_term import ShortTermMemory

logger = logging.getLogger(__name__)


class ResponseFormatter:
    def __init__(self, config: BotConfig, prompt_path: str = "conf/prompt.yaml", character_path: str = "conf/character.yaml"):
        self.config = config
        self._prompts = self._load_yaml(prompt_path)
        self._character = self._load_yaml(character_path) if Path(character_path).exists() else {}

    @staticmethod
    def _load_yaml(path: str) -> dict:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def format_system_prompt(self, emotion_state: dict | None = None) -> str:
        parts = []
        char_desc = self._character.get("description", "")
        if char_desc:
            parts.append(f"角色设定：\n{char_desc}")

        base = self._prompts.get("base_prompt", "")
        if base:
            parts.append(base.strip())

        if emotion_state:
            parts.append(
                f"当前状态：情绪愉悦度={emotion_state.get('valence', 0):.2f}, "
                f"精力={emotion_state.get('energy', 0):.2f}, "
                f"兴趣={emotion_state.get('interest', 0):.2f}"
            )

        return "\n\n".join(parts)

    def format_memory_context(self, context: MemoryContext) -> str:
        if not context.entries:
            return ""
        lines = ["相关记忆："]
        for entry in context.entries:
            lines.append(f"- [{entry.memory_type.value}] {entry.summary}")
        return "\n".join(lines)

    def format_chat_messages(self, chats: list[ShortTermMemory]) -> str:
        parts = []
        for chat in chats:
            read = chat.get_read()[-10:]
            if read:
                msgs = "\n".join(f"[{m.user_nickname}] {m.content}" for m in read)
                parts.append(f"Chat {chat.chat_id}:\n{msgs}")
        return "\n\n".join(parts)

    def format_response_prompt(self) -> str:
        return self._prompts.get("response_prompt", "").strip()
