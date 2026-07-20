import os

import valkey
from strands import Agent
from strands.models.ollama import OllamaModel
from strands_valkey_session_manager import ValkeySessionManager


def create_model() -> OllamaModel:
    return OllamaModel(
        host=os.getenv("OLLAMA_HOST", "http://localhost:11434"),
        model_id=os.getenv("OLLAMA_MODEL", "llama3.2:1b"),
        temperature=0,
    )


def make_client() -> valkey.Valkey:
    return valkey.Valkey(
        host=os.getenv("VALKEY_HOST", "localhost"),
        port=int(os.getenv("VALKEY_PORT", "6379")),
        decode_responses=True,
    )


def create_agent(client: valkey.Valkey, session_id: str, agent_id: str) -> Agent:
    session_manager = ValkeySessionManager(session_id=session_id, client=client)
    return Agent(
        model=create_model(),
        agent_id=agent_id,
        session_manager=session_manager,
        callback_handler=None,
    )


def delete_session(client: valkey.Valkey, session_id: str, missing_ok: bool = False) -> None:
    manager = ValkeySessionManager(session_id=session_id, client=client)
    if missing_ok and not client.exists(f"session:{session_id}"):
        return
    manager.delete_session(session_id)


def main() -> None:
    client = make_client()
    session_id = "cookbook-session"
    delete_session(client, session_id, missing_ok=True)
    try:
        first = create_agent(client, session_id, "researcher")
        first("Remember that Valkey stores agent sessions.")
        resumed = create_agent(client, session_id, "researcher")
        result = resumed("What fact did I ask you to remember?")
        reader = ValkeySessionManager(session_id=session_id, client=client)
        messages = reader.list_messages(session_id, "researcher")
        print(f"Persisted messages: {len(messages)}")
        print(f"Resumed response: {result}")
    finally:
        delete_session(client, session_id, missing_ok=True)
        client.close()


if __name__ == "__main__":
    main()
