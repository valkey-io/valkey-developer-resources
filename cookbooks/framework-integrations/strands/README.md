# Strands + Valkey

> 3 cookbooks for using the `strands-valkey-session-manager` community package to back Strands agents with Valkey, persisting conversation history, session records, and agent state.

Strands Agents is an open-source agent SDK maintained by Amazon. This
cookbook uses its public session-manager interface with the community
`strands-valkey-session-manager` package.

## Cookbooks

| # | Cookbook | Description | Tags |
| --- | --- | --- | --- |
| 01 | <nobr>[Getting Started](01-getting-started.md)</nobr> | Install `strands-valkey-session-manager`, create a `ValkeySessionManager`, and wire it to a Strands agent. Persistent conversation history in under 15 minutes. | Beginner, ~15 min, Python |
| 02 | <nobr>[Managing Session Data](02-session-internals.md)</nobr> | Understand the key structure and shape of session, agent, and message objects. Use `list_messages(session_id, agent_id)` and other built-in API methods to inspect and manage session data. | Intermediate, ~15 min, Python |
| 03 | <nobr>[Managing Your Session Store](03-managing-your-session-store.md)</nobr> | Delete sessions on logout, query raw keys to inspect what's stored, and share a session across multiple agents in an orchestrator pattern. | Intermediate, ~15 min, Python |

## Sample

The [`sample/`](sample/README.md) uses a local Ollama model, so the session
persistence flow runs without provider credentials. Pull the configured model
before running the sample.
