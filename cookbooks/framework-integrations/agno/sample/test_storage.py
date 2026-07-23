"""CI tests for Agno + Valkey storage adapter.

Uses ValkeyDb directly without an LLM — tests session persistence.
Requires Valkey running on localhost:6379.
"""

from __future__ import annotations

import uuid

import pytest

from agno.db.valkey import ValkeyDb
from agno.session.agent import AgentSession


@pytest.fixture(scope="module")
def db():
    """Create a ValkeyDb instance for tests."""
    store = ValkeyDb(host="localhost", port=6379)
    yield store


class TestValkeyDbStorage:
    """Test ValkeyDb session storage operations."""

    def test_upsert_and_get_session(self, db: ValkeyDb):
        """Store a session and retrieve it."""
        session_id = f"test-session-{uuid.uuid4().hex[:8]}"
        session = AgentSession(
            session_id=session_id,
            user_id="test-user",
            agent_id="test-agent",
            session_data={"messages": [{"role": "user", "content": "Hello"}]},
        )
        db.upsert_session(session)

        # Retrieve by session_id
        retrieved = db.get_session(session_id)
        assert retrieved is not None
        assert retrieved.session_id == session_id
        assert retrieved.user_id == "test-user"

        # Cleanup
        db.delete_session(session_id)

    def test_get_sessions(self, db: ValkeyDb):
        """List all sessions."""
        session_id = f"test-list-{uuid.uuid4().hex[:8]}"
        session = AgentSession(
            session_id=session_id,
            user_id="list-user",
            agent_id="list-agent",
        )
        db.upsert_session(session)

        sessions = db.get_sessions()
        assert len(sessions) >= 1
        found = any(s.session_id == session_id for s in sessions)
        assert found, f"Session {session_id} not found in listing"

        # Cleanup
        db.delete_session(session_id)

    def test_delete_session(self, db: ValkeyDb):
        """Delete a session by ID."""
        session_id = f"test-delete-{uuid.uuid4().hex[:8]}"
        session = AgentSession(
            session_id=session_id,
            user_id="del-user",
        )
        db.upsert_session(session)

        # Confirm it exists
        assert db.get_session(session_id) is not None

        # Delete
        db.delete_session(session_id)

        # Confirm gone
        assert db.get_session(session_id) is None

    def test_session_update(self, db: ValkeyDb):
        """Upsert with same session_id updates the record."""
        session_id = f"test-update-{uuid.uuid4().hex[:8]}"
        session = AgentSession(
            session_id=session_id,
            user_id="update-user",
            session_data={"version": 1},
        )
        db.upsert_session(session)

        # Update
        session_v2 = AgentSession(
            session_id=session_id,
            user_id="update-user",
            session_data={"version": 2},
        )
        db.upsert_session(session_v2)

        retrieved = db.get_session(session_id)
        assert retrieved is not None
        assert retrieved.session_data.get("version") == 2

        # Cleanup
        db.delete_session(session_id)
