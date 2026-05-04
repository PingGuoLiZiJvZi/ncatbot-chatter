from __future__ import annotations

from memory.schemas import Message
from memory.short_term import ShortTermMemory


class MemoryManager:
    def __init__(self, short_term_max: int = 100):
        self._short_term_max = short_term_max
        self._chats: dict[str, ShortTermMemory] = {}

    def add_message(self, msg: Message) -> None:
        chat = self.get_or_create_chat(msg.chat_id)
        chat.add_incoming(msg)

    def get_or_create_chat(self, chat_id: str) -> ShortTermMemory:
        if chat_id not in self._chats:
            self._chats[chat_id] = ShortTermMemory(chat_id, self._short_term_max)
        return self._chats[chat_id]

    def get_chat(self, chat_id: str) -> ShortTermMemory | None:
        return self._chats.get(chat_id)

    def get_active_chats(self) -> list[ShortTermMemory]:
        return [chat for chat in self._chats.values() if chat.get_unread_count() > 0]

    def get_all_chats(self) -> list[ShortTermMemory]:
        return list(self._chats.values())
