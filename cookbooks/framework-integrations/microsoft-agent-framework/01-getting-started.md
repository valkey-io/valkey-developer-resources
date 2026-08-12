# Microsoft Agent Framework Getting Started: Chat History with Valkey

> Build a small .NET chat-history store that keeps messages in chronological order in a Valkey List.

**Beginner** · .NET · ~15 min

**Who is this for:** .NET developers learning how an agent conversation can use Valkey for durable, bounded chat history.

The Microsoft Agent Framework integration introduced in [PR #5542](https://github.com/microsoft/agent-framework/pull/5542) uses a List per conversation. The
runnable sample calls Valkey through GLIDE directly, making the List operations and stored data contract easy to inspect alongside the framework integration.

## Prerequisites

- Docker or Podman
- .NET 8 SDK or later
- The cookbook's `sample/` dependency file, including stable `Valkey.Glide` 1.1.0
- A terminal with `curl` or another Valkey client for optional inspection

## Step 1: Start Valkey

Start a local, localhost-only Valkey Bundle. The image includes the modules used by the wider cookbook track.

```bash
docker run -d --name valkey-agent-framework \
  -p 127.0.0.1:6379:6379 \
  valkey/valkey-bundle:9.1.0
```

**Note:** Substitute `podman` for `docker` if that is your container runtime; the arguments are the same.

> ⚠️ **Security:** This example uses no authentication or TLS and binds Valkey to localhost for simplicity. For any non-localhost deployment, enable authentication and TLS. See the [Valkey security documentation](https://valkey.io/topics/security/).

## Step 2: Create a conversation

Choose a conversation identifier that is stable for the lifetime of the chat. The framework-shaped model used by the sample contains a role and message content; the stored value is JSON.

```text
conversationId = "demo-42"
key = "chat_history:" + conversationId
message = { "role": "user", "content": "How do I retry a stream?" }
```

The exact C# DTOs and GLIDE calls are in `sample/`. The snippet above is intentionally pseudocode: it shows the data contract without asserting a framework or client method signature.

## Step 3: Append messages

Append each JSON message to the right side of the List. `RPUSH` preserves arrival order, so the oldest message is at index zero and the newest is at the end.

```text
RPUSH chat_history:demo-42 {"role":"user","content":"How do I retry a stream?"}
RPUSH chat_history:demo-42 {"role":"assistant","content":"Persist each chunk and resume after the last ID."}
```

For a bounded context window, trim after appending. `LTRIM key -N -1` retains the newest `N` entries. A retry of the same append is not automatically
idempotent; use an application message ID or a deduplication policy if a caller may retry after an uncertain network result.

## Step 4: Read and delete history

Read the complete chronological List with `LRANGE key 0 -1`. Decode each JSON value into the framework-shaped message type before passing it to the agent.
`LLEN` reports the current number of messages, and `DEL` removes the conversation when it expires or is explicitly cleared.

```text
messages = LRANGE chat_history:demo-42 0 -1
count = LLEN chat_history:demo-42
DEL chat_history:demo-42
```

The sample test checks append, chronological range, length, trim behavior, and deletion against a live Valkey instance.

## How It Works

| Component                       | Role                                                            |
| ------------------------------- | --------------------------------------------------------------- |
| Microsoft Agent Framework       | Produces and consumes framework-shaped chat messages.           |
| `chat_history:<conversationId>` | Stable key pattern for one conversation's List.                 |
| Valkey List                     | Stores JSON messages in chronological order.                    |
| Valkey GLIDE 1.1.0              | Stable .NET client used by the independent runnable validation. |

The framework API and the storage pattern are related but distinct: the framework owns message semantics, while Valkey owns the List operations. The direct GLIDE
sample makes the wire-level behavior visible while keeping the example focused on the storage contract.

## Configuration Reference

| Field                | Required | Default           | Description                                                                    |
| -------------------- | -------- | ----------------- | ------------------------------------------------------------------------------ |
| `VALKEY_HOST`        | —        | `127.0.0.1`       | Host for the local Valkey server.                                              |
| `VALKEY_PORT`        | —        | `6379`            | Port for the local Valkey server.                                              |
| `CONVERSATION_ID`    | —        | Generated demo ID | Identifier appended to `chat_history:`; the sample also accepts this variable. |
| `CHAT_HISTORY_LIMIT` | —        | `20`              | Maximum number of newest messages retained when trimming is enabled.           |

## Run and inspect

From the sample directory, follow its README to restore dependencies, run the test, and execute the demonstration. To inspect the List manually:

```bash
docker exec valkey-agent-framework valkey-cli LRANGE chat_history:<conversationId> 0 -1
```

When finished, remove the local container:

```bash
docker rm -f valkey-agent-framework
```

---

[← Track README](README.md) | [Next → Resumable streaming](02-resumable-streaming.md)
