# llm-d Serving with Valkey

Put [llm-d](https://llm-d.ai)'s router in front of two CPU vLLM servers and use
one Valkey for three things: the router's prefix-cache index, the KV cache the
servers share through LMCache, and the batch job queue with per-user quotas.

This recipe builds on the [KV caching recipe](../kv-caching/), which shares one
KV cache between two vLLM servers through Valkey. Here llm-d's router (Envoy
plus llm-d's Endpoint Picker, run without Kubernetes) decides which server gets
each request: it keeps an index of which server holds which prompt blocks, and
sends follow-up turns of a conversation to the server that already has them in
memory. When it has to send a conversation elsewhere, the other server loads it
from Valkey instead of recomputing it. llm-d's batch processor (llm-d-async)
queues jobs and enforces quotas in the same Valkey and sends the jobs through
the same router.

llm-d is a Cloud Native Computing Foundation (CNCF) sandbox project, founded by
Red Hat, Google Cloud, IBM Research, CoreWeave and NVIDIA. LMCache and vLLM are
independent open-source projects. Every component here is an unmodified
upstream image, pointed at Valkey by configuration.

## What you'll have working at the end

A seven-container stack and a notebook that walks through it on CPU. You'll
measure the three ways a server can get a conversation's first token (recompute,
load from Valkey, local hit); see the router send every follow-up back to the
server holding the conversation, compared with random routing; restart the
router and watch routing stay correct; fill one server with long jobs and watch
the router move a conversation to the other server, which loads it from Valkey;
and submit batch jobs from Python into llm-d-async's Valkey queue, with a
per-user rate limit holding some of them back.

## How it works

The notebook drives seven containers (defined in
[`docker-compose.yml`](docker-compose.yml)):

```text
  valkey           db 1: router index    db 0: LMCache KV chunks, batch queue, quotas
  lmcache-server   standalone LMCache server; L2 -> Valkey (from the KV caching recipe)
  vllm-a, vllm-b   CPU vLLM replicas; prefix cache on; publish KV events over ZMQ
  envoy            the router's front door on localhost:8080
  epp              llm-d Endpoint Picker: subscribes to KV events, keeps the index
                   in Valkey, picks a replica for every request
  async-processor  llm-d-async: pulls jobs from Valkey, applies quotas, sends them
                   through Envoy

  chat request -> envoy -> (epp picks) -> vllm-a | vllm-b <-> lmcache-server <-> valkey
  batch job -> valkey queue -> async-processor -> envoy -> ...
```

| File | What it configures |
| --- | --- |
| [`epp/precise-valkey.yaml`](epp/precise-valkey.yaml) | Default router config: precise prefix-cache routing, index in Valkey database 1, load settings retuned for CPU |
| [`epp/random.yaml`](epp/random.yaml) | Baseline router config: random pick |
| [`epp/endpoints.yaml`](epp/endpoints.yaml) | The two replicas the router may pick (file discovery instead of Kubernetes) |
| [`envoy/envoy.yaml`](envoy/envoy.yaml) | Envoy config from llm-d's no-Kubernetes guide (Apache-2.0) |
| [`async/transport-config.json`](async/transport-config.json) | llm-d-async's queue, result list and quota gate in Valkey; jobs sent to Envoy |

The router index has a Valkey database of its own (`redis://valkey:6379/1`).
When a replica restarts, the router forgets that replica's entries by scanning
its whole database and reading each key as a hash. In a database shared with
LMCache's string keys that scan fails with `WRONGTYPE` and leaves stale entries
behind, so the index lives in database 1. The notebook explains this in more
detail.

## Prerequisites

- **A container runtime with Compose** (Docker Compose or compatible). Tested
  with Colima (Docker Engine 29.5) on Apple silicon. The commands work the
  same with `podman compose`, but this recipe has not been run on Podman.
