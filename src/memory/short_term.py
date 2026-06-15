"""Short-term memory via sliding conversation window."""

from typing import Optional
from src.state.workflow_state import Message


class ConversationMemory:
    """Sliding-window conversation memory for agent context management.

    Maintains a fixed-size window of recent messages with a configurable
    system prompt, formatted for LLM API consumption.
    """

    def __init__(self, max_window_size: int = 50, system_prompt: str = ""):
        self._messages: list[Message] = []
        self._max_window = max_window_size
        self._system_prompt = system_prompt

    def set_system_prompt(self, prompt: str) -> None:
        """Set the system message shown at the beginning of the context window."""
        self._system_prompt = prompt

    def add_message(self, role: str, content: str, agent: Optional[str] = None) -> None:
        """Add a message to the conversation.

        Args:
            role: 'user', 'assistant', or 'system'.
            content: The message text.
            agent: Optional agent identifier (e.g., 'spec_architect').
        """
        self._messages.append(Message(role=role, content=content, agent=agent))

        # Trim to window size
        if len(self._messages) > self._max_window:
            self._messages = self._messages[-self._max_window:]

    def get_window(self, n: int = 10) -> list[Message]:
        """Get the last n messages.

        Args:
            n: Number of recent messages to retrieve.

        Returns:
            The most recent n messages (or all if fewer than n).
        """
        return self._messages[-n:]

    def get_all(self) -> list[Message]:
        """Get all messages currently in memory."""
        return list(self._messages)

    def get_context_for_llm(self) -> list[dict]:
        """Format messages as OpenAI-compatible message list.

        Returns:
            List of dicts with 'role' and 'content' keys, suitable for
            passing directly to an LLM API call.
        """
        messages: list[dict] = []

        if self._system_prompt:
            messages.append({"role": "system", "content": self._system_prompt})

        for msg in self._messages:
            role = msg.get("role", "user")
            # Map to valid OpenAI roles
            if role not in ("system", "user", "assistant"):
                role = "user"
            messages.append({"role": role, "content": msg.get("content", "")})

        return messages

    def clear(self) -> None:
        """Reset the conversation memory."""
        self._messages.clear()

    def __len__(self) -> int:
        return len(self._messages)

    def __repr__(self) -> str:
        return f"ConversationMemory({len(self)}/{self._max_window} messages)"
