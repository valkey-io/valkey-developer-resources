# Strands +Valkey

> 3 cookbooks for using the official strands-valkey-session-manager community package to back Strands agents with Valkey - persisting conversation history, session metadata, and agent state.

## Cookbooks

| # | Cookbook | Description | Tags |
| --- | --- | --- | --- |
| 01 | <nobr>[Getting Started](01-getting-started.md)</nobr> | Install `strands-valkey-session-manager`, create a `ValkeySessionManager`, and wire it to a Strands agent. Persistent conversation history in under 15 minutes. | Beginner, ~15 min, Python |
| 02 | <nobr>[Managing Session Data](02-session-internals.md)</nobr> | Understand the key structure and shape of session, agent, and message objects. Use `list_messages()` and other built-in API methods to inspect and manage session data. | Intermediate, ~15 min, Python |
| 03 | <nobr>[Managing Your Session Store](03-managing-your-session-store.md)</nobr> | Delete sessions on logout, query raw keys to inspect what's stored, and share a session across multiple agents in an orchestrator pattern. | Intermediate, ~15 min, Python |

