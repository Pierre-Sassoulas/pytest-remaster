"""Fake Slack-like chatbot for demonstrating pytest-remaster."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ChatMessage:
    channel: str
    text: str
    emoji: str | None = None

    def __str__(self) -> str:
        prefix = f"{self.emoji} " if self.emoji else ""
        return f"[{self.channel}] {prefix}{self.text}"


def handle_command(command: str) -> list[ChatMessage]:
    """Process a chat command and return response messages."""
    parts = command.split(maxsplit=1)
    verb = parts[0] if parts else ""
    arg = parts[1] if len(parts) > 1 else ""

    if verb == "hello":
        return [
            ChatMessage(channel="#general", text=f"Hello, {arg}!", emoji=":wave:"),
        ]
    if verb == "goodbye":
        return [
            ChatMessage(channel="#general", text=f"Goodbye, {arg}!", emoji=":wave:"),
            ChatMessage(
                channel="#general", text=f"{arg} has left the chat.", emoji=":door:"
            ),
        ]
    return [
        ChatMessage(channel="#errors", text=f"Unknown command: {verb}", emoji=":x:"),
        ChatMessage(
            channel="#general",
            text="Available commands: hello, goodbye",
            emoji=":info:",
        ),
    ]
