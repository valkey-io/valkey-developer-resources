# vLLM Semantic Router + Valkey Go client

This sample calls a running vLLM Semantic Router over its OpenAI-compatible HTTP API. Semantic Router owns the
Valkey cache implementation; this Go program never creates an index or sends storage commands directly.

## Prerequisites

- Go 1.24+
- Docker or Podman
- Python 3.10–3.12
- A Hugging Face access token if the embedding model download is gated
- A running OpenAI-compatible upstream model configured as `demo-model`

## Setup

Start local Valkey with the Search module, bound only to localhost:

```bash
docker run -d --name valkey-search -p 127.0.0.1:6379:6379 valkey/valkey-bundle:9.1.2
```

Install and validate the released Router version:

```bash
python -m pip install "vllm-sr==0.3.0"
vllm-sr validate
```

Update `upstream-model` in `config.yaml` to point to your model, then start the Router:

```bash
HF_TOKEN=hf_your_token vllm-sr serve --config config.yaml
```

The supplied `host.docker.internal` Valkey host works with Docker Desktop. On native Linux, replace it with your
container runtime's host-gateway address before starting the Router.

## Run

```bash
export SEMANTIC_ROUTER_URL=http://localhost:8888
export SEMANTIC_ROUTER_MODEL=demo-model
go run .
```

Expected result:

```text
first request cache hit: false
second request cache hit: true
router response: ...
```

The second result is the framework-level proof: vLLM Semantic Router sets `x-vsr-cache-hit: true`. Its startup logs
also show the configured Valkey backend and index initialization.

## Tests

```bash
go test -v ./...
```

The deterministic tests validate client input, HTTP response handling, and the released Valkey configuration. To run
the real Router cache assertion after starting the service, provide both variables:

```bash
SEMANTIC_ROUTER_URL=http://localhost:8888 SEMANTIC_ROUTER_MODEL=demo-model go test -v ./...
```

The CI job validates this configuration with `vllm-sr==0.3.0` and runs the Go test suite. It does not start the full
Router because the released runtime downloads large model assets; the opt-in test above is the end-to-end check.

## Teardown

```bash
vllm-sr stop
docker rm -f valkey-search
```
