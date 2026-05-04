from __future__ import annotations

import json
import logging
from datetime import datetime

from conf.schema import BotConfig
from infra.llm_client import LLMClient
from infra.llm_schemas import ConcentrateItem, ConcentrateOutput
from memory.long_term import LongTermMemory
from memory.schemas import MemoryEntry, MemoryType
from memory.short_term import ShortTermMemory

logger = logging.getLogger(__name__)


class ConcentrateJob:
    def __init__(self, llm: LLMClient, long_term: LongTermMemory, config: BotConfig):
        self.llm = llm
        self.long_term = long_term
        self.config = config
        self._prompt_template = (
            "请将以下对话历史进行浓缩总结，提取重要信息。\n"
            "对每条重要记忆，请提供：\n"
            "- memory_type: event/fact/impression/plan\n"
            "- summary: 记忆摘要\n"
            "- importance: 重要性评分(1-10)\n"
            "- confidence: 置信度(0.0-1.0)\n"
            "- keywords: 关键词列表\n"
            "- source_message_ids: 来源消息ID列表\n"
            "- expires_at: 过期时间(可选, ISO格式)\n\n"
            "请以JSON格式返回，格式为：\n"
            '{"entries": [{"memory_type": "event", "summary": "...", "importance": 5, '
            '"confidence": 0.8, "keywords": ["key1", "key2"], "source_message_ids": ["msg1"]}]}'
        )

    def run(self, chat: ShortTermMemory) -> bool:
        read_msgs = chat.get_read()
        pending_msgs = chat.get_pending()
        all_msgs = pending_msgs + read_msgs

        if not all_msgs:
            return True

        messages = self._build_prompt(all_msgs)
        try:
            raw = self.llm.chat_text(messages)
        except Exception as e:
            logger.error("Concentrate LLM call failed for chat %s: %s", chat.chat_id, e)
            return False

        output = self._parse_output(raw)
        if output is None:
            logger.error("Failed to parse concentrate output for chat %s", chat.chat_id)
            return False

        now = datetime.now().isoformat()
        for item in output.entries:
            entry = MemoryEntry(
                memory_type=item.memory_type,
                chat_type="group",
                chat_id=chat.chat_id,
                timestamp=now,
                importance=item.importance,
                confidence=item.confidence,
                summary=item.summary,
                keywords=",".join(item.keywords) if item.keywords else "",
                source_message_ids=",".join(item.source_message_ids) if item.source_message_ids else "",
                expires_at=item.expires_at.isoformat() if item.expires_at else None,
            )
            merged_id = self.long_term.merge_similar(entry)
            if merged_id is not None:
                logger.debug("Merged entry into existing id=%d", merged_id)
            else:
                new_id = self.long_term.add(entry)
                logger.debug("Added new memory entry id=%d", new_id)

        keep_recent = self.config.memory.pending_threshold
        chat.clear_pending()
        if keep_recent > 0 and len(read_msgs) > keep_recent:
            recent = read_msgs[-keep_recent:]
        else:
            recent = read_msgs
        # Move recent read messages into pending as context for next round
        chat._pending = list(recent)
        chat._read = []
        logger.info(
            "Concentrated chat %s: %d messages → %d entries",
            chat.chat_id, len(all_msgs), len(output.entries),
        )
        return True

    def _build_prompt(self, messages: list) -> list[dict]:
        lines = []
        for msg in messages:
            ts = msg.timestamp.strftime("%H:%M") if hasattr(msg.timestamp, "strftime") else str(msg.timestamp)
            name = getattr(msg, "group_nickname", None) or getattr(msg, "user_nickname", "unknown")
            lines.append(f"[{ts}] {name}: {msg.content}")
        chat_text = "\n".join(lines)

        return [
            {"role": "system", "content": self._prompt_template},
            {"role": "user", "content": f"以下是需要浓缩的对话：\n\n{chat_text}"},
        ]

    @staticmethod
    def _parse_output(raw: str) -> ConcentrateOutput | None:
        try:
            start = raw.find("{")
            end = raw.rfind("}")
            if start == -1 or end == -1 or end <= start:
                return None
            data = json.loads(raw[start : end + 1])
            return ConcentrateOutput.model_validate(data)
        except Exception:
            return None
