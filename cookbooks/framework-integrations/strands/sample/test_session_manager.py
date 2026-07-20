import os

from strands.models.ollama import OllamaModel
from strands_valkey_session_manager import ValkeySessionManager

from demo import create_agent, create_model, delete_session, make_client


SESSION_ID = "pytest-strands-session"


def test_agent_persists_messages_for_a_second_agent():
    client = make_client()
    delete_session(client, SESSION_ID, missing_ok=True)

    first = create_agent(client, SESSION_ID, "researcher")
    first("Remember that Valkey stores agent sessions.")

    second = create_agent(client, SESSION_ID, "researcher")
    assert len(second.messages) == 2
    assert "Valkey stores agent sessions" in second.messages[0]["content"][0]["text"]
    second("What fact did I ask you to remember?")

    keys = client.keys(f"session:{SESSION_ID}*")
    assert len(keys) >= 4

    reader = ValkeySessionManager(session_id=SESSION_ID, client=client)
    messages = reader.list_messages(SESSION_ID, "researcher")
    assert len(messages) >= 4
    assert any(
        "Valkey stores agent sessions" in block.get("text", "")
        for message in messages
        for block in message.message["content"]
    )

    delete_session(client, SESSION_ID)
    assert client.keys(f"session:{SESSION_ID}*") == []


def test_client_uses_environment_overrides():
    client = make_client()
    assert client.connection_pool.connection_kwargs["host"] == os.getenv("VALKEY_HOST", "localhost")
    assert client.connection_pool.connection_kwargs["port"] == int(os.getenv("VALKEY_PORT", "6379"))


def test_agent_uses_ollama_environment_overrides(monkeypatch):
    monkeypatch.setenv("OLLAMA_HOST", "http://ollama.example:11434")
    monkeypatch.setenv("OLLAMA_MODEL", "test-model")

    model = create_model()

    assert isinstance(model, OllamaModel)
    assert model.host == "http://ollama.example:11434"
    assert model.get_config()["model_id"] == "test-model"
