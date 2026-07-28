# TestContainers Python + Valkey

> Spin up disposable Valkey instances in Python tests — no shared server, no state leaks, no manual cleanup.

**Who is this for:** Python developers who want reliable integration tests against Valkey without maintaining a shared test server or worrying about port conflicts between parallel test runs.

## Prerequisites

- Docker or Podman (container runtime)
- Python 3.9 or newer

## Cookbooks

| # | Cookbook | Description | Tags |
| --- | --- | --- | --- |
| 01 | [Getting Started](01-getting-started.md) | Launch a Valkey container, connect with valkey-glide, run basic operations. | Beginner, ~5 min, Python |
| 02 | [Integration Testing](02-integration-testing.md) | Pytest patterns: fixtures, parallel safety, password auth, bundle image. | Intermediate, ~10 min, Python |

## Affiliation Disclosure

[Testcontainers](https://testcontainers.com/) is an open-source project (Apache-2.0 licensed)
maintained by [AtomicJar](https://www.atomicjar.com/) (a Docker company).
The Valkey module was contributed by the community.

---

[01 - Getting Started →](01-getting-started.md)
