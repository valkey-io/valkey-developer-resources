# PHP GLIDE Demos

## Prerequisites

- Docker installed on your system
- Access to Valkey server (set `VALKEY_HOST` environment variable)

## Setup

Build the Docker image:

```bash
docker build -t php-glide .
```

## Running Demos

Run a demo script:

```bash
docker run --rm \
  -v $(pwd)/demos:/app \
  -e VALKEY_HOST=${VALKEY_HOST} \
  --network host \
  php-glide php /app/basic_operations.php
```

Or enter interactive shell:

```bash
docker run --rm -it \
  -v $(pwd)/demos:/app \
  -e VALKEY_HOST=${VALKEY_HOST} \
  --network host \
  php-glide bash
```

## Demos

- `basic_operations.php` - Connect, set/get, error handling
- `batch_pipeline.php` - Atomic transactions vs non-atomic pipelines
- `cluster_operations.php` - Multi-node routing, hash slot constraints

All demos connect to Valkey at `$VALKEY_HOST:6379` (standalone) or `:7000` (cluster).
