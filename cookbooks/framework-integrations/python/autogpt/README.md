# AutoGPT with Valkey

> Run and operate the Valkey cluster that AutoGPT's platform uses for caching, distributed locking, rate limiting and agent-output streaming.

[AutoGPT](https://github.com/Significant-Gravitas/AutoGPT) is an open-source platform for building and running continuous AI agents, developed by the Significant-Gravitas project. Its backend depends on a Valkey-compatible engine for caching, distributed locking, rate limiting, spend and usage counters, session metadata, pending-message buffers, and the server-sent-event streams that carry agent output to the browser.

Valkey is the engine inside AutoGPT's [single-container distribution](https://github.com/Significant-Gravitas/AutoGPT/tree/dev/autogpt_platform/single-container), which starts three `valkey-server` processes and forms them into a cluster before the backend boots. This series reproduces that topology on its own, so you can exercise, verify and operate the coordination layer without running the whole platform — and without an LLM API key.

The platform always connects with a cluster client, so **a single standalone node will not serve it.** Every guide here uses a three-shard cluster for that reason.

## Cookbooks

| # | Cookbook | Description | Tags |
| --- | --- | --- | --- |
| 01 | <nobr>[Getting Started](01-getting-started.md)</nobr> | Start the three-shard cluster AutoGPT expects, connect with valkey-glide, and verify the coordination layer end to end | Beginner, ~10 min, Python |
| 02 | <nobr>[Coordination Patterns](02-coordination-patterns.md)</nobr> | Sharded pub/sub for agent output, a single-flight lock around an execution step, and a fixed-window rate counter — with the hash-tag rule they all depend on | Intermediate, ~20 min, Python |
| 03 | <nobr>[Production](03-production.md)</nobr> | Authentication, TLS, announced shard addresses, timeouts and retries, and what happens when memory fills | Advanced, ~25 min, Python |

## Runnable sample

[`sample/`](sample/) contains a Compose file that reproduces AutoGPT's cluster topology and a `main.py` that asserts all three coordination patterns work against it. See [`sample/README.md`](sample/README.md).

## Compatibility

Tested against `valkey/valkey-bundle:8.1.9` and `valkey/valkey-bundle:9.1.2`. The platform's commands imply a floor of Valkey 7.2-equivalent cluster semantics (sharded pub/sub, `EXPIRE … NX`); no modules are used.

## Upstream status

The Valkey-based single-container distribution is merged into AutoGPT's `dev` integration branch: [PR #13758](https://github.com/Significant-Gravitas/AutoGPT/pull/13758) added it, and [PR #13994](https://github.com/Significant-Gravitas/AutoGPT/pull/13994) published its images. It has not yet reached the `master` release branch or a tagged release — the most recent at the time of writing is `autogpt-platform-beta-v0.7.0` — so check out `dev` to use it.

Nothing in this series depends on that distribution, though. The Compose file in [`sample/`](sample/) reproduces its cluster topology independently, and the patterns in 02 and the settings in 03 apply to any AutoGPT deployment, single-container or not.