- **Memory.** Give the container runtime **10 GiB (10240 MiB)**. See
  [Memory requirements](#memory-requirements).
- **CPU.** 8 cores is comfortable; the typical timings quoted in the notebook
  were measured on an 8-CPU, 16 GiB Colima VM on an Apple M4 Pro.
- **[uv](https://docs.astral.sh/uv/)** for Python dependency management:

  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```

  (or `brew install uv`). `uv` provides the Python version this notebook needs
  (3.12).
- **Disk.** About 3 GiB to download on arm64 (more on amd64): the images from
  the KV caching recipe (vLLM CPU, Valkey), the router, Envoy and llm-d-async
  images (about 0.4 GiB unpacked together), the model (about 1 GiB), and the
  packages the LMCache containers install at startup. If you have run the KV
  caching recipe, only the router, Envoy and llm-d-async images and a second
  copy of the model are new.
- **Free ports** on localhost: 6379 (Valkey), 8001 and 8002 (replicas), 8080
  (router), 9090 (router metrics), 9091 (llm-d-async metrics). The container
  names and ports overlap with the KV caching recipe, so stop that stack first
  (`docker compose down` in `../kv-caching`).
- **CPU dtype (optional).** As in the KV caching recipe, the replicas run in
  float16; `export VLLM_DTYPE=bfloat16` before starting the stack if your CPU
  has BF16 instructions (see the
  [KV caching recipe's prerequisites](../kv-caching/README.md#prerequisites)).

### Memory requirements

Measured with `docker stats` every few seconds during startup and a full
notebook run, on an 8-CPU Colima VM with 15.6 GiB (arm64):

| Container | Peak |
| --- | --- |
| vllm-a | 3.5 GiB |
| vllm-b | 3.3 GiB |
| lmcache-server | 0.6 GiB |
| valkey | 0.3 GiB |
| envoy, epp, async-processor | under 0.03 GiB each |
| **all containers (sampled together)** | **7.4 GiB** |

Valkey grows by about 0.3 GiB each time you run the notebook, because LMCache
keeps every 3 MiB KV chunk (no TTL in this demo) until you run
`docker compose down`. The 10 GiB recommendation adds room for that and for the
VM itself. The lowest working limit was not measured; the
[KV caching recipe](../kv-caching/README.md#memory-requirements) measured 7.5 GiB
for its two replicas on arm64, and this stack needs a little more.

## Getting started

**1. Clone the repository and switch to the recipe folder:**

```bash
git clone https://github.com/valkey-io/valkey-developer-resources.git
cd valkey-developer-resources/cookbooks/llm-d-serving
```

**2. Start the stack.** This checks that the runtime exposes enough memory,
then blocks until the services with healthchecks are healthy (about two minutes
once the images are pulled):

```bash
rt=""; mem_bytes=""
for candidate in docker podman; do
  case "$(command -v "$candidate" 2>/dev/null)" in /*) ;; *) continue ;; esac
  mem_bytes="$("$candidate" info --format '{{.MemTotal}}' 2>/dev/null)" ||
    mem_bytes="$("$candidate" info --format '{{.Host.MemTotal}}' 2>/dev/null)"
  # A numeric test, not a case pattern with a negated bracket: pasted into an
  # interactive zsh or bash, that bracket's character starts history expansion.
  if [ -n "$mem_bytes" ] && [ "$mem_bytes" -ge 0 ] 2>/dev/null; then
    rt="$candidate"; break
  fi
  mem_bytes=""
done
if [ -z "$rt" ]; then
  echo "Could not read the container runtime's memory from 'docker info' or 'podman info'. Is the runtime running?"
elif [ "$mem_bytes" -lt 10200547328 ]; then
  tenths=$(( mem_bytes * 10 / 1073741824 ))
  echo "Not enough memory: $rt reports $(( tenths / 10 )).$(( tenths % 10 )) GiB; this recipe needs 10 GiB (10240 MiB), which this check sees as at least 9.5 GiB. Raise the limit (Docker Desktop: Settings > Resources; Podman: podman machine stop, then podman machine set --memory 10240, then podman machine start) and retry."
else
  "$rt" compose up -d --wait
  "$rt" compose ps -a
fi
```

> ⚠ **Security:** These examples use no authentication or TLS for simplicity.
> For any non-localhost deployment, enable authentication and TLS.
> See the [Valkey security documentation](https://valkey.io/topics/security/).

`valkey`, `lmcache-server`, `vllm-a` and `vllm-b` must be `healthy`. `envoy`,
`epp` and `async-processor` show only `Up`: their images are distroless (no
shell), so they have no healthcheck. The notebook's first cells wait until the
router answers.

**3. Create the notebook environment and kernel:**

```bash
uv sync
uv run python -m ipykernel install --user --name llm-d-serving-valkey
```

**4. Open the notebook and run it:**

```bash
uv run jupyter lab llm-d-serving-with-valkey.ipynb
```

Select the `llm-d-serving-valkey` kernel and run the cells top to bottom. Some
cells restart or reconfigure the router with `docker compose`, so start Jupyter
from this directory.

**5. Tear down when you're done:**

```bash
docker compose down
```

The model weights stay in the `hf-cache` volume for the next run
(`docker compose down -v` removes them).

## Troubleshooting

**The router returns errors or the first cell times out.** Check
`docker compose logs epp`. Right after startup the EPP needs a few seconds to
load its config and connect to the replicas' event streams. If it reports
`Failed to connect subscriber socket` for longer than a minute, a replica is
not reachable at the address in `epp/endpoints.yaml`.

**`Pool overlaps with other one on this address space` on `docker compose up`.**
The compose network uses the fixed subnet `172.16.89.0/24`, because the router's
file discovery needs each replica's literal address. If it clashes with another
network on your machine, change all of these together:

- the `subnet` under `networks.serving` in `docker-compose.yml`;
- every service's `ipv4_address` in `docker-compose.yml` (valkey,
  lmcache-server, vllm-a, vllm-b, envoy, async-processor);
- `POD_IP` for `vllm-a` and `vllm-b`, which must equal their `ipv4_address`;
- both `address` values in `epp/endpoints.yaml`.

The notebook reads the replica addresses from `epp/endpoints.yaml`, so it
follows automatically. `uv run pytest` checks that the addresses agree and sit
inside the subnet.

**A replica restarted and the router still sends it old conversations.** If the
router was running at the time, it should not: the router notices the replica's
event sequence restart on the replica's first new event and clears its entries
from database 1. If the router's URL points at database 0 (shared with LMCache),
this clear fails with `WRONGTYPE` in `docker compose logs epp`; keep the `/1`.
If the replica restarted while the router was down, a fresh router has no way
to tell, because it keeps the last sequence number only in memory, so the
replica's old entries stay in database 1. The notebook's "Restarting the router"
section explains this. To clear them, restart that replica again while the
router runs, or start from an empty index with `docker compose down` and `up`.

**You restarted the LMCache server.** As in the KV caching recipe, restart the
replicas too: `docker compose restart lmcache-server`, then
`docker compose restart vllm-a vllm-b` (see the
[KV caching recipe](../kv-caching/README.md#if-you-restart-the-lmcache-server)).

**A replica runs out of memory.** See the
[KV caching recipe's troubleshooting](../kv-caching/README.md#if-the-first-request-hangs-or-a-replica-dies);
the same checks apply.

## What's in this directory

| File | Purpose |
| --- | --- |
| [`llm-d-serving-with-valkey.ipynb`](llm-d-serving-with-valkey.ipynb) | The recipe: run this |
| [`docker-compose.yml`](docker-compose.yml) | Valkey, the LMCache server, two vLLM replicas, Envoy, the EPP and llm-d-async |
| [`epp/`](epp/) | Router configs (precise-valkey, random) and the endpoint list |
| [`envoy/envoy.yaml`](envoy/envoy.yaml) | Envoy config, from llm-d's no-Kubernetes guide |
| [`async/`](async/) | llm-d-async's transport config and the dummy kubeconfig it needs off-cluster |
| [`pyproject.toml`](pyproject.toml), [`uv.lock`](uv.lock) | Pinned Python dependencies for the notebook and tests |
| [`test_llm_d_serving.py`](test_llm_d_serving.py) | Tests: config and compose wiring always; routing, KV reuse and the batch queue when the stack is up |
| [`.ci-structural-only`](.ci-structural-only) | Tells CI to skip notebook execution (the stack does not fit a hosted runner) |

## Running the tests

The config and wiring tests run without the stack. The live tests drive the
router, the replicas and the batch queue, and run only when the stack is up with
the default router config:

```bash
docker compose up -d --wait
uv run pytest
```
