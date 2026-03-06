# Retry Strategies (Cluster Batch)

**Retry on server errors:**
```python
from glide_shared.commands.batch_options import BatchRetryStrategy

options = ClusterBatchOptions(
    retry_strategy=BatchRetryStrategy(
        retry_server_error=True,
        retry_connection_error=False,
    )
)
results = await client.exec(batch, raise_on_error=True, options=options)
```

**Retry on connection errors:**
```python
options = ClusterBatchOptions(
    retry_strategy=BatchRetryStrategy(
        retry_server_error=False,
        retry_connection_error=True,
    )
)
results = await client.exec(batch, raise_on_error=True, options=options)
```

**Retry on both:**
```python
options = ClusterBatchOptions(
    retry_strategy=BatchRetryStrategy(
        retry_server_error=True,
        retry_connection_error=True,
    )
)
results = await client.exec(batch, raise_on_error=True, options=options)
```

**No retries:**
```python
options = ClusterBatchOptions(
    retry_strategy=BatchRetryStrategy(
        retry_server_error=False,
        retry_connection_error=False,
    )
)
results = await client.exec(batch, raise_on_error=True, options=options)
```

