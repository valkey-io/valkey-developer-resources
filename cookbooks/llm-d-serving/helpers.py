"""Helpers shared by the notebook and ``test_llm_d_serving.py``.

Both import from here, so the live tests exercise the same code the notebook
runs: the Prometheus scraping, the Valkey waits, the synthetic lease document,
and the batch-job submitter that speaks llm-d-async's wire format.

Only the standard library is imported at module level. The Valkey GLIDE client
is imported inside the functions that need it, so the structural tests can
import this module in a CI job that has no stack.
"""

from __future__ import annotations

import contextlib
import functools
import json
import re
import secrets
import socket
import time
import urllib.request

# ---------------------------------------------------------------------------
# Valkey
# ---------------------------------------------------------------------------


def connect(host: str, port: int, database_id: int):
    """A Valkey GLIDE client for one database."""
    from glide_sync import GlideClient, GlideClientConfiguration, NodeAddress

    return GlideClient.create(GlideClientConfiguration(
        addresses=[NodeAddress(host, port)], database_id=database_id, request_timeout=5000))


def settled_dbsize(client, quiet_s: float = 1.0, timeout_s: float = 15.0) -> int:
    """The client's ``DBSIZE`` once it has not changed for ``quiet_s`` seconds.

    The LMCache server writes KV to Valkey asynchronously, so a replica that
    asks for a prefix right after another replica computed it can find chunks
    that are not stored yet. Call this before expecting a Valkey load.
    """
    deadline = time.monotonic() + timeout_s
    last, since = int(client.custom_command(["DBSIZE"])), time.monotonic()
    while time.monotonic() < deadline:
        time.sleep(0.1)
        current = int(client.custom_command(["DBSIZE"]))
        if current != last:
            last, since = current, time.monotonic()
        elif time.monotonic() - since >= quiet_s:
            break
    return last


# ---------------------------------------------------------------------------
# Prometheus metrics
# ---------------------------------------------------------------------------


def scrape(url: str) -> str:
    """The text of a Prometheus ``/metrics`` endpoint."""
    with urllib.request.urlopen(url, timeout=5) as resp:
        return resp.read().decode()


def metric(text: str, name: str, **labels) -> float:
    """Sum every sample of a Prometheus metric whose labels include ``labels``."""
    total = 0.0
    for match in re.finditer(rf"^{re.escape(name)}(?:\{{([^}}]*)\}})? (\S+)$", text, re.M):
        found = dict(re.findall(r'(\w+)="([^"]*)"', match.group(1) or ""))
        if all(found.get(k) == v for k, v in labels.items()):
            total += float(match.group(2))
    return total


# ---------------------------------------------------------------------------
# Requests
# ---------------------------------------------------------------------------


def document(tag: str, clauses: int = 29) -> str:
    """A synthetic lease. At 29 clauses, roughly 900-1,100 tokens, depending on ``tag``."""
    return f"[document {tag}] " + " ".join(
        f"Clause {i}: the tenant of unit {tag} shall keep fixture {i * 7 % 13} in good "
        f"repair and report any fault within {i % 5 + 1} days." for i in range(clauses))


def close_connections(connections: list) -> None:
    """Close every connection, even if one fails.

    Closing the socket makes vLLM abort a request it is still generating.
    """
    for conn in connections:
        if conn.sock is not None:
            with contextlib.suppress(OSError):
                conn.sock.shutdown(socket.SHUT_RDWR)
        conn.close()


# ---------------------------------------------------------------------------
# Batch jobs in llm-d-async's wire format
# ---------------------------------------------------------------------------

# submitRequestScript from llm-d-async v1.0.0 producer/redis_sortedset_producer.go,
# copied unchanged. Apache License 2.0:
# https://github.com/llm-d/llm-d-async/blob/main/LICENSE
SUBMIT_REQUEST_LUA = """
local seq = redis.call("INCR", KEYS[1])
redis.call("EXPIREAT", KEYS[1], ARGV[3])
redis.call("DEL", KEYS[2])
redis.call("SET", KEYS[3], ARGV[1], "PX", ARGV[2])
local score = tonumber(ARGV[6]) + math.min(seq, 2097151) / 2097152
redis.call("ZADD", KEYS[4], string.format("%.17g", score), ARGV[4] .. seq .. ARGV[5])
if KEYS[5] then
  redis.call("SET", KEYS[5], ARGV[7], "PX", ARGV[8])
end
return seq
"""


@functools.cache
def _submit_script():
    from glide_sync import Script

    return Script(SUBMIT_REQUEST_LUA)


def go_json(value) -> str:
    """JSON the way Go's encoding/json writes it: compact, UTF-8, <>& escaped."""
    text = json.dumps(value, separators=(",", ":"), ensure_ascii=False)
    for char, escaped in (("<", "\\u003c"), (">", "\\u003e"), ("&", "\\u0026"),
                          ("\u2028", "\\u2028"), ("\u2029", "\\u2029")):
        text = text.replace(char, escaped)
    return text


def job_envelope(job_id: str, prompt: str, *, model: str, token: str, created: int,
                 deadline: int, userid: str | None = None, max_tokens: int = 16,
                 queue: str = "request-sortedset", results: str = "result-list") -> str:
    """One /v1/completions job as llm-d-async's producer serializes it.

    Field order matches the Go structs (api.InternalRouting, api.RequestMessage),
    and ``metadata`` is left out without a ``userid``, as Go's ``omitempty``
    does. ``enqueue_seq`` is a -1 placeholder that the Lua script replaces.
    """
    data = {"id": job_id, "created": created, "deadline": deadline,
            "payload": {"model": model, "prompt": prompt, "max_tokens": max_tokens,
                        "temperature": 0}}
    if userid is not None:
        data["metadata"] = {"userid": userid}
    data |= {"endpoint": "/v1/completions", "model": model}
    return go_json({
        "internal": {"request_token": token, "request_queue_name": queue,
                     "result_queue_name": results, "enqueue_seq": -1},
        "request_kind": "plain",
        "data": data,
    })


def submit_job(client, job_id: str, prompt: str, *, model: str, userid: str | None = None,
               max_tokens: int = 16, ttl_s: int = 300, queue: str = "request-sortedset",
               results: str = "result-list") -> int:
    """Enqueue one /v1/completions job the way llm-d-async's producer does.

    Returns the job's sequence number among jobs with the same deadline.
    """
    created = int(time.time())
    deadline = created + ttl_s
    token = secrets.token_hex(16)
    envelope = job_envelope(job_id, prompt, model=model, token=token, created=created,
                            deadline=deadline, userid=userid, max_tokens=max_tokens,
                            queue=queue, results=results)
    # The script splices the sequence number in where the -1 placeholder is.
    head, tail = envelope.split('"enqueue_seq":-1', 1)
    keys = [f"request-seq:{queue}:{deadline}", f"request-cancel:{job_id}",
            f"request-active:{job_id}", queue]
    args = [token, str(max(int((deadline - time.time()) * 1000), 1)), str(deadline + 3600),
            head + '"enqueue_seq":', tail, str(deadline)]
    return client.invoke_script(_submit_script(), keys=keys, args=args)
