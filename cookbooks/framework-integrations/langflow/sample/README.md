# Langflow + Valkey Sample

Scripts and tests for the [Langflow + Valkey cookbook](../README.md).

## Quick Start

```bash
# Start Valkey and Langflow
docker compose up -d

# Wait for services to be ready
docker compose exec valkey valkey-cli PING

# Install Python dependencies
uv pip install -e ".[test]"
```

## Project Structure

```text
sample/
├── docker-compose.yml      # Valkey + Langflow services
├── pyproject.toml           # Python project config
├── scripts/
│   ├── query_flow.py        # Run a flow via API
│   ├── ingest_file.py       # Upload and ingest a document
│   └── health_check.py     # Check service health
├── flows/
│   └── (exported flow JSON files)
└── tests/
    ├── conftest.py          # Shared fixtures
    └── test_valkey_connection.py
```

## Running Tests

```bash
# Run all tests (requires running Valkey)
pytest

# Run only integration tests
pytest -m integration
```

## Environment Variables

| Variable | Default | Description |
| --- | --- | --- |
| `LANGFLOW_BASE_URL` | `http://127.0.0.1:7860` | Langflow server URL |
| `LANGFLOW_API_KEY` | — | API key for authentication |
| `LANGFLOW_FLOW_ID` | — | Flow UUID to execute |
| `VALKEY_HOST` | `localhost` | Valkey server hostname |
| `VALKEY_PORT` | `6379` | Valkey server port |
