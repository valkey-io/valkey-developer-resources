# Microsoft Agent Framework with Valkey

> Learn the Valkey data structures used by Microsoft Agent Framework for chat history and resumable stream buffers.

Microsoft Agent Framework is a Microsoft project. This cookbook documents its released Valkey integration and includes a runnable .NET sample using the official
Valkey GLIDE client.

## Cookbooks

| #   | Cookbook                                                      | Description                                                                       | Tags                                |
| --- | ------------------------------------------------------------- | --------------------------------------------------------------------------------- | ----------------------------------- |
| 01  | <nobr>[Getting started](01-getting-started.md)</nobr>         | Store and retrieve chronological conversation messages with Valkey Lists.         | Beginner, ~15 min, .NET             |
| 02  | <nobr>[Resumable streaming](02-resumable-streaming.md)</nobr> | Append streamed response chunks to a Valkey Stream and resume after reconnecting. | Intermediate, ~20 min, .NET         |
| 03  | <nobr>[Production](03-production.md)</nobr>                   | Apply TLS, authentication, retention, monitoring, and operational controls.       | Advanced, ~25 min, Provider-neutral |

## Integration provenance

- [Microsoft Agent Framework PR #5542](https://github.com/microsoft/agent-framework/pull/5542) is merged. It defines the stable chat-history Valkey contract used here: a
  `chat_history:<conversationId>` List containing JSON messages in chronological order.
- [Microsoft Agent Framework PR #5576](https://github.com/microsoft/agent-framework/pull/5576) adds the Valkey-backed response stream buffer and replay behavior
  described in cookbook 02.
- `Valkey.Glide` 1.1.0 is the client used by the runnable .NET sample to demonstrate the Valkey operations underlying the integration.

## Navigation

- Start with [Getting started](01-getting-started.md), then continue to [Resumable streaming](02-resumable-streaming.md) and [Production](03-production.md).
