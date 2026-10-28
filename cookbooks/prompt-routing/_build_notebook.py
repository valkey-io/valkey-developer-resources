#!/usr/bin/env python3
"""Generate the prompt-routing recipe notebook (Go kernel, shell-out design).

The notebook runs on the gophernotes (Go) kernel. Rather than interpreting
llm-d's indexer library in-kernel — gophernotes' gomacro interpreter can't load
a dependency tree that large as Go plugins — each step shells out to the
compiled program in ./cmd/prompt-routing via os/exec. The program is llm-d's real
indexer code, compiled normally, so what runs is exactly what a reader runs with
`go run`.

Each cell sets cmd.Dir to $PWD (the recipe directory, which is nbconvert's
working directory) so `go run` finds the module.
"""
import nbformat as nbf

nb = nbf.v4.new_notebook()
md = lambda s: nbf.v4.new_markdown_cell(s)
code = lambda s: nbf.v4.new_code_cell(s)

# A helper cell defines run(step) once; later cells call it.
HELPER = '''import (
    "fmt"
    "os"
    "os/exec"
)

// run executes one step of the compiled prompt-routing program and prints its
// output. The program is llm-d's real indexer code; os/exec runs it as a normal
// binary. cmd.Dir is the recipe directory (nbconvert's working directory),
// so `go run` resolves the module (deps are pinned in go.mod/go.sum).
func run(step string) {
    cmd := exec.Command("go", "run", "./cmd/prompt-routing", step)
    cmd.Dir = os.Getenv("PWD")
    out, err := cmd.CombinedOutput()
    fmt.Print(string(out))
    if err != nil {
        panic(err)
    }
}'''

cells = [
    md("""# Prompt routing with llm-d and Valkey

> Run llm-d's KV-cache routing index on Valkey and see how it answers the router's "who already holds this conversation?" question that prompt routing relies on.

**Difficulty:** Intermediate · Go · ~15 min

**Who is this for:** Engineers running or evaluating llm-d who want to see how Valkey backs the router's cache-aware routing decisions across replicas.

llm-d puts a router in front of several model servers. When a request arrives,
the router's Endpoint Picker tries to send the prompt to a server that already
holds its KV cache, so the server reuses that work instead of recomputing it.
Making that choice well is prompt routing, and it rests on an index: a map from
KV-cache block keys to the servers that cached those blocks.

This notebook is about that index, the piece prompt routing is built on. By
default each router replica keeps the index in its own memory, so replicas don't
share what they know. Point the index at Valkey and the map becomes one shared
store, where every replica reads and writes the same index and agrees on which
server holds each conversation.

It drives llm-d's real indexer library
([`llm-d-kv-cache`](https://github.com/llm-d/llm-d-kv-cache)) against Valkey, so
the keys it writes are exactly what a live router stores. It exercises the index
backend directly — no model servers, tokenizer, or GPUs — so it runs anywhere
Valkey does. The router's live routing decisions sit on top of this index and are
out of scope here (see the final section)."""),

    md("""## How to run this notebook

Start Valkey first, from this directory:

```bash
docker compose up -d --wait
```

> ⚠️ **Security:** These examples use no authentication or TLS for simplicity.
> For any non-localhost deployment, enable authentication and TLS.
> See the [Valkey security documentation](https://valkey.io/topics/security/).

This notebook uses the Go (gophernotes) kernel. Each step runs the compiled
program in `cmd/prompt-routing` against Valkey; the first run compiles the
dependency tree, which takes a moment. Run the code cells top to bottom."""),

    md("""## Setup

Define a small helper that runs one step of the compiled program and prints its
output. The program reads `VALKEY_HOST` / `VALKEY_PORT` (set by CI) and falls
back to `127.0.0.1:6379`."""),
    code(HELPER),

    md("""## A server records the blocks it cached

A conversation's prompt is split into fixed-size token blocks. Each block has a
stable hash that depends on its content and every block before it, so a shared
prefix produces a shared run of block hashes.

Say server `vllm-a` has just served this conversation, so it now holds all three
blocks. In llm-d the server reports this over a KV-cache event stream; the
`record` step writes the same block → pod entries into the shared index."""),
    code('run("record")'),

    md("""## The router looks up who holds the conversation

A follow-up request on the same conversation arrives. The `lookup` step is the
router's "who holds this prefix?" query: it looks the conversation's block keys
up in the index to find which server already holds the KV cache, so it can route
there instead of recomputing it.

This runs as a separate process from the one that recorded the blocks — yet it
sees them, because the index lives in Valkey, not in one process's memory."""),
    code('run("lookup")'),

    md("""## The cached prefix is a chain

The scorer prefers the server holding the longest cached *prefix*. The prefix is
a chain: it counts only up to the first block a server is missing. The `evict`
step removes the first block from `vllm-a` (as if under memory pressure); the
chain then breaks at the front, so the cached-prefix length the router can rely
on drops to zero."""),
    code('run("evict")'),

    md("""## It's a shared index

Every step above ran as its own process, and each one saw the previous step's
writes — because the index is in Valkey, not an in-process map. That is exactly
what lets a fleet of router replicas agree on which server holds each
conversation, which the in-memory backend cannot do across replicas.

You can read the index yourself from a shell:

```bash
docker compose exec valkey valkey-cli keys '*'
```

You'll see one hash per cached block (its fields are the servers holding it) and
the `engine:<hash>` sorted sets that chain engine blocks to request blocks.

## What this shows, and what it doesn't

This notebook is about the routing index itself — the shared state in Valkey. It
uses llm-d's released indexer code, so the index mechanics are real: the
block-to-server map, the prefix chain, and the shared-across-replicas property.

It does not stand up the full routing-and-serving path: model servers emitting
KV-cache events, the router tokenizing live prompts and scoring real traffic, or
the first-token-latency win that cache-aware routing produces end to end. That
needs GPU model servers and is out of scope for this notebook. The recipe's
optional [GPU benchmark](benchmark/) runs the full path as plain containers, with
no Kubernetes, and measures it. For a Kubernetes deployment, see llm-d's
[precise prefix-cache routing guide](https://github.com/llm-d/llm-d/tree/main/guides/precise-prefix-cache-routing)."""),
]

nb["cells"] = cells
nb["metadata"] = {
    "kernelspec": {"display_name": "Go", "language": "go", "name": "gophernotes"},
    "language_info": {"name": "go"},
}

with open("prompt-routing-with-valkey.ipynb", "w") as f:
    nbf.write(nb, f)
print("wrote prompt-routing-with-valkey.ipynb with", len(cells), "cells")
