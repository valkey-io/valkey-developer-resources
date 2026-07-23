# Getting Started with Langflow and Valkey

> Build a persistent memory chatbot in Langflow using Valkey Chat Memory —
> no additional modules required.

**Beginner** · Python · ~15 min

**Who is this for:** Developers and AI practitioners who want to use Langflow's
visual workflow builder with Valkey as a persistent chat memory backend.
You should be comfortable running Docker containers and navigating a web UI.

## Prerequisites

| Tool | Version | Purpose |
| --- | --- | --- |
| Docker | 20.10+ | Run Valkey server |
| Python | 3.10–3.13 | Run Langflow |
| uv | 0.4+ | Install Langflow (recommended) |

> **Security:** Never expose Valkey to the public internet without authentication.
> Use `requirepass` or ACLs in production. See the
> [Valkey security documentation](https://valkey.io/topics/security/).

## Step 1: Start Valkey

The Valkey Chat Memory component works with any Valkey server — no search module needed.

```bash
docker run -d --name valkey -p 6379:6379 valkey/valkey:8.1.1
```

Verify the server is running:

```bash
docker exec valkey valkey-cli PING
# PONG
```

## Step 2: Install and Start Langflow

Install Langflow with `uv` (recommended):

```bash
uv pip install langflow
```

Start the server:

```bash
langflow run
```

Langflow opens at `http://127.0.0.1:7860`. The Valkey bundle components are included
by default when you install the full `langflow` package.

## Step 3: Create a Memory Chatbot Flow

1. Click **New Flow** → **Blank Flow**.
2. From the sidebar, drag these components onto the canvas:
   - **Chat Input** (under Input/Output)
   - **Prompt** (under Prompts)
   - **OpenAI** model (under Models) — or any LLM of your choice
   - **Chat Output** (under Input/Output)
   - **Valkey Chat Memory** (under Bundles → Valkey)
   - **Message History** (under Core)

3. Connect the components:
   - **Chat Input** → **Prompt** (input)
   - **Prompt** → **OpenAI** (input)
   - **OpenAI** → **Chat Output** (input)
   - **Valkey Chat Memory** → **Message History** (memory input)
   - **Message History** → **Prompt** (memory variable)

4. Configure the **Prompt** component with a template that includes `{memory}`:

```text
You are a helpful assistant.

Previous conversation:
{memory}

User: {input}
Assistant:
```

## Step 4: Configure Valkey Chat Memory

Select the **Valkey Chat Memory** component and set its parameters:

| Parameter | Value | Notes |
| --- | --- | --- |
| Hostname | `localhost` | Or your Valkey host |
| Port | `6379` | Default Valkey port |
| Database | `0` | Database number |
| Session ID | `user-session-1` | Unique per conversation |
| Key prefix | `langflow:` | Optional namespace |

Leave **Username** and **Password** empty for local development.

## Step 5: Test the Flow

1. Click **Playground** in the top-right corner.
2. Send a message: "My name is Alice."
3. Send a follow-up: "What's my name?"
4. The assistant should recall your name from the Valkey-backed memory.

Verify the data in Valkey:

```bash
docker exec valkey valkey-cli KEYS "langflow:*"
# 1) "langflow:user-session-1"
```

## Step 6: Inspect Stored Messages

View the stored chat history:

```bash
docker exec valkey valkey-cli LRANGE "langflow:user-session-1" 0 -1
```

Each message is stored as a JSON object with role, content, and timestamp.

## How It Works

Under the hood, the Valkey Chat Memory component uses LangChain's
`RedisChatMessageHistory` class (wire-compatible with Valkey).
Messages are stored in a Redis List keyed by `{prefix}{session_id}`.

```text
┌─────────────┐     ┌──────────────────┐     ┌─────────────┐
│ Chat Input  │────▶│  Message History  │────▶│   Prompt    │
└─────────────┘     │  (reads memory)   │     └──────┬──────┘
                    └────────┬─────────┘            │
                             │                      ▼
                    ┌────────┴─────────┐     ┌─────────────┐
                    │ Valkey Chat      │     │  LLM Model  │
                    │ Memory           │     └──────┬──────┘
                    │ (stores msgs)    │            │
                    └──────────────────┘            ▼
                                              ┌─────────────┐
                                              │ Chat Output │
                                              └─────────────┘
```

## Configuration Reference

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| host | String | `localhost` | Valkey server hostname |
| port | Integer | `6379` | Valkey server port |
| database | Integer | `0` | Valkey database number |
| username | String | _(empty)_ | Authentication username |
| password | SecretString | _(empty)_ | Authentication password |
| key_prefix | String | _(empty)_ | Prefix for all keys |
| session_id | String | _(required)_ | Unique session identifier |

## Troubleshooting

**"Connection refused" error:**
Ensure Valkey is running and accessible from the Langflow process.
If Langflow runs inside Docker, use `host.docker.internal` instead of `localhost`.

**Messages not persisting between restarts:**
Check that the Session ID is consistent across flow runs.
Langflow generates a new session ID per Playground session by default.

---

| | |
| --- | --- |
| [↑ README](README.md) | [Vector Store RAG →](02-vector-store-rag.md) |
