"""Agno + Valkey: Agent session storage demo.

Demonstrates ValkeyDb as a persistent storage backend for Agno agents.
Uses Ollama (free, local) as the model — no API keys needed.

Usage:
    docker run -d --name valkey -p 127.0.0.1:6379:6379 valkey/valkey-bundle:9.1.0
    ollama pull llama3.2
    pip install "agno[valkey,ollama]==2.8.0"
    python agent_storage.py
"""

from __future__ import annotations

from agno.agent import Agent
from agno.db.base import SessionType
from agno.db.valkey import ValkeyDb
from agno.models.ollama import Ollama


def main() -> None:
    # Connect to Valkey (defaults: localhost:6379)
    db = ValkeyDb()

    # Create agent with Valkey-backed session storage
    # Uses Ollama (free, local). For OpenAI: remove the model param and set OPENAI_API_KEY.
    agent = Agent(
        model=Ollama(id="llama3.2"),
        db=db,
        add_history_to_context=True,
    )

    # First interaction — stores session in Valkey
    agent.print_response("My favorite color is blue")

    # Second interaction — agent has context from first
    agent.print_response("What is my favorite color?")

    # Verify sessions are persisted
    sessions = db.get_sessions(session_type=SessionType.AGENT)
    print(f"\nSessions stored in Valkey: {len(sessions)}")
    assert len(sessions) >= 1, "Expected at least 1 session in Valkey"
    print("✓ Session persistence verified")


if __name__ == "__main__":
    main()
