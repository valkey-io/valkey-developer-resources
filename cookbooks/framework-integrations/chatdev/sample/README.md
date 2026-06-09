# ChatDev + Valkey — Sample Code

Runnable sample demonstrating ValkeyMemory's store/retrieve API.

## Prerequisites

1. **Valkey** running with the Search module:
   ```bash
   docker run -d --name valkey -p 127.0.0.1:6379:6379 valkey/valkey-bundle:latest
   ```

2. **ChatDev** installed with Valkey support:
   ```bash
   git clone https://github.com/OpenBMB/ChatDev.git
   cd ChatDev
   pip install -e ".[valkey]"
   ```

3. **Environment variables**:
   ```bash
   export API_KEY="sk-..."          # OpenAI API key (for embeddings)
   export BASE_URL="https://api.openai.com/v1"
   ```

## Running

Run from the **ChatDev project root** (where `runtime/` is importable):

```bash
python path/to/quick_start.py
```

## Files

| File | Description |
|------|-------------|
| `quick_start.py` | Store and retrieve memories using ValkeyMemory (requires embedding API key) |
| `requirements.txt` | Python dependencies (installed automatically via `pip install -e ".[valkey]"`) |
