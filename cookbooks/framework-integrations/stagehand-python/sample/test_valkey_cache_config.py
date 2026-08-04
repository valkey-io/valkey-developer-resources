"""
Validates two things documented in this cookbook series:

1. `stagehand.types.ValkeyCacheOptions` still exposes the field names used in
   02/03 (host, port, tls, password, username, cache_ttl, key_prefix) — catches
   the docs drifting from the installed SDK's actual contract.
2. The raw Valkey protocol contract the server's caching code is documented to rely
   on: SET/GET/EX under the `{prefix}:{category}:{hash}` key scheme documented in
   01/02, using the `valkey` client directly against a live Valkey container.

Test 2 does NOT start the Stagehand server, and does not import or exercise any
code from the fork's server-side CacheStorage implementation — it only proves the
key scheme and commands are valid Valkey usage, not that the server's actual
caching code path is bug-free. Nothing here calls act()/execute(); that needs the
real server, a real browser, and a paid LLM call, demonstrated manually in demo.py.
"""

import time

import pytest
from valkey import Valkey

from stagehand.types.session_start_params import ValkeyCacheOptions


def test_valkey_cache_options_field_names():
    documented_fields = {
        "host",
        "port",
        "tls",
        "password",
        "username",
        "cache_ttl",
        "key_prefix",
    }
    assert documented_fields <= set(ValkeyCacheOptions.__annotations__)


@pytest.fixture
def client():
    conn = Valkey(host="localhost", port=6379)
    yield conn
    conn.close()


@pytest.fixture
def prefix():
    return f"stagehand-test-{int(time.time() * 1000)}"


def test_write_and_read_an_act_entry(client, prefix):
    key = f"{prefix}:act:a1b2c3d4"
    value = '{"action": "click", "selector": "#quickstart"}'

    client.set(key, value)
    assert client.get(key) == value.encode()

    client.delete(key)


def test_namespaces_agent_entries_separately(client, prefix):
    agent_key = f"{prefix}:agent:e5f6g7h8"
    act_key = f"{prefix}:act:e5f6g7h8"

    client.set(agent_key, '{"steps": ["navigate", "click"]}')

    assert client.get(agent_key) is not None
    assert client.get(act_key) is None

    client.delete(agent_key)


def test_expires_entries_written_with_ttl(client, prefix):
    key = f"{prefix}:act:ttl-check"

    client.set(key, "cached-value", ex=1)
    assert client.get(key) == b"cached-value"

    ttl = client.ttl(key)
    assert 0 < ttl <= 1

    client.delete(key)


def test_cache_miss_returns_none_without_raising(client, prefix):
    assert client.get(f"{prefix}:act:never-written") is None
