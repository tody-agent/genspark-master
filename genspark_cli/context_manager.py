"""Smart context tracking and conversation health management.

Monitors conversation length and suggests compaction when conversations
get too long — inspired by Claude Code's /compact behavior.

Thresholds:
    - 7 turns:  Suggest /compact (gentle hint)
    - 12 turns: Warn about context quality degradation
    - 20 turns: Auto-compact with notification

The summarization uses the AI itself (meta-call via GensparkClient)
to produce a high-quality summary of the conversation so far.
"""

import time
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from .conversations import Conversation, ConversationStore
from .log import log


# ── Thresholds ───────────────────────────────────────────────────────────

SUGGEST_COMPACT_AT = 7       # Gentle suggestion
WARN_COMPACT_AT = 12         # Stronger warning
AUTO_COMPACT_AT = 20         # Auto-compact

# Estimated tokens per message (rough heuristic)
EST_TOKENS_PER_CHAR = 0.25


class ContextAdvice(Enum):
    """Advice for the user about conversation context health."""
    CONTINUE = "continue"
    SUGGEST_COMPACT = "suggest_compact"
    WARN_COMPACT = "warn_compact"
    AUTO_COMPACT = "auto_compact"


@dataclass
class ContextHealth:
    """Current context health assessment."""
    advice: ContextAdvice
    turn_count: int
    estimated_tokens: int
    message: str
    should_auto_compact: bool = False


# ── Summary Prompt ───────────────────────────────────────────────────────

SUMMARY_PROMPT = """Summarize this conversation concisely, preserving:
1. Key decisions and conclusions
2. Important code/technical details mentioned
3. Open questions or next steps
4. Any specific preferences or constraints established

Keep it under 500 words. Write in the same language as the conversation.

Conversation:
{conversation_text}""".strip()


COMPACT_CONTINUE_PROMPT = """Here is a summary of our previous conversation:

{summary}

Please continue from where we left off. I may ask follow-up questions.""".strip()


