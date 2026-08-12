# Microsoft Agent Framework Resumable Streaming with Valkey

> Persist response chunks in a Valkey Stream so a disconnected .NET consumer can replay a standalone stream buffer after reconnecting.

**Intermediate** · .NET · ~20 min

**Who is this for:** .NET developers who need a reconnectable response-chunk buffer and want to understand its Valkey command contract.

The Microsoft Agent Framework Valkey integration stores one Stream per response, writes JSON-encoded chunks in a `content` field, and replays entries
exclusively after a continuation ID. The runnable .NET sample uses Valkey GLIDE 1.1.0 to demonstrate the Valkey operations behind that behavior.

## Prerequisites

- Docker or Podman
- .NET 8 SDK or later
- Stable `Valkey.Glide` 1.1.0 from the sample dependency file
- Familiarity with Valkey Streams and reconnect/retry logic

## Step 1: Start Valkey

```bash
docker run -d --name valkey-agent-framework \
  -p 127.0.0.1:6379:6379 \
  valkey/valkey-bundle:9.1.0
```

> **Note:** Substitute `podman` for `docker` if needed. This page follows the localhost-only setup from cookbook 01; production authentication and TLS guidance
> is in [03-production.md](03-production.md).

## Step 2: Create a response stream

Use the response identifier as part of the key: `agent_stream:<responseId>`. Each entry contains one `content` field whose value is JSON. The JSON can carry a
text delta and any application metadata needed to reconstruct the response.

```text
streamKey = "agent_stream:" + responseId
entry = { "content": JSON({ "content": "first chunk" }) }
XADD streamKey * content entry.content
```

The snippet describes the integration's Valkey data model. The sample contains the GLIDE calls and tests for the corresponding operations.

## Step 3: Replay the buffer from the beginning or after a continuation ID

For a new consumer, the integration accepts `0-0` as its full-replay sentinel and translates it to `-` before issuing the raw Valkey command
`XRANGE key - +`.

After a client has processed entry `lastSeenId`, request entries strictly after it with an exclusive start ID:

```text
XRANGE agent_stream:response-7 - +
XRANGE agent_stream:response-7 (lastSeenId +
```

The parenthesis before `lastSeenId` makes the range start exclusive. Use the GLIDE range option shown in the sample rather than copying this pseudocode as a
client method call. The important invariant is that the continuation entry itself is not delivered twice.

## Step 4: Append, trim, and acknowledge progress

The producer appends each chunk with `XADD`. If a maximum stream length is configured, approximate trimming may be requested so old entries are discarded as the
stream grows. Approximate trimming is a boundedness policy, not an exact count guarantee.

```text
XADD agent_stream:response-7 * content {"content":"next chunk"}
XTRIM agent_stream:response-7 MAXLEN ~ 1000
XLEN agent_stream:response-7
```

The integration's `MaxLength` option maps to this optional approximate trimming behavior. Do not treat the returned `XLEN` as a promise that the stream never exceeds the configured value at every instant.

## Step 5: Retry, reconnect, and clean up

Persist the last successfully processed entry ID with the consumer's job state. On timeout or reconnect, replay the buffer after that ID; if no continuation ID
exists, use the full-replay sentinel described in step 3. A producer retry can create duplicate chunks after an uncertain write, so consumers should make
reconstruction tolerant of duplicate application content or add an application-level chunk ID.

When the response is complete and no replay is required, remove it with `DEL`. `XLEN` is useful for monitoring and for deciding whether a response has accumulated unexpected data.

```text
XLEN agent_stream:response-7
DEL agent_stream:response-7
```

## How It Works

| Component                             | Role                                                |
| ------------------------------------- | --------------------------------------------------- |
| Microsoft Agent Framework integration | Provides the Valkey-backed response stream buffer.  |
| `agent_stream:<responseId>`           | One Valkey Stream per response.                     |
| `content` field                       | JSON-encoded response chunk in each Stream entry.   |
| Entry ID                              | Continuation cursor for exclusive replay.           |
| Valkey GLIDE 1.1.0                    | Client used by the runnable .NET sample.            |

Earlier entries may be trimmed when `MaxLength` is enabled. A reconnecting consumer must therefore retain a sensible completion policy: if its cursor is older than
the retained history, it may need to restart the response or obtain the missing content from another durable source.

## Configuration Reference

| Field             | Required | Default           | Description                                                                    |
| ----------------- | -------- | ----------------- | ------------------------------------------------------------------------------ |
| `VALKEY_HOST`     | —        | `127.0.0.1`       | Valkey host.                                                                   |
| `VALKEY_PORT`     | —        | `6379`            | Valkey port.                                                                   |
| `RESPONSE_ID`     | —        | Generated demo ID | Identifier appended to `agent_stream:`; the sample also accepts this variable. |
| `MAX_LENGTH`      | —        | `100`             | Optional approximate maximum length for trimming.                              |
| `CONTINUATION_ID` | —        | None              | Last processed entry ID; replay starts exclusively after it.                   |

## Run and inspect

Use the sample README for restore, test, and demonstration commands. Inspect a complete stream with:

```bash
docker exec valkey-agent-framework valkey-cli XRANGE agent_stream:<responseId> - +
```

Then clean up the local container as described in [01-getting-started.md](01-getting-started.md).

---

[← Getting started](01-getting-started.md) | [Next → Production](03-production.md)
