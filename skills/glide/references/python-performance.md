# Python Performance Optimization

Config templates: `../assets/python-config.py`

## AZ Affinity

```python
from glide import GlideClusterClient, GlideClusterClientConfiguration, NodeAddress, ReadFrom

config = GlideClusterClientConfiguration(
    addresses=[NodeAddress("cluster.endpoint.cache.amazonaws.com", 6379)],
    read_from=ReadFrom.AZ_AFFINITY,
    client_az="us-east-1a",
    request_timeout=500,
)
client = await GlideClusterClient.create(config)
```

## Throughput Tuning

```python
config = GlideClientConfiguration(
    addresses=[NodeAddress("localhost", 6379)],
    inflight_requests_limit=2000,  # Default: 1000
    request_timeout=500,
)
```

## Serverless / Lambda

```python
config = GlideClientConfiguration(
    addresses=[NodeAddress("localhost", 6379)],
    lazy_connect=True,  # Defer connection until first command
    request_timeout=500,
)
client = await GlideClient.create(config)
```

## Dedicated Blocking Client

```python
blocking_client = await GlideClient.create(GlideClientConfiguration(
    addresses=[NodeAddress("localhost", 6379)],
    request_timeout=30000,
    client_name="queue-worker",
))
item = await blocking_client.blpop(["queue"], 30)
```

## Hash vs JSON for Structured Data

## Context Manager Pattern

```python
# Async
async with await GlideClient.create(config) as client:
    result = await client.get("key")

# Sync
with GlideClient.create(config) as client:
    result = client.get("key")
```

## Monitoring

### OpenTelemetry

```python
from glide import OpenTelemetry, OpenTelemetryConfig, OpenTelemetryTracesConfig, OpenTelemetryMetricsConfig

OpenTelemetry.init(OpenTelemetryConfig(
    traces=OpenTelemetryTracesConfig(
        endpoint="http://localhost:4318/v1/traces",
        sample_percentage=1,  # 1% for production
    ),
    metrics=OpenTelemetryMetricsConfig(
        endpoint="http://localhost:4318/v1/metrics",
    ),
))
```

### Logging

```python
from glide import Logger

Logger.set_logger_config("warn", "glide.log")   # Production
Logger.set_logger_config("error")                # Max performance
```

## Concurrent Operations (Async)

```python
# When operations are truly independent and on different keys:
user, posts, comments = await asyncio.gather(
    client.get("user:123"),
    client.lrange("posts:123", 0, -1),
    client.lrange("comments:123", 0, -1),
)
```

Server-side config: `server-configuration-guide.md`