class ContextManager:
    """Monitors conversation health and manages compaction.

    Usage:
        ctx_mgr = ContextManager()
        health = ctx_mgr.check_health(conversation)

        if health.advice == ContextAdvice.AUTO_COMPACT:
            new_conv = await ctx_mgr.compact(client, conversation, store)
    """

    def __init__(
        self,
        suggest_at: int = SUGGEST_COMPACT_AT,
        warn_at: int = WARN_COMPACT_AT,
        auto_at: int = AUTO_COMPACT_AT,
    ):
        self.suggest_at = suggest_at
        self.warn_at = warn_at
        self.auto_at = auto_at

    def check_health(self, conversation: Conversation) -> ContextHealth:
        """Assess the health of a conversation's context.

        Args:
            conversation: The conversation to check.

        Returns:
            ContextHealth with advice and display message.
        """
        turns = conversation.user_turn_count
        est_tokens = self._estimate_tokens(conversation)

        if turns >= self.auto_at:
            return ContextHealth(
                advice=ContextAdvice.AUTO_COMPACT,
                turn_count=turns,
                estimated_tokens=est_tokens,
                message=(
                    f"🔄 Auto-compacting conversation ({turns} turns)...\n"
                    f"   Creating summary and starting fresh session..."
                ),
                should_auto_compact=True,
            )

        if turns >= self.warn_at:
            return ContextHealth(
                advice=ContextAdvice.WARN_COMPACT,
                turn_count=turns,
                estimated_tokens=est_tokens,
                message=(
                    f"⚠️  {turns} turns — context may be getting noisy.\n"
                    f"   Run /compact to create a summary and continue with fresh context.\n"
                    f"   Estimated context: ~{est_tokens:,} tokens"
                ),
            )

        if turns >= self.suggest_at:
            return ContextHealth(
                advice=ContextAdvice.SUGGEST_COMPACT,
                turn_count=turns,
                estimated_tokens=est_tokens,
                message=(
                    f"💡 This conversation has {turns} turns. Consider /compact to summarize\n"
                    f"   and start fresh for better context quality."
                ),
            )

        return ContextHealth(
            advice=ContextAdvice.CONTINUE,
            turn_count=turns,
            estimated_tokens=est_tokens,
            message="",
        )

    def _estimate_tokens(self, conversation: Conversation) -> int:
        """Rough token estimate for the conversation."""
        total_chars = sum(len(m.content) for m in conversation.messages)
        if conversation.summary:
            total_chars += len(conversation.summary)
        return int(total_chars * EST_TOKENS_PER_CHAR)

    def format_context_info(self, conversation: Conversation) -> str:
        """Format context info for /context command display."""
        turns = conversation.user_turn_count
        total_msgs = len(conversation.messages)
        est_tokens = self._estimate_tokens(conversation)
        total_chars = sum(len(m.content) for m in conversation.messages)

        lines = [
            f"  Session: {conversation.display_name}",
            f"  ID: {conversation.id[:12]}...",
            f"  Model: {conversation.model or 'default'}",
            f"  Profile: {conversation.profile}",
            f"  Turns: {turns} user / {total_msgs} total messages",
            f"  Content: ~{total_chars:,} chars / ~{est_tokens:,} tokens (est.)",
        ]

        if conversation.summary:
            lines.append(f"  Has summary: yes ({len(conversation.summary)} chars)")
        if conversation.parent_id:
            lines.append(f"  Forked from: {conversation.parent_id[:12]}...")

        # Health indicator
        health = self.check_health(conversation)
        if health.advice == ContextAdvice.CONTINUE:
            lines.append(f"  Context health: 🟢 Good")
        elif health.advice == ContextAdvice.SUGGEST_COMPACT:
            lines.append(f"  Context health: 🟡 Consider compacting")
        elif health.advice == ContextAdvice.WARN_COMPACT:
            lines.append(f"  Context health: 🟠 Getting long — compact recommended")
        elif health.advice == ContextAdvice.AUTO_COMPACT:
            lines.append(f"  Context health: 🔴 Too long — auto-compact needed")

        return "\n".join(lines)

    # ── Summarization ────────────────────────────────────────────────────

    def build_summary_prompt(self, conversation: Conversation, instruction: str = "") -> str:
        """Build a prompt to summarize the conversation.

        Args:
            conversation: The conversation to summarize.
            instruction: Optional user instruction for the summary
                         (e.g., "focus on the API changes").

        Returns:
            Formatted prompt string for the AI.
        """
        # Build conversation text
        parts = []
        for msg in conversation.messages:
            role_label = "User" if msg.role == "user" else "Assistant"
            parts.append(f"{role_label}: {msg.content}")

        conversation_text = "\n\n".join(parts)

        prompt = SUMMARY_PROMPT.format(conversation_text=conversation_text)

        if instruction:
            prompt += f"\n\nAdditional focus: {instruction}"

        return prompt

    async def generate_summary(
        self,
        client,  # GensparkClient — not imported to avoid circular
        conversation: Conversation,
        instruction: str = "",
    ) -> str:
        """Use the AI to generate a conversation summary.

        Args:
            client: GensparkClient instance.
            conversation: The conversation to summarize.
            instruction: Optional focus instruction.

        Returns:
            Summary text generated by the AI.
        """
        prompt = self.build_summary_prompt(conversation, instruction)

        log.info(
            "Generating conversation summary (%d messages)",
            len(conversation.messages),
            extra={"event": "summary_start"},
        )

        t0 = time.monotonic()
        response = await client.chat(prompt)
        elapsed_ms = int((time.monotonic() - t0) * 1000)

        log.info(
            "Summary generated: %d chars in %dms",
            len(response.content), elapsed_ms,
            extra={"event": "summary_done"},
        )

        return response.content

    async def compact(
        self,
        client,  # GensparkClient
        conversation: Conversation,
        store: ConversationStore,
        instruction: str = "",
    ) -> Conversation:
        """Compact a conversation: summarize → fork → return new conversation.

        1. Generate summary of the current conversation
        2. Save summary to the current conversation
        3. Fork a new conversation with the summary as initial context
        4. Return the new conversation

        Args:
            client: GensparkClient for generating the summary.
            conversation: The conversation to compact.
            store: ConversationStore for persistence.
            instruction: Optional focus instruction for the summary.

        Returns:
            New Conversation with summary as context.
        """
        # 1. Generate summary
        summary = await self.generate_summary(client, conversation, instruction)

        # 2. Save summary on parent
        store.set_summary(conversation.id, summary)

        # 3. Fork with summary
        new_conv = store.fork(
            parent_id=conversation.id,
            summary=summary,
            model=conversation.model,
            profile=conversation.profile,
        )

        if new_conv is None:
            raise RuntimeError(f"Failed to fork conversation {conversation.id[:8]}")

        log.info(
            "Compacted conversation %s → %s (%d turns → summary)",
            conversation.id[:8], new_conv.id[:8], conversation.user_turn_count,
            extra={"event": "compact_done"},
        )

        return new_conv

    def build_continue_prompt(self, summary: str) -> str:
        """Build a prompt to continue a conversation from a summary."""
        return COMPACT_CONTINUE_PROMPT.format(summary=summary)
