"""LocalAI + Valkey vector store — full lifecycle demo.

Drives LocalAI's /stores/* REST API with the `valkey-store` backend to store,
search, and delete embedding vectors persisted in Valkey Search.

Runnable companion to the LocalAI + Valkey cookbook series:
  cookbooks/framework-integrations/localai/README.md

Dependencies (see requirements.txt):
  - requests           HTTP client for the /stores/* API
  - python-dotenv      loads .env for configuration

Prerequisites:
  - A Valkey server with the Valkey Search (FT.*) module, e.g.
        docker run -d --name valkey -p 6379:6379 valkey/valkey-bundle:8.1.7
  - A running LocalAI with the `valkey-store` backend registered. Until
    mudler/LocalAI#10770 merges and ships in the backend gallery, build the
    backend from the PR branch (see the cookbook's 01-getting-started.md).
"""

import os
import sys
import time

# Third-party imports are guarded so a missing dependency prints an install
# hint and exits, rather than raising an opaque ImportError before main() runs.
try:
    import requests
    from dotenv import load_dotenv
except ImportError as exc:
    sys.exit(
        f"Missing dependency ({exc.name}). Install requirements first:\n"
        "  pip install -r requirements.txt"
    )

load_dotenv()

# --- Configuration (env-overridable, with defaults) ---
BASE_URL = os.environ.get("LOCALAI_BASE_URL", "http://localhost:8080")
BACKEND = os.environ.get("STORE_BACKEND", "valkey-store")  # route /stores/* to Valkey
STORE = os.environ.get("STORE_NAME", "cookbook-demo")      # namespace / "table"
TIMEOUT = float(os.environ.get("REQUEST_TIMEOUT", "5.0"))  # per-request seconds; raise for slow nets

# One session reused for every request (expensive objects instantiated once).
SESSION = requests.Session()


def stores_set(keys, values):
    """Store vectors (keys) with their opaque values."""
    resp = SESSION.post(
        f"{BASE_URL}/stores/set",
        json={"backend": BACKEND, "store": STORE, "keys": keys, "values": values},
        timeout=TIMEOUT,
    )
    resp.raise_for_status()


def stores_get(keys):
    """Fetch values by exact vector match. Missing keys are omitted."""
    resp = SESSION.post(
        f"{BASE_URL}/stores/get",
        json={"backend": BACKEND, "store": STORE, "keys": keys},
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()


def stores_find(query, topk):
    """Return the topk nearest stored vectors to `query`, nearest-first."""
    resp = SESSION.post(
        f"{BASE_URL}/stores/find",
        json={"backend": BACKEND, "store": STORE, "key": query, "topk": topk},
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()


def stores_delete(keys):
    """Delete entries by exact vector. Missing keys are tolerated."""
    resp = SESSION.post(
        f"{BASE_URL}/stores/delete",
        json={"backend": BACKEND, "store": STORE, "keys": keys},
        timeout=TIMEOUT,
    )
    resp.raise_for_status()


def find_when_ready(query, topk, expect, attempts=20, delay=0.25):
    """Poll Find until at least `expect` results appear.

    Valkey Search back-fills its vector index asynchronously after a write, so a
    Find right after Set may not see the new vectors yet. attempts * delay caps
    the wait (20 * 0.25s = 5s) so a genuinely empty/misconfigured store fails
    loudly instead of hanging.
    """
    result = {"keys": []}
    for _ in range(attempts):  # bounded — never loop unboundedly
        result = stores_find(query, topk)
        if len(result["keys"]) >= expect:
            return result
        time.sleep(delay)
    raise AssertionError(
        f"only {len(result['keys'])}/{expect} results after back-fill wait"
    )


def main():
    # Four unit vectors along the axes: geometry is obvious, so the cosine
    # similarities below are easy to reason about.
    keys = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0], [-1.0, 0.0, 0.0]]
    values = ["pos-x", "pos-y", "pos-z", "neg-x"]

    # Idempotent: clear any entries left by a previous run so reruns don't build
    # on stale state. Delete tolerates missing keys, so this is a safe no-op the
    # first time through.
    stores_delete(keys)

    print(f"Storing {len(keys)} vectors in store '{STORE}' via '{BACKEND}'...")
    stores_set(keys, values)

    # Exact-match Get. Assert the round-trip — a silent empty result would mean
    # the write never landed.
    got = stores_get([[1.0, 0.0, 0.0]])
    assert got["values"] == ["pos-x"], f"Get round-trip failed: {got}"
    print(f"  Get [1,0,0] -> {got['values'][0]}")

    # KNN search. Query along +X: expect pos-x (sim +1), the two orthogonal
    # vectors (sim 0), then neg-x (sim -1), nearest-first.
    print("\nFinding nearest neighbours of [1, 0, 0]:")
    result = find_when_ready([1.0, 0.0, 0.0], topk=4, expect=4)
    assert len(result["keys"]) == 4, f"expected 4 results, got {result}"
    assert result["values"][0] == "pos-x", f"nearest should be pos-x: {result}"
    # Cosine: identical direction ~ +1.0, opposite ~ -1.0.
    assert result["similarities"][0] > 0.99, result["similarities"]
    assert result["similarities"][-1] < -0.99, result["similarities"]
    for value, sim in zip(result["values"], result["similarities"]):
        print(f"  {value:>6}  sim={sim:+.3f}")

    # Delete one vector; confirm it's gone (Get omits it).
    print("\nDeleting [1, 0, 0]...")
    stores_delete([[1.0, 0.0, 0.0]])
    after = stores_get([[1.0, 0.0, 0.0]])
    assert after["keys"] == [], f"expected empty after delete, got {after}"
    print("  confirmed removed")

    print("\nDone. Vectors persist in Valkey across a LocalAI restart.")


if __name__ == "__main__":
    try:
        main()
    except requests.exceptions.ConnectionError:
        sys.exit(
            f"Could not reach LocalAI at {BASE_URL}.\n"
            "Is the server running and reachable? See 01-getting-started.md."
        )
    except requests.exceptions.HTTPError as exc:
        # A 500 here usually means the valkey-store backend can't reach Valkey.
        sys.exit(f"LocalAI returned an error: {exc}\nIs Valkey running and is the backend registered?")
    finally:
        SESSION.close()
