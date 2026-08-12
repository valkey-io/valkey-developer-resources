# Microsoft Agent Framework and Valkey in Production

> Apply provider-neutral security, retention, monitoring, and tuning practices to chat-history Lists and agent-response Streams.

**Advanced** · Provider-neutral · ~25 min

**Who is this for:** Operators and platform engineers taking the cookbook's Valkey data patterns from local development into a managed or self-hosted deployment.

This page is provider-neutral. The same controls apply whether Valkey runs on your own infrastructure or through a managed Valkey-compatible service; consult
your provider's current networking and certificate documentation for deployment-specific steps.

## Prerequisites

- A Valkey 8.1.x or 9.x deployment with network policy controls
- A stable Valkey client and a secret-management system
- An operational owner for backups, retention, and incident response
- The data contracts from [01-getting-started.md](01-getting-started.md) and [02-resumable-streaming.md](02-resumable-streaming.md)

## Step 1: Protect the connection

Use TLS for every connection that leaves a trusted local process boundary. Validate the server certificate, keep the CA material in your secret or certificate
store, and rotate client credentials without putting them in source control or command history.

Enable authentication with the least privilege required by the application. Separate read/write identities from administrative identities where your deployment
supports ACLs. The application identity needs access only to its assigned `chat_history:*` and `agent_stream:*` keyspaces; do not grant unrestricted
administrative commands to the agent process.

## Step 2: Configure deployment-neutral connectivity

Keep endpoint, port, TLS, and credential settings outside the application binary. The exact configuration object differs by client, so use the official client
documentation for your language and construct the complete configuration before creating the client.

```text
endpoint = environment("VALKEY_ENDPOINT")
port = environment_or_default("VALKEY_PORT", 6379)
tls = true
credentials = secret_manager("valkey/application")
client = create_valkey_client(endpoint, port, tls, credentials)
```

This is pseudocode: it intentionally does not claim a particular GLIDE or framework method signature. Never log the credential, full connection URI, or TLS private-key material.

## Step 3: Set retention policies

Chat history and response streams have different retention needs. Decide how long each conversation remains available, then enforce that decision rather than relying on memory pressure.

| Data          | Key pattern                     | Retention control                                    | Cleanup action                                                                 |
| ------------- | ------------------------------- | ---------------------------------------------------- | ------------------------------------------------------------------------------ |
| Chat messages | `chat_history:<conversationId>` | Conversation TTL or lifecycle event                  | `DEL` after expiry/deletion request; trim to a context limit when appropriate. |
| Stream chunks | `agent_stream:<responseId>`     | Completion TTL plus optional approximate `MaxLength` | `DEL` after successful completion and replay window; trim while active.        |

An active stream may need a longer replay window than a completed stream. If a response must survive process failure, persist its completion state and continuation
ID with the same ownership and retention policy. Make cleanup idempotent: a repeated `DEL` is safe when a retry races with another cleanup worker.

## Step 4: Monitor correctness and capacity

Monitor both Valkey health and application-level progress. Useful signals include connection failures, TLS/authentication failures, command errors, key counts by
prefix, List lengths, Stream lengths, oldest retained Stream ID, cleanup age, and the number of responses waiting for completion.

Alert on trends that indicate a correctness problem: a stream whose `XLEN` grows without completion, a chat List that never trims, continuation IDs older than the
retained Stream range, or a rising count of keys past their intended retention. Sample a small number of command latencies for troubleshooting, but avoid
embedding unsourced latency or throughput targets in a cookbook.

## Step 5: Tune conservatively

Tune based on observed workload and failure recovery requirements:

- Set a chat-history limit that fits the agent's context policy, not an arbitrary global value.
- Set Stream `MaxLength` only when replay requirements permit approximate trimming.
- Choose connection pool and timeout settings from concurrency and recovery tests.
- Bound retries with exponential backoff and jitter; do not retry authentication or certificate failures indefinitely.
- Reserve memory for operational headroom and configure the deployment's eviction behavior deliberately.
- Test backup and restore procedures with both Lists and Streams, including a response that is mid-stream.

## Step 6: Operate safely

Use network segmentation and firewall rules to limit who can reach Valkey. Rotate credentials and certificates on a schedule, test revocation, and review ACL
changes. Keep Valkey and client versions in a documented compatibility matrix, and rehearse upgrades against a copy of representative keys.

For a partial batch or interrupted cleanup, earlier commands may already have succeeded. The sample performs history and stream deletion as independent best-effort
cleanup operations, so one deletion failure does not prevent an attempt of the other. Use idempotent operations, record cleanup progress, and retry only the
unfinished work. Do not infer that a failed multi-command request rolled back unless you deliberately used an atomic Valkey transaction and verified its error
semantics.

## Configuration Reference

| Field                    | Required            | Default                              | Description                                                          |
| ------------------------ | ------------------- | ------------------------------------ | -------------------------------------------------------------------- |
| Endpoint and port        | ✓                   | —                                    | Private Valkey endpoint and service port.                            |
| TLS                      | ✓ outside localhost | Disabled only for the local tutorial | Enable certificate validation for production traffic.                |
| Credentials              | ✓                   | —                                    | Secret-managed account with least-privilege ACLs.                    |
| Chat retention           | ✓                   | Application policy                   | TTL/lifecycle rule and optional List trim limit.                     |
| Stream retention         | ✓                   | Application policy                   | Completion TTL, replay window, and optional approximate `MaxLength`. |
| Connect/command timeouts | ✓                   | Client-specific                      | Set from tested failure and recovery behavior.                       |
| Retry policy             | ✓                   | Client-specific                      | Bounded retries with backoff and jitter.                             |
| Monitoring               | ✓                   | —                                    | Alerts for errors, growth, stale cleanup, and replay gaps.           |

---

[← Resumable streaming](02-resumable-streaming.md) | [Back to track README](README.md)
