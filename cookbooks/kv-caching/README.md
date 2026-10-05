# Building a KV Cache for vLLM with Valkey

Serve an LLM behind two vLLM instances that share one KV cache in Valkey, and
watch a prompt prefix that one instance computes get reused by the other instead
of being recomputed.

When an LLM answers a prompt it first computes attention key/value (KV) tensors
for every input token — the prefill step. That work is thrown away after
each request, so whenever a later request shares a prefix with an earlier one
(a multi-turn chat, a shared system prompt, a reused RAG passage), prefill
recomputes the same KV from scratch. Caching that KV and reloading it skips the
recompute: you pay for prefill once and reuse it.

[LMCache](https://github.com/LMCache/LMCache) is the KV-cache layer that plugs
into vLLM. It can store KV in local memory, on disk, or in a remote backend; this
cookbook runs a standalone LMCache server backed by **Valkey**. vLLM's own
built-in prefix cache only covers what a single engine holds and is not shared
with other engines — so use Valkey when several vLLM instances should share a cache.

## What you'll have working at the end

A running four-container stack — Valkey, a standalone LMCache server, and two
vLLM replicas — and a notebook that walks a multi-turn chat through it. You'll
see a cold request store its KV in Valkey, a warm request read that KV back
(faster, no re-prefill), and a **second replica reuse the first replica's cached
prefix** — cross-instance reuse an in-process cache can't do. The whole thing
runs on CPU.

## How it works

The notebook drives four containers (defined in
[`docker-compose.yml`](docker-compose.yml)):

```
  valkey          one shared KV-cache store (LMCache's L2 backend)
  lmcache-server  standalone LMCache server: L1 in its own memory, L2 -> Valkey
  vllm-a          vLLM replica A, KV connector pointed at the LMCache server
  vllm-b          vLLM replica B, same connector, same LMCache server

  How a KV chunk flows on CPU:

  vLLM (prefill)  ->  LMCacheMPConnector  ->  lmcache-server (L1)  ->  Valkey (L2)
```

The CPU build has no in-worker KV connector, so both replicas hand their KV to
the standalone LMCache server over the multi-process connector. The server writes
through to Valkey (its L2 backend), which is what makes one replica's KV visible
to the other.

## Prerequisites

- **A container runtime with Compose** (Docker Compose or compatible).
- **Memory.** Give your container runtime **8 GiB (8192 MiB)** for the default
  two-replica walkthrough, or about **5.5 GiB** to run every step with one
  replica at a time (see
  [Running on a smaller machine](#running-on-a-smaller-machine)). Count in
  MiB: a Podman machine with 8 GB in decimal units (7629 MiB) reports less
  than the 7.5 GiB the check below needs. Check with `podman machine list` and fix
  it with `podman machine stop`, `podman machine set --memory 8192`,
  `podman machine start`.
  See [Memory requirements](#memory-requirements) for the measured numbers.
- **CPU dtype (optional).** The replicas run in float16 so the stack also works
  on CPUs without BF16 instructions (for example Apple M1). If your CPU has them,
  run `export VLLM_DTYPE=bfloat16` in the terminal before you start the stack
  (every later `docker compose up` then picks it up). Memory is the same; on
  AWS Graviton4 the walkthrough runs several times faster (token generation
  about 15x), and on x86 with AMX prefill is about 25% faster (so the cache's
  relative saving looks smaller). To check your CPU, run
  `docker run --rm alpine grep -m1 -owE 'bf16|avx512_bf16|amx_bf16' /proc/cpuinfo`;
  if it prints nothing, keep float16.
- **[uv](https://docs.astral.sh/uv/)** for Python dependency management. Install
  it with the official installer:

  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```

  (or `brew install uv`, or see the uv docs for other platforms). `uv` provides
  the Python version this notebook needs (3.12), so you don't have to install
  Python yourself.
- **Disk.** The first run downloads about 3.5 GiB on amd64 (2.5 GiB on arm64):
  the vLLM CPU image (~1.7 GiB compressed on amd64, ~0.8 GiB on arm64), the
  Valkey image (~0.4 GiB), the model (~1 GiB), and the packages the three
  LMCache containers install at startup. Unpacked, the vLLM image takes ~7.5 GB
  on amd64 (~3.7 GB on arm64), so plan for about 11 GB of free disk (about 7 GB
  on arm64).

### Memory requirements

The lowest memory limit at which every cold run of the full walkthrough passed
(notebook, live tests, and a healthy stack afterwards), measured on Linux with
the containers under one hard memory limit and no swap. Docker, Podman and
nerdctl measured the same within 0.25 GiB:

| CPU | two replicas | one replica at a time | single replica |
| --- | --- | --- | --- |
| x86-64 | 6.75 GiB | 3.75 GiB | 3.75 GiB |
| arm64 (AWS Graviton) | 7.5 GiB | 4.5 GiB | 4.5 GiB |

Docker Desktop and Podman machine run the containers in a VM, which needs memory
of its own on top of these numbers, and Apple silicon was not measured
directly; the recommendations above add a margin for that to the larger arm64
figure. At steady state each vLLM replica uses about 3 GiB, the LMCache
server about 0.5 GiB, and Valkey about 25 MiB.

## Getting started

Run these once, from a terminal. Step 1 clones the repository; every later
command runs in the cookbook directory it switches to
(`cookbooks/kv-caching/`).

**1. Clone the repository and switch to the notebook folder:**

```bash
git clone https://github.com/valkey-io/valkey-developer-resources.git
cd valkey-developer-resources/cookbooks/kv-caching
```

**2. Start the stack** (Valkey, the LMCache server, and both vLLM replicas).
This checks that the runtime exposes enough memory first, then blocks until every
container is healthy:

```bash
rt=""; mem_bytes=""
for candidate in docker podman; do
  case "$(command -v "$candidate" 2>/dev/null)" in /*) ;; *) continue ;; esac
  mem_bytes="$("$candidate" info --format '{{.MemTotal}}' 2>/dev/null)" ||
    mem_bytes="$("$candidate" info --format '{{.Host.MemTotal}}' 2>/dev/null)"
  case "$mem_bytes" in
    ''|*[!0-9]*) mem_bytes="" ;;
    *) rt="$candidate"; break ;;
  esac
done
if [ -z "$rt" ]; then
  echo "Could not read the container runtime's memory from 'docker info' or 'podman info'. Is the runtime running?"
elif [ "$mem_bytes" -lt 8053063680 ]; then
  tenths=$(( mem_bytes * 10 / 1073741824 ))
  echo "Not enough memory: $rt reports $(( tenths / 10 )).$(( tenths % 10 )) GiB; the two-replica example needs 8 GiB (8192 MiB), which this check sees as at least 7.5 GiB. Raise the limit (Docker Desktop: Settings > Resources; Podman: podman machine stop, then podman machine set --memory 8192, then podman machine start) and retry, or run one replica at a time on about 5.5 GiB — see 'Running on a smaller machine'."
else
  "$rt" compose up -d --wait
  "$rt" compose ps -a
fi
```

> ⚠️ **Security:** These examples use no authentication or TLS for simplicity.
> For any non-localhost deployment, enable authentication and TLS.
> See the [Valkey security documentation](https://valkey.io/topics/security/).

The check accepts 7.5 GiB (8053063680 bytes), a little under the recommended
8 GiB, because a VM reports slightly less than its configured size. If the
runtime has less, it prints how much memory the runtime reports. It uses the
first of `docker` and `podman` that is installed and answers `info`, and starts
the stack with that same command. A `docker` command that is really Podman (the
`podman-docker` package) is read with Podman's `{{.Host.MemTotal}}`; a shell
alias such as `alias docker=podman` is skipped in favour of the real `podman`.
If your `podman compose` uses an older podman-compose without `--wait` (1.0.x,
for example the one Ubuntu 24.04 ships), run `podman compose up -d` instead and
wait until `podman ps` shows every container `healthy`.
`MemTotal` is the memory of the Docker Desktop or Podman machine VM. On native
Linux there is no VM, so it reports the host's total RAM and the check only
tells you the machine is big enough, not that the memory is free.

Both `vllm-a` and `vllm-b` must be `Up` and `healthy`. The first run takes a few
minutes while Docker pulls the image, the containers install pinned packages, and
the model downloads; later runs reuse the cached image layers and model volume.

**3. Create the notebook environment and kernel:**

`uv sync` reads `pyproject.toml` and `uv.lock`, creates `.venv`, and installs the
exact locked dependencies (fetching Python 3.12 if you don't already have it):

```bash
uv sync
uv run python -m ipykernel install --user --name kv-caching-valkey
```

**4. Open the notebook and run it:**

```bash
uv run jupyter lab kv-caching-with-valkey.ipynb
```

Select the `kv-caching-valkey` kernel, then run the cells top to bottom. Each
cell prints what to look for — key counts and Valkey `GET` calls — so you can
watch the cache fill and get reused.

**5. Tear down when you're done:**

```bash
docker compose down
```

## Running on a smaller machine

The default walkthrough keeps both vLLM replicas running at the same time,
which needs the most memory (see [Prerequisites](#prerequisites)). If your
container runtime has less, run the replicas one at a time: only one replica is
ever resident, so it fits in about 5.5 GiB (the one-replica figure in
[Prerequisites](#prerequisites); see [Memory requirements](#memory-requirements)
for the measured minimums).

### One replica at a time (every step, including cross-replica reuse)

Valkey and the LMCache server keep running the whole time, so the KV that
replica A wrote is still in Valkey when replica B starts. Replica B reading it
back also shows that the cache outlives the replica that computed it.

1. Start Valkey, the LMCache server, and replica A only:

   ```bash
   docker compose up -d --wait vllm-a
   ```

2. Run the notebook from the top and stop at
   **"A second replica hits the first replica's cache."**
3. Swap replica A for replica B, from a terminal in this directory:

   ```bash
   docker compose stop vllm-a
   docker compose up -d --wait --no-deps vllm-b
   ```

   Keep `--no-deps`: `vllm-b` normally waits for `vllm-a` to be healthy, so
   without it Compose would start replica A again. Replica B needs a minute or
   two to install LMCache, load the model, and warm up.
4. Run the remaining cells. Replica B's request reads replica A's KV from
   Valkey: the `GET` calls go up and `dbsize` stays the same.

With Podman, run the same commands with `podman compose`. If your
`podman compose` has no `--wait`, drop it and wait until `podman compose ps`
shows `vllm-b` as healthy.

### A single replica

If you only want the single-replica part of the demo, start replica A as in
step 1 and skip the one cell that calls `replica_b` (under
**"A second replica hits the first replica's cache"**). You still see a cold
turn store its KV in Valkey and a warm turn read it back.

## If the first request hangs or a replica dies

Each replica serves one short warm-up request before it reports healthy, so on
too little memory `docker compose up -d --wait` usually fails with a replica
`exited` or `unhealthy`. If it does succeed, a replica can still run out of
memory on its first notebook request: the kernel kills its engine process (an
out-of-memory kill) and the cell fails with a connection or server error; just
above that point the request can instead hang for minutes. To check:

```bash
docker compose ps -a
docker compose logs --tail 30 vllm-a vllm-b
docker stats --no-stream
```

A replica that is `Exited`, `unhealthy` or restarting, or log lines with
`EngineDeadError` or `died unexpectedly`, point to memory. With Podman use
`podman ps -a`, `podman logs --tail 30 vllm-a` and `podman stats --no-stream`.
The kernel log names the killed process: `sudo dmesg | grep -i 'killed process'`
on native Linux, or `podman machine ssh 'sudo dmesg' | grep -i 'killed process'`
for a Podman machine.

Give the container runtime more memory (see [Prerequisites](#prerequisites)) or
run the replicas one at a time (see
[Running on a smaller machine](#running-on-a-smaller-machine)), then recreate
the stack with `docker compose down` and `docker compose up -d --wait`.

## If you restart the LMCache server

The KV chunks live in Valkey, so they survive a restart of `lmcache-server`,
but the vLLM replicas do not reconnect to a restarted server: their requests
hang (until the client times out) while `docker compose ps` still shows them
`healthy`. Restart the replicas after the server:

```bash
docker compose restart lmcache-server
docker compose restart vllm-a vllm-b
```

A restarted replica reports healthy again within about half a minute on a fast
host (longer on a slow CPU), and its next request reads the prefixes cached
before the restart back from Valkey.

## What's in this directory

| File | Purpose |
| --- | --- |
| [`kv-caching-with-valkey.ipynb`](kv-caching-with-valkey.ipynb) | The cookbook — run this |
| [`docker-compose.yml`](docker-compose.yml) | Starts Valkey, the LMCache server, and two vLLM replicas |
| [`lmcache_config.yaml`](lmcache_config.yaml) | Documents the Valkey L2 adapter spec — the line that makes Valkey the LMCache backend |
| [`pyproject.toml`](pyproject.toml) | Project metadata and pinned Python dependencies for the notebook's client |
| [`uv.lock`](uv.lock) | Fully resolved dependency lock (`uv` generates it; commit it for reproducible installs) |
| [`test_lmcache_valkey.py`](test_lmcache_valkey.py) | Tests: config + compose wiring always; live cache-hit signals when the stack is up |

## Running the tests

The config and compose-wiring tests run without the stack. The live tests
exercise the cache-hit signals and run only when the stack is up:

```bash
docker compose up -d --wait
uv run pytest test_lmcache_valkey.py -v
```
