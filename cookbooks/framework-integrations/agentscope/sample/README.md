# AgentScope + Valkey Cookbook Sample

Runnable code for the [AgentScope + Valkey cookbook series](../README.md).

## Prerequisites

1. **Python 3.10+**
2. **Docker** (for Valkey)
3. **AWS credentials** with Bedrock access (for the RAG pipeline example only)

## Setup

```bash
# Start Valkey
docker run -d --name valkey -p 6379:6379 valkey/valkey-bundle:latest

# Install dependencies (ValkeyStore is not yet released — install from feature branch)
pip install "agentscope[valkey] @ git+https://github.com/MatthiasHowellYopp/agentscope.git@feat/valkey-vector-store"
pip install "valkey-glide>=2.1.0,<2.4.0"
pip install boto3
```

## Running

```bash
# 01 - Quick start (no API key needed, uses synthetic embeddings)
python quick_start.py

# 02 - RAG pipeline (requires AWS credentials with Bedrock access)
python rag_pipeline.py

# 03 - Production patterns (no API key needed)
python production_patterns.py
```

## Sample Scripts

| Script | Cookbook | Description |
|--------|---------|-------------|
| `quick_start.py` | [01 - Getting Started](../01-getting-started.md) | Connect, store embeddings, similarity search, delete |
| `rag_pipeline.py` | [02 - RAG Pipeline](../02-rag-pipeline.md) | Chunk text, embed with Bedrock Titan, retrieve context |
| `production_patterns.py` | [03 - Production](../03-production.md) | HNSW tuning, metadata filtering, batch ingestion |

## Troubleshooting

- **Connection refused**: Ensure Valkey is running on `localhost:6379`.
- **Module errors**: Use `valkey/valkey-bundle` (not plain `valkey/valkey`) — it includes the Search module.
- **ImportError for valkey-glide**: Run `pip install valkey-glide`. Note: `valkey-glide>=2.4.0` has a known packaging issue (`glide_shared` not bundled). Use `2.1.x`–`2.3.x` until resolved.
- **Bedrock errors**: Ensure AWS credentials are configured and you have access to Titan Embeddings v2 in us-east-1.
