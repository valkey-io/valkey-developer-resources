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
- **Memory.** Give your container runtime about **9 GiB** for the default
  two-replica walkthrough, or about **5.5 GiB** to run every step with one
  replica at a time (see
  [Running on a smaller machine](#running-on-a-smaller-machine)).
  See [Memory requirements](#memory-requirements) for the measured numbers.
- **Python 3.12** for the notebook client.
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

Run these once, from a terminal, in this directory
(`cookbooks/kv-caching/`).

**1. Clone the repository and switch to the notebook folder:**

```bash
git clone https://github.com/valkey-io/valkey-samples.git
cd valkey-samples/cookbooks/kv-caching
```

**2. Start the stack** (Valkey, the LMCache server, and both vLLM replicas).
This checks that the runtime exposes enough memory first, then blocks until every
container is healthy:

```bash
if docker info >/dev/null 2>&1; then
  rt=docker; mem_bytes="$(docker info --format '{{.MemTotal}}')"
else
  rt=podman; mem_bytes="$(podman info --format '{{.Host.MemTotal}}' 2>/dev/null)"
fi
case "$mem_bytes" in
  ''|*[!0-9]*)
    echo "Could not read the container runtime's memory from 'docker info' or 'podman info'. Is the runtime running?" ;;
  *)
    if [ "$mem_bytes" -lt 9126805504 ]; then
      echo "This two-replica example needs about 9 GiB of container-runtime memory (this check allows a little under). Increase the memory limit and retry, or see 'Running on a smaller machine'."
    else
      "$rt" compose up -d --wait
      "$rt" compose ps -a
    fi ;;
esac
```

The check accepts 8.5 GiB (9126805504 bytes), a little under the recommended
9 GiB, because a VM reports slightly less than its configured size. It reads
Docker's `{{.MemTotal}}` or, if Docker is not running, Podman's
`{{.Host.MemTotal}}`, and starts the stack with the same runtime. If your
`podman compose` uses podman-compose, which has no `--wait`, run
`podman compose up -d` instead and wait until `podman ps` shows every
container `healthy`.
`MemTotal` is the memory of the Docker Desktop or Podman machine VM. On native
Linux there is no VM, so it reports the host's total RAM and the check only
tells you the machine is big enough, not that the memory is free.

Both `vllm-a` and `vllm-b` must be `Up` and `healthy`. The first run takes a few
minutes while Docker pulls the image, the containers install pinned packages, and
the model downloads; later runs reuse the cached image layers and model volume.

**3. Create the notebook environment and kernel:**

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m ipykernel install --user --name kv-caching-valkey
```

**4. Open the notebook and run it:**

```bash
.venv/bin/jupyter lab kv-caching-with-valkey.ipynb
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
ever resident, so it fits the one-replica figure in Prerequisites.

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

## What's in this directory

| File | Purpose |
| --- | --- |
| [`kv-caching-with-valkey.ipynb`](kv-caching-with-valkey.ipynb) | The cookbook — run this |
| [`docker-compose.yml`](docker-compose.yml) | Starts Valkey, the LMCache server, and two vLLM replicas |
| [`lmcache_config.yaml`](lmcache_config.yaml) | Documents the Valkey L2 adapter spec — the line that makes Valkey the LMCache backend |
| [`requirements.txt`](requirements.txt) | Pinned Python dependencies for the notebook's client |
| [`test_lmcache_valkey.py`](test_lmcache_valkey.py) | Tests: config + compose wiring always; live cache-hit signals when the stack is up |

## Running the tests

The config and compose-wiring tests run without the stack. The live tests
exercise the cache-hit signals and run only when the stack is up:

```bash
docker compose up -d --wait
.venv/bin/python -m pytest test_lmcache_valkey.py -v
```
