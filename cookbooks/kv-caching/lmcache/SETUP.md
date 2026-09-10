# Setup

Run these once in a terminal from this directory, then open
[`kv-caching-with-valkey.ipynb`](kv-caching-with-valkey.ipynb), select the
`kv-caching-valkey` kernel, and run the cells.

## 1. Start the stack

Valkey, the LMCache server, and both vLLM replicas:

```bash
docker compose up -d --wait
```

`--wait` blocks until every container is healthy. The first run is slow. The
vLLM image is large, each replica loads the model on startup, and the LMCache
server installs its dependencies, so give it several minutes. Later runs reuse
the cached image and model weights.

The two-replica walkthrough needs about **16 GiB** of RAM. On a smaller machine
(about **10 GiB**), start a single replica instead and skip the cross-replica
step. The notebook's "Running on a smaller machine" section covers how.

## 2. Create the notebook environment and kernel

```bash
python3.12 -m venv .venv
```

```bash
.venv/bin/python -m pip install -r requirements.txt
```

```bash
.venv/bin/python -m ipykernel install --user --name kv-caching-valkey
```

## 3. Open the notebook

Open [`kv-caching-with-valkey.ipynb`](kv-caching-with-valkey.ipynb) and select
the `kv-caching-valkey` kernel (in VS Code, the kernel picker is at the top
right; you can also pick the `.venv` in this directory). If your editor keeps
prompting you to install `ipykernel`, you have the wrong environment selected.
Pick the `kv-caching-valkey` kernel instead of installing into whatever it
defaulted to.

Then run the code cells top to bottom.

## Teardown

```bash
docker compose down
```
