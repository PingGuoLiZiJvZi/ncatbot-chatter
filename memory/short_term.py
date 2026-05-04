from __future__ import annotations

import threading
from memory.schemas import Message, SelfMessage


class ShortTermMemory:
    def __init__(self, chat_id: str, max_size: int = 100):
        self.chat_id = chat_id
        self.max_size = max_size
        self._unread: list[Message] = []
        self._read: list[Message] = []
        self._pending: list[Message] = []
        self._self_sent: list[SelfMessage] = []
        self._lock = threading.Lock()

    def add_incoming(self, msg: Message) -> None:
        with self._lock:
            self._unread.append(msg)

    def consume_unread(self) -> list[Message]:
        with self._lock:
            unread = self._unread
            self._unread = []
        self._read.extend(unread)
        return unread

    def add_self_sent(self, msg: SelfMessage) -> None:
        self._self_sent.append(msg)

    def get_read(self) -> list[Message]:
        return list(self._read)

    def get_pending(self) -> list[Message]:
        return list(self._pending)

    def get_unread_count(self) -> int:
        with self._lock:
            return len(self._unread)

    def rotate_read_to_pending(self) -> None:
        self._pending = self._read
        self._read = []

    def clear_pending(self) -> None:
        self._pending = []

    def should_concentrate(self, threshold: int) -> bool:
        return len(self._read) > threshold
