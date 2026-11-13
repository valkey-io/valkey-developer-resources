# llm-d Serving with Valkey

Put [llm-d](https://llm-d.ai)'s router in front of two vLLM servers and use a
single Valkey server (one standalone node) for three things:

- **Prefix-cache index:** Track which server has the prompt prefix cached, so
  follow-up requests go to a server that can start answering sooner.
- **Shared KV cache:** Store the model's computed attention state through
  LMCache. When a conversation moves to another server, that server can reuse
  the work instead of processing the whole prompt again.
- **Batch queue and per-user quotas:** Hold background jobs until they can run,
  and limit how many jobs each user has admitted within a time window.

The notebook follows one scenario: a contract-review assistant on two vLLM
servers. Reviewers chat about long lease documents, and an analyst runs batch
questions over the same leases. With two servers and nothing coordinating them,
a reviewer's follow-up can land on the server that doesn't have the
conversation, the server that has it can be busy while the other one idles, and
the analyst's batch competes with the reviewers for the same servers. The
router and Valkey handle each of these.

The first two roles work together. A server answers fastest when the prompt
prefix is already in its own memory, so the router sends each request to that
server when it can. When it can't, for example because that server is busy, the
other server loads the prefix from Valkey. That is slower than a local hit, but
several times faster than recomputing the prompt. Keeping the index in Valkey
rather than in the router's memory is about durability, not speed: the index
survives a router restart.

llm-d is an open-source, Kubernetes-native stack for distributed LLM inference
that runs model servers such as vLLM and SGLang. Its router chooses a server
based on what it already has cached and how busy it is.

**Why CPU here?** This recipe runs on CPU so readers can try it locally without
GPU hardware. llm-d is validated in production on GPUs and TPUs and also
supports CPU; its
[upstream routing guide](https://github.com/llm-d/llm-d/tree/v1.0.0/guides/precise-prefix-cache-routing)
defaults to NVIDIA GPUs. The three Valkey roles are useful in either setup.
This Compose stack and the timings shown here were tested only on CPU. A GPU
version would need an appropriate vLLM image, GPU device configuration, and
router load settings calibrated for that hardware.

This recipe builds on the [KV caching recipe](../kv-caching/), which shares one
KV cache between two vLLM servers through Valkey. You don't need to run that
recipe first: this stack starts its own copy of those servers. Here, llm-d's
router (Envoy plus its Endpoint Picker) runs without Kubernetes, and llm-d's
batch processor sends admitted jobs through the same router.

## What you'll have working at the end

A seven-container stack and a notebook that walks through it on CPU. You'll
measure the three ways a server can get a reviewer's first token (recompute,
load from Valkey, local hit); see the router send every follow-up back to the
server holding the conversation, compared with random routing; fill one server
with long jobs and watch the router move a conversation to the other server,
which loads it from Valkey; restart the router with its index in memory and
then in Valkey, and see that only the Valkey index still finds the warm
conversations; and submit the analyst's batch jobs from Python into
llm-d-async's Valkey queue, with a per-user rate limit holding some of them
back.

## How it works

The notebook drives seven containers (defined in
[`docker-compose.yml`](docker-compose.yml)):

![Architecture of the stack. A chat client sends requests to Envoy on localhost:8080, which asks the EPP (Endpoint Picker) which vLLM replica to use and forwards the request to vllm-a or vllm-b. Both replicas publish KV events over ZMQ to the EPP, which keeps its prefix-cache index in Valkey database 1. The replicas exchange KV chunks with the LMCache server, which stores them in Valkey database 0. Batch jobs submitted from Python go into a Valkey sorted set with per-user quota keys; llm-d-async admits them, sends them through Envoy like chat requests, and writes results to a Valkey list. A legend colours the three Valkey roles: index blue, KV cache green, queue and quotas orange.](images/02-architecture.svg)

| File | What it configures |
| --- | --- |
| [`epp/precise-valkey.yaml`](epp/precise-valkey.yaml) | Default router config: precise prefix-cache routing, index in Valkey database 1, load settings retuned for CPU |
| [`epp/precise-memory.yaml`](epp/precise-memory.yaml) | The same router config with the index in the router's memory (no `redisConfig`), for the notebook's restart comparison |
| [`epp/random.yaml`](epp/random.yaml) | Baseline router config: random pick |
| [`epp/endpoints.yaml`](epp/endpoints.yaml) | The two replicas the router may pick (file discovery instead of Kubernetes) |
| [`envoy/envoy.yaml`](envoy/envoy.yaml) | Envoy config from llm-d's no-Kubernetes guide (Apache-2.0) |
| [`async/transport-config.json`](async/transport-config.json) | llm-d-async's queue, result list and quota gate in Valkey; jobs sent to Envoy |

The router index has a Valkey database of its own (`redis://valkey:6379/1`).
When a replica restarts, the router forgets that replica's entries by scanning
its whole database and reading each key as a hash. In a database shared with
LMCache's string keys that scan fails with `WRONGTYPE` and leaves stale entries
behind, so the index lives in database 1. The notebook's "Notes on the router
index" explains this in more detail.

`EPP_STRATEGY` selects the router config the EPP loads: `precise-valkey`
(default), `precise-memory` or `random`. The notebook switches between them
itself.

## Prerequisites

- **A container runtime with Compose.** Tested with:
  - macOS on Apple silicon (arm64): Colima (Docker Engine 29.5), and Podman 6.1
    (`podman compose`, with Docker Compose 5.7 as its provider);
  - Windows on x86-64, under WSL2: Docker Engine 29.9 installed in Ubuntu, and
    Podman 6.1 for Windows. See [Running on Windows](#running-on-windows).
    In one of three notebook runs on Podman for Windows, the busy-server
    section failed with Envoy's `upstream connect error ... connection
    termination`. No container restarted and the logs showed nothing. Running
    the notebook again on the same stack passed. If you see it, re-run the
    notebook (or that section); it doesn't mean your setup is wrong.

  Not tested: Docker Desktop, Rancher Desktop, and Linux hosts outside WSL2.
- **Memory.** Give the container runtime 10 GiB (10240 MiB). On Apple silicon
  the measured minimum is 8.5 GiB; on x86-64 only 10 GiB was tested. See
  [Memory requirements](#memory-requirements) and
  [Running on a smaller machine](#running-on-a-smaller-machine).
- **CPU.** Tested with 8 cores; the typical timings quoted in the notebook
  were measured on an 8-CPU, 16 GiB Colima VM on an Apple M4 Pro.
- **[uv](https://docs.astral.sh/uv/)** for Python dependency management:

  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```

  (or `brew install uv`). `uv` provides the Python version this notebook needs
  (3.12).
- **Disk.** On arm64 the first start downloads about 2.3 GiB: the images (about
  1 GiB), the model (about 1 GiB), and the packages the LMCache containers
  install at startup (about 0.4 GiB). Unpacked and installed, that takes about
  10 GB of disk. On x86-64 the images are about 0.85 GiB larger, mostly the vLLM
  CPU image (from the image manifests), and the stack took about 11 GB of disk
  in WSL2.

  On either architecture, if you have run the KV caching recipe, its vLLM and
  Valkey images are reused; the router, Envoy and llm-d-async images and a
  second copy of the model are new.
- **Free ports** on localhost: 6379 (Valkey), 8001 and 8002 (replicas), 8080
  (router), 9090 (router metrics), 9091 (llm-d-async metrics). The container
  names and ports overlap with the KV caching recipe, so stop that stack first
  (`docker compose down` in `../kv-caching`).
- **CPU dtype (optional).** As in the KV caching recipe, the replicas run in
  float16; `export VLLM_DTYPE=bfloat16` before starting the stack if your CPU
  has BF16 instructions (see the
  [KV caching recipe's prerequisites](../kv-caching/README.md#prerequisites)).

### Memory requirements

The lowest memory setting at which every cold run passed was **8.5 GiB**,
measured on an 8-CPU Colima VM on Apple silicon (arm64), which reports 8.2 GiB
at that setting. A run passed if the notebook ran end to end, the live tests
passed twice in a row, and every service still answered afterwards. Two runs at
8.5 GiB and one at 9 GiB passed. At 8 GiB the kernel killed vllm-a's engine
during the live tests.

Peak memory per container, measured with `docker stats` every few seconds
during startup and one full notebook run. The arm64 numbers come from a
15.6 GiB Colima VM on an Apple M4 Pro. The x86-64 numbers come from WSL2 with
10 GiB (Docker Engine in Ubuntu) on an 8-vCPU Intel Xeon 6975P-C:

| Container | arm64 peak | x86-64 peak |
| --- | --- | --- |
| vllm-a | 3.8 GiB | 3.7 GiB |
| vllm-b | 3.7 GiB | 4.1 GiB |
| lmcache-server | 0.6 GiB | 0.8 GiB |
| valkey | 0.4 GiB | 0.3 GiB |
| envoy, epp, async-processor | under 0.03 GiB each | under 0.1 GiB each |
| **all containers (sampled together)** | **7.4 GiB** | **8.2 GiB** |

The x86-64 column and the 8.5 GiB minimum were measured with an earlier
version of the notebook, before the router-restart comparison was added. On
arm64 the current notebook peaked at the same total, 7.4 GiB.

Valkey grows by about 0.4 GiB each time you run the notebook, because LMCache
keeps every 3 MiB KV chunk (no TTL in this demo) until you run
`docker compose down`. The 10 GiB recommendation leaves room for that, so you
can run the notebook again without restarting the stack.

On x86-64 the containers peaked about 0.8 GiB higher than on arm64. Every run
there passed at 10 GiB, which the runtime reports as 9.7 GiB. The minimum on
x86-64 wasn't measured, so give the runtime the full 10 GiB.

## Getting started

**1. Clone the repository and switch to the recipe folder:**

```bash
git clone https://github.com/valkey-io/valkey-developer-resources.git
cd valkey-developer-resources/cookbooks/llm-d-serving
```

**2. Start the stack** with the script in this folder. It checks that the
container runtime exposes enough memory, runs `docker compose up -d --wait` (or
`podman compose` if Docker isn't available), then shows each service's status.
`compose up` blocks until the services with healthchecks are healthy. With the
images already downloaded, that took about 100 s on the Mac and about 200 s on
the x86-64 Windows host. A first start also downloads the images and the model;
it took three to four minutes in our tests, and about seven with Podman on
Windows:

```bash
./start.sh
```

If both Docker and Podman are installed, the script uses Docker. To use Podman,
run `CONTAINER_ENGINE=podman ./start.sh`. The notebook honours the same
variable.

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

## Running on a smaller machine

On Apple silicon the stack runs with 8.5 GiB for the container runtime, the
measured minimum (see [Memory requirements](#memory-requirements)). On a
16 GiB laptop that leaves room for the host. At that size:

- Stop anything else running in the container runtime first, including the
  KV caching recipe's stack.
- Run `docker compose down` and then `docker compose up -d --wait` before each
  new notebook run. Valkey keeps every KV chunk until the stack is taken down,
  so it grows by about 0.4 GiB per run.

Both replicas have to run at once, because routing between them is what this
recipe shows, so there is no one-replica mode like the KV caching recipe's.
Lowering `--kv-cache-memory-bytes` doesn't help much either: it is only 96 MiB
per replica, and the model and runtime take the rest (about 3 GiB per replica).

## Running on Windows

Tested on Windows Server 2025 (x86-64, 8 vCPU) with WSL2 and Ubuntu. Run
everything from the WSL2 shell, the notebook included. The Valkey GLIDE Python
client that the notebook uses publishes no Windows packages, so `uv sync` in a
Windows shell tries to build it from source and fails without a Rust toolchain.

- **Container runtime.** Install Docker Engine inside the WSL2 distribution, or
  use Podman for Windows, whose machine runs as a WSL2 distribution of its own.
  With Podman, install the distribution's `podman` package and Docker Compose
  (for example Docker's `docker-compose-plugin` package) in your distribution,
  and point the client at the machine's socket before running `./start.sh`:

  ```bash
  export CONTAINER_HOST=unix:///mnt/wsl/podman-sockets/podman-machine-default/podman-user.sock
  ```

- **Memory.** WSL2 sets one memory limit for all distributions, Podman's
  machine included, so `podman machine set --memory` has no effect there. Put
  this in `%UserProfile%\.wslconfig`, then run `wsl --shutdown`:

  ```ini
  [wsl2]
  memory=10GB
  ```

  With that setting the runtime reports 9.7 GiB.
- **Where to clone.** Clone inside the WSL2 file system, for example under
  `~`. A clone under `/mnt/c` works too, but `uv sync` took 137 s there in our
  test. A clone made with Git for Windows also works: `.gitattributes` keeps
  `start.sh` on LF line endings, and the other files work with CRLF.
- **Use one side throughout.** Start the stack and run the notebook from the
  same shell. Compose records the paths it mounted, so a stack started from
  Windows paths and then changed from WSL paths makes Compose recreate
  containers, which Podman refuses while other containers depend on them. For
  the same reason, don't share one `.venv` between Windows and WSL2.

## Troubleshooting

**`error mounting ... not a directory` when the stack starts, on Colima.**
Colima shares only your home directory with its VM by default. In a clone
outside it, for example under `/tmp`, the containers see empty paths where the
config files should be. Clone under your home directory, or add the path to
Colima's `mounts` setting.

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
replica's old entries stay in database 1. The notebook's "Notes on the router
index" section explains this. To clear them, restart that replica again while the
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
| [`epp/`](epp/) | Router configs (precise-valkey, precise-memory, random) and the endpoint list |
| [`images/`](images/) | The notebook's and this README's diagrams (SVG); `render.sh` regenerates the two drawn with Mermaid from `images/src/`, and the others are hand-written SVG |
| [`envoy/envoy.yaml`](envoy/envoy.yaml) | Envoy config, from llm-d's no-Kubernetes guide |
| [`async/`](async/) | llm-d-async's transport config and the dummy kubeconfig it needs off-cluster |
| [`pyproject.toml`](pyproject.toml), [`uv.lock`](uv.lock) | Pinned Python dependencies for the notebook and tests |
| [`start.sh`](start.sh) | Memory check, then `compose up -d --wait` and the services' status |
| [`helpers.py`](helpers.py) | Helpers the notebook and tests share: metrics scraping, Valkey waits, the sample lease, and the batch-job submitter (with llm-d-async's Lua script) |
| [`test_llm_d_serving.py`](test_llm_d_serving.py) | Tests: config and compose wiring always; routing, KV reuse, the batch queue and per-user quotas when the stack is up |
| [`.ci-structural-only`](.ci-structural-only) | Tells CI to skip notebook execution; its first line says why |

## Running the tests

The config and wiring tests run without the stack. The live tests drive the
router, the replicas, the batch queue and per-user quotas, and run only when
the stack is up with the default router config:

```bash
docker compose up -d --wait
uv run pytest
```
