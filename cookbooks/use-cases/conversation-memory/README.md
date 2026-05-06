# Conversation Memory + Valkey

> Scalable, low-latency session storage for chatbot and agent conversations. Six Valkey data structures - LIST, HASH, JSON, STRING, STREAM, and FT.SEARCH - powering a complete AI memory system.

## Cookbooks

| # | Cookbook | Description | Tags |
| --- | --- | --- | --- |
| 01 | <nobr>[Getting Started](01-getting-started.md)</nobr> | Connect with GLIDE, store chat messages in a LIST, retrieve conversation history, and auto-expire sessions with TTL. | Beginner, ~15 min, Python |
| 02 | <nobr>[Session Management](02-session-management.md)</nobr> | Track session metadata with HASH - user ID, model, token count, timestamps. List active sessions and implement sliding window history. | Intermediate, ~15 min, Python |
| 03 | <nobr>[Semantic Memory](03-semantic-memory.md)</nobr> | Store conversation embeddings with JSON.SET and search by meaning with FT.SEARCH KNN. Find relevant past context across all sessions. | Intermediate, ~20 min, Python |
| 04 | <nobr>[Semantic Caching](04-semantic-caching.md)</nobr> | Cache LLM responses by meaning, not exact match. Skip expensive API calls when a similar question was already answered. | Advanced, ~20 min, Python |
| 05 | <nobr>[Agent State & Tool Results](05-agent-state.md)</nobr> | Checkpoint agent reasoning with HASH, log tool calls to STREAM, and resume multi-step workflows after interruption. | Advanced, ~25 min, Python |

