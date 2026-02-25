# Node.js GLIDE Demos

Working examples for developing the Node.js GLIDE skill.

## Setup

```bash
cd js/demos
npm install
```

## Run Demos

```bash
node basic_operations.js
node batch_pipeline.js
node vector_search.js
node cluster_operations.js
```

## Testing

All demos connect to Valkey at host identified in `VALKEY_HOST` environment variable at port `6379` (standalone) or `:7000` (cluster) for local testing.
