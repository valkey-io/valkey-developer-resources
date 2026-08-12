# Microsoft Agent Framework Valkey sample

This sample shows the Valkey data contracts used by Microsoft Agent Framework's
chat-history and resumable-streaming integrations, using only the stable
Valkey.Glide 1.1.0 package.

## Prerequisites

- .NET 8 SDK
- Docker Compose or Podman Compose
- No Microsoft Agent Framework package, model provider, or credentials

## Run it

    docker compose up -d
    dotnet run --project MicrosoftAgentFramework.Valkey.Sample.csproj
    docker compose down -v

The sample reads `VALKEY_HOST` (default `127.0.0.1`), `VALKEY_PORT` (default
`6379`), `VALKEY_REQUEST_TIMEOUT_MS` (default `5000`), `CONVERSATION_ID`,
`RESPONSE_ID`, `CHAT_HISTORY_LIMIT` (default `20`), `MAX_LENGTH` (default
`100`), and `CONTINUATION_ID`. Its `finally` block independently attempts
history deletion, stream deletion, and GLIDE connection closure. If cleanup
fails while application code is already failing, it reports the cleanup failure
to standard error and preserves the application exception. If only cleanup
fails, it throws an aggregate cleanup exception.

Expected output:

    History messages: 2
    Stream entries: 2; after continuation: 1

`chat_history:<conversationId>` is a list of camel-case JSON objects with
framework-shaped `role` and `content` fields. Appends preserve chronological
order; optional trimming keeps the newest messages. `agent_stream:<responseId>`
is a stream whose `content` field contains camel-case JSON with response
`content`. Full replay is `XRANGE agent_stream:<responseId> - +`; resuming
after an entry uses `XRANGE agent_stream:<responseId> (<last-id> +`, where the
opening parenthesis excludes the saved ID. Optional stream trimming is
approximate (`XTRIM MAXLEN ~`).

List push, list trim, stream append, and stream trim are separate commands and
therefore non-atomic. A failure can leave an earlier command applied. Each
operation is safe to retry for this sample: list appends and stream appends are
idempotent only when the caller supplies its own de-duplication policy;
otherwise retrying may duplicate data. Deletes are idempotent.

The sample validates role/content JSON before every write and validates data
loaded from Valkey before returning it to an agent.
