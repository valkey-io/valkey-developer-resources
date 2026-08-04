# Stagehand Python + Valkey

> 3 cookbooks for using Valkey as a persistent cache backend for the Stagehand Python SDK's act and agent action replay.

[Stagehand](https://github.com/browserbase/stagehand) is an open-source browser automation framework built by [Browserbase](https://www.browserbase.com/).
Valkey support is implemented in [browserbase/stagehand#2264](https://github.com/browserbase/stagehand/pull/2264) (core server) and
[browserbase/stagehand-python#346](https://github.com/browserbase/stagehand-python/pull/346) (this SDK), both open but not yet merged — this cookbook
installs from the forks that implement them until they release upstream (see [01 - Getting Started](01-getting-started.md)).

## Cookbooks

| # | Cookbook | Description | Tags |
| --- | --- | --- | --- |
| 01 | <nobr>[Getting Started](01-getting-started.md)</nobr> | Connect the Stagehand Python SDK to Valkey and run a cached browser action. | Beginner, ~15 min, Python |
| 02 | <nobr>[Cache Categories and TTL](02-cache-categories-and-ttl.md)</nobr> | Control cache namespacing, key prefixes, and expiration. | Intermediate, ~15 min, Python |
| 03 | <nobr>[Production Configuration](03-production-configuration.md)</nobr> | Configure TLS, authentication, and environment-based setup for production. | Intermediate, ~15 min, Python |
