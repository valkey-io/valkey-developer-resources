"""
Stagehand Python + Valkey Cache Demo

Demonstrates all cookbook topics in a single runnable script:
  1. Basic cached browser action (01-getting-started)
  2. Cache categories, key prefix, and TTL (02-cache-categories-and-ttl)
  3. Production configuration with TLS and auth (03-production-configuration)

Usage:
  # Start the Stagehand server first (from the stagehand repo):
  cd stagehand/packages/server-v3
  VALKEY_HOST=localhost VALKEY_PORT=6379 VALKEY_KEY_PREFIX=stagehand-demo \
    VALKEY_CACHE_TTL=3600 PORT=3000 npx tsx src/server.ts

  # Then run this demo:
  MODEL_API_KEY=your-key python demo.py

Requires:
  - Valkey running on localhost:6379 (see docker-compose.yml)
  - Stagehand server-v3 running on localhost:3000 with Valkey env vars
  - A MODEL_API_KEY for an LLM provider supported by Stagehand
"""

from __future__ import annotations

import os
import sys

from stagehand import Stagehand


def _stream_to_result(stream, label: str) -> object | None:
    result_payload: object | None = None
    for event in stream:
        if event.type == "log":
            print(f"[{label}][log] {event.data.message}")
            continue
        status = event.data.status
        print(f"[{label}][system] status={status}")
        if status == "finished":
            result_payload = event.data.result
        elif status == "error":
            raise RuntimeError(f"{label} error: {event.data.error}")
    return result_payload


def main() -> None:
    model_key = os.environ.get("MODEL_API_KEY")
    if not model_key:
        sys.exit("Set MODEL_API_KEY to run the demo.")

    # --- Connect to the Stagehand server ---
    # The server is configured with Valkey via env vars:
    #   VALKEY_HOST, VALKEY_PORT, VALKEY_KEY_PREFIX, VALKEY_CACHE_TTL
    client = Stagehand(
        base_url=os.environ.get("STAGEHAND_SERVER_URL", "http://localhost:3000"),
        model_api_key=model_key,
    )

    session_id: str | None = None
    try:
        print("Starting session against Stagehand server (with Valkey cache)...")
        session = client.sessions.start(
            model_name="gpt-4o-mini",
            browser={"type": "local", "launchOptions": {"headless": True}},
        )
        session_id = session.data.session_id
        print(f"Session started: {session_id}")

        print("Navigating to https://docs.stagehand.dev...")
        client.sessions.navigate(id=session_id, url="https://docs.stagehand.dev")
        print("Navigation complete")

        # First run: resolves via LLM. Second run: replays from Valkey cache.
        print("Running act() - first call resolves via LLM, second replays from cache")
        act_stream = client.sessions.act(
            id=session_id,
            input="click on the Quickstart link",
            stream_response=True,
            x_stream_response="true",
        )
        _stream_to_result(act_stream, "act")
        print("Action completed")

    except Exception as exc:
        print(f"Error: {exc}")
        raise
    finally:
        if session_id:
            client.sessions.end(id=session_id)
            print("Session ended")
        client.close()
        print("Done! Run again to see the cache hit (no LLM call).")


if __name__ == "__main__":
    main()
