# Cognee + Valkey Cookbook Sample

Runnable code for the [Cognee + Valkey cookbook series](../README.md).

## Prerequisites

1. **Python 3.11+**
2. **Docker** (for Valkey)
3. **AWS credentials** with Bedrock access (Claude 4.5 Sonnet + Titan Embeddings v2)

## Setup

```bash
# Start Valkey
docker run -d --name valkey -p 6379:6379 valkey/valkey-bundle:latest

# Install dependencies
pip install -r requirements.txt
```

## Running

```bash
# 01 - Quick start (requires AWS credentials with Bedrock access)
python quick_start.py

# 02 - Knowledge graph search types
python knowledge_graph.py

# 03 - Production patterns
python production_patterns.py
```

## Sample Scripts

| Script | Cookbook | Description |
|--------|---------|-------------|
| `quick_start.py` | [01 - Getting Started](../01-getting-started.md) | Configure Valkey adapter, add documents, cognify, search |
| `knowledge_graph.py` | [02 - Knowledge Graph](../02-knowledge-graph.md) | Multi-document relationships, search types comparison |
| `production_patterns.py` | [03 - Production](../03-production.md) | Error handling, batch operations, monitoring |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `AWS_REGION` | `us-east-1` | AWS region for Bedrock |
| `AWS_PROFILE` | (default) | AWS credentials profile |
| `VECTOR_DB_URL` | `valkey://localhost:6379` | Valkey connection URL |
| `LLM_MODEL` | `bedrock/us.anthropic.claude-sonnet-4-5-20250929-v1:0` | LLM model ID |
| `EMBEDDING_MODEL` | `bedrock/amazon.titan-embed-text-v2:0` | Embedding model ID |

## Troubleshooting

- **Connection refused**: Ensure Valkey is running on `localhost:6379`.
- **Module errors**: Use `valkey/valkey-bundle` (not plain `valkey/valkey`) — it includes the Search module.
- **Missing boto3**: Run `pip install boto3`.
- **Invalid model identifier**: Use the cross-region inference profile ID (e.g., `us.anthropic.claude-sonnet-4-5-20250929-v1:0`).
- **Bedrock access errors**: Ensure your AWS credentials have Bedrock model access enabled in your region.
