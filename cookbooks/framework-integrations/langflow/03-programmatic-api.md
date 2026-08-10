# Programmatic API with Langflow and Valkey

> Run Langflow flows programmatically via the REST API — automate document
> ingestion, query flows with custom parameters, and integrate Valkey-backed
> AI workflows into your applications.

**Intermediate** · Python · ~15 min

**Who is this for:** Developers who have built Langflow flows (from the previous
cookbooks) and want to trigger them from code — for batch processing, integration
with existing applications, or CI/CD pipelines.
You should have completed the [Vector Store RAG](02-vector-store-rag.md) guide.

## Prerequisites

| Tool | Version | Purpose |
| --- | --- | --- |
| Docker | 20.10+ | Run Valkey |
| Langflow | 1.11+ | Running with a deployed flow |
| Python | 3.10–3.13 | Client scripts |
| requests | 2.28+ | HTTP client (or use httpx) |

> **Security:** Never expose Valkey to the public internet without authentication.
> Store API keys in environment variables, not in source code.
> See the [Valkey security documentation](https://valkey.io/topics/security/).

## Step 1: Get Your Flow ID and API Key

1. In Langflow, open your RAG flow from the previous cookbook.
2. Click **API** (top-right) → copy the **Flow ID** (UUID).
3. Go to **Settings** → **API Keys** → create a new key.

```bash
export LANGFLOW_API_KEY="your-api-key-here"
export LANGFLOW_FLOW_ID="your-flow-id-here"
export LANGFLOW_BASE_URL="http://127.0.0.1:7860"
```

## Step 2: Run a Flow with a Query

The simplest API call sends a text input to your flow and gets a response:

```python
import os
import requests

BASE_URL = os.environ["LANGFLOW_BASE_URL"]
FLOW_ID = os.environ["LANGFLOW_FLOW_ID"]
API_KEY = os.environ["LANGFLOW_API_KEY"]

response = requests.post(
    f"{BASE_URL}/api/v1/run/{FLOW_ID}",
    headers={
        "Content-Type": "application/json",
        "x-api-key": API_KEY,
    },
    json={
        "input_value": "What are the main topics in the document?",
        "output_type": "chat",
        "input_type": "chat",
    },
    timeout=120,
)
response.raise_for_status()

data = response.json()
message = data["outputs"][0]["outputs"][0]["results"]["message"]["data"]["text"]
print(f"Response: {message}")
```

## Step 3: Upload and Ingest a File

For the data ingestion flow, upload a file first, then trigger the flow:

```python
import os
import requests

BASE_URL = os.environ["LANGFLOW_BASE_URL"]
FLOW_ID = os.environ["LANGFLOW_FLOW_ID"]  # Ingestion flow ID
API_KEY = os.environ["LANGFLOW_API_KEY"]

# Step 1: Upload the file
with open("knowledge-base.pdf", "rb") as f:
    upload_response = requests.post(
        f"{BASE_URL}/api/v2/files/",
        headers={"x-api-key": API_KEY},
        files={"file": ("knowledge-base.pdf", f, "application/pdf")},
        timeout=60,
    )
upload_response.raise_for_status()
uploaded_path = upload_response.json()["path"]

# Step 2: Run the ingestion flow with the uploaded file
run_response = requests.post(
    f"{BASE_URL}/api/v1/run/{FLOW_ID}",
    headers={
        "Content-Type": "application/json",
        "x-api-key": API_KEY,
    },
    json={
        "input_value": "Ingest this document",
        "output_type": "chat",
        "input_type": "text",
        "tweaks": {
            "File-XXXXX": {  # Replace with your File component ID
                "path": uploaded_path,
            }
        },
    },
    timeout=300,
)
run_response.raise_for_status()
print(f"Ingestion complete: {run_response.json()}")
```

Find your component ID by clicking the component in Langflow and checking
the **ID** field in the component inspection panel.

## Step 4: Use Tweaks to Override Parameters

Tweaks let you override any component parameter at runtime — useful for
changing the Valkey connection, session ID, or search parameters:

```python
import os
import requests

BASE_URL = os.environ["LANGFLOW_BASE_URL"]
FLOW_ID = os.environ["LANGFLOW_FLOW_ID"]
API_KEY = os.environ["LANGFLOW_API_KEY"]

response = requests.post(
    f"{BASE_URL}/api/v1/run/{FLOW_ID}",
    headers={
        "Content-Type": "application/json",
        "x-api-key": API_KEY,
    },
    json={
        "input_value": "Tell me about deployment",
        "output_type": "chat",
        "input_type": "chat",
        "tweaks": {
            # Override Valkey connection for different environment
            "ValkeyVectorStore-XXXXX": {
                "valkey_server_url": "valkey://production-host:6379",
                "number_of_results": 8,
            },
            # Override memory session for user isolation
            "ValkeyChatMemory-XXXXX": {
                "session_id": "user-42",
                "host": "production-host",
            },
        },
    },
    timeout=120,
)
response.raise_for_status()
data = response.json()
message = data["outputs"][0]["outputs"][0]["results"]["message"]["data"]["text"]
print(f"Response: {message}")
```

## Step 5: Batch Processing

Process multiple queries against your Valkey-backed RAG flow:

```python
import os
import requests
from concurrent.futures import ThreadPoolExecutor

BASE_URL = os.environ["LANGFLOW_BASE_URL"]
FLOW_ID = os.environ["LANGFLOW_FLOW_ID"]
API_KEY = os.environ["LANGFLOW_API_KEY"]

questions = [
    "What is the architecture overview?",
    "How do I configure authentication?",
    "What are the performance requirements?",
    "Describe the deployment process.",
]


def query_flow(question: str) -> dict:
    """Send a single query to the Langflow flow."""
    response = requests.post(
        f"{BASE_URL}/api/v1/run/{FLOW_ID}",
        headers={
            "Content-Type": "application/json",
            "x-api-key": API_KEY,
        },
        json={
            "input_value": question,
            "output_type": "chat",
            "input_type": "chat",
        },
        timeout=120,
    )
    response.raise_for_status()
    data = response.json()
    answer = data["outputs"][0]["outputs"][0]["results"]["message"]["data"]["text"]
    return {"question": question, "answer": answer}


# Process queries concurrently (respect Langflow's concurrency limits)
with ThreadPoolExecutor(max_workers=3) as executor:
    results = list(executor.map(query_flow, questions))

for result in results:
    print(f"Q: {result['question']}")
    print(f"A: {result['answer']}\n")
```

## Step 6: Health Check and Monitoring

Check that your Langflow server and Valkey backend are both healthy:

```python
import os
import requests

BASE_URL = os.environ["LANGFLOW_BASE_URL"]
API_KEY = os.environ["LANGFLOW_API_KEY"]
VALKEY_HOST = os.environ.get("VALKEY_HOST", "localhost")
VALKEY_PORT = int(os.environ.get("VALKEY_PORT", "6379"))


def check_langflow() -> bool:
    """Verify Langflow API is responding."""
    try:
        resp = requests.get(
            f"{BASE_URL}/health",
            headers={"x-api-key": API_KEY},
            timeout=5,
        )
        return resp.status_code == 200
    except requests.ConnectionError:
        return False


def check_valkey() -> bool:
    """Verify Valkey is responding to PING."""
    import socket

    try:
        sock = socket.create_connection((VALKEY_HOST, VALKEY_PORT), timeout=2)
        sock.sendall(b"PING\r\n")
        response = sock.recv(64)
        sock.close()
        return b"PONG" in response
    except (socket.error, OSError):
        return False


print(f"Langflow: {'✓' if check_langflow() else '✗'}")
print(f"Valkey:   {'✓' if check_valkey() else '✗'}")
```

## How It Works

```text
┌──────────────┐     POST /api/v1/run/{flow_id}      ┌──────────────┐
│ Your App     │────────────────────────────────────▶│  Langflow    │
│ (Python)     │◀────────────────────────────────────│  Server      │
└──────────────┘     JSON response                   └──────┬───────┘
                                                            │
                                                            │ valkey://
                                                            ▼
                                                     ┌──────────────┐
                                                     │   Valkey     │
                                                     │ (memory +    │
                                                     │  vectors)    │
                                                     └──────────────┘
```

The Langflow API executes the entire flow graph server-side:

1. Your app sends a query to `/api/v1/run/{flow_id}`
2. Langflow executes each component in dependency order
3. The Valkey components read/write to the Valkey server
4. The final output is returned as JSON

## Configuration Reference

| Endpoint | Method | Description |
| --- | --- | --- |
| `/health` | GET | Server health check |
| `/api/v1/run/{flow_id}` | POST | Run a flow synchronously |
| `/api/v2/files/` | POST | Upload a file for processing |
| `/api/v1/workflows/{flow_id}` | POST | Run async (returns task ID) |

### Request Body Parameters

| Parameter | Type | Description |
| --- | --- | --- |
| input_value | String | The input text or query |
| input_type | String | `chat` or `text` |
| output_type | String | `chat` or `text` |
| tweaks | Object | Component parameter overrides |
| session_id | String | Session ID for stateful flows |

## Troubleshooting

**401 Unauthorized:**

Ensure your API key is valid. Regenerate it in Langflow Settings → API Keys.

**"Flow not found" (404):**

Verify the Flow ID. You can list flows with:

```bash
curl -s -H "x-api-key: $LANGFLOW_API_KEY" \
  "$LANGFLOW_BASE_URL/api/v1/flows" | python -m json.tool
```

**Timeout errors:**

Increase the timeout for large documents or complex flows.
For production, use the async workflow endpoint instead:

```python
# Async execution
response = requests.post(
    f"{BASE_URL}/api/v1/workflows/{FLOW_ID}",
    headers={
        "Content-Type": "application/json",
        "x-api-key": API_KEY,
    },
    json={
        "input_value": "Process this large document",
        "output_type": "chat",
        "input_type": "text",
    },
    timeout=10,
)
task_id = response.json()["task_id"]
# Poll for completion or use webhooks
```

**Valkey connection errors in production:**

Use tweaks to point to a different Valkey instance without modifying the flow:

```python
# In production, always load credentials from environment variables — never
# hardcode passwords or connection strings in source code.
tweaks = {
    "ValkeyVectorStore-XXXXX": {
        "valkey_server_url": f"valkeyss://{os.environ['VALKEY_USER']}:{os.environ['VALKEY_PASSWORD']}@prod-host:6379",
    }
}
```

---

| | |
| --- | --- |
| [← Vector Store RAG](02-vector-store-rag.md) | [↑ README](README.md) |
