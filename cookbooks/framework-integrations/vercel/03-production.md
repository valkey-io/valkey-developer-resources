# Production Deployment on Vercel

> Deploy your Valkey Streams application to Vercel with proper networking, security, and monitoring for production workloads.

**Advanced** · TypeScript · ~25 min

**Who is this for:** Developers ready to move from local development to a production deployment, connecting Vercel Functions to a managed Valkey instance.

## Prerequisites

- Completed [01 - Getting Started](./01-getting-started.md) and [02 - Streams Deep Dive](./02-streams-deep-dive.md)
- A Vercel account with a deployed project
- A managed Valkey instance (self-hosted, or a cloud provider such as AWS ElastiCache, Google Cloud Memorystore, or any Valkey-compatible service)

## Step 1: Managed Valkey Options

Any Valkey-compatible service works. Here are common choices:

| Provider | Service | Notes |
| -------- | ------- | ----- |
| Self-hosted | `valkey/valkey` on a VM or Kubernetes | Full control, requires ops |
| AWS | ElastiCache for Valkey | VPC-only, requires network connectivity |
| Google Cloud | Memorystore for Valkey | VPC-native |
| Any cloud | Valkey on a VM with ACLs + TLS | Portable |

The key requirement is that your Valkey instance is reachable from Vercel Functions at runtime.

## Step 2: Network Connectivity

Managed Valkey instances typically run inside a private network (VPC). Vercel Functions run on Vercel's infrastructure. You need a network path between them.

### Options

1. **Vercel Secure Compute** (Enterprise) — Private peering between Vercel and your VPC
2. **VPN / WireGuard tunnel** — Connect Vercel to your network via a tunnel
3. **Public endpoint with TLS + ACLs** — Expose Valkey on a public IP with mutual TLS and strong authentication (simplest for non-enterprise)

For option 3 (public with TLS), update your GLIDE configuration:

```typescript
import { GlideClient, GlideClientConfiguration } from '@valkey/valkey-glide'

const config: GlideClientConfiguration = {
  addresses: [{ host: process.env.VALKEY_HOST!, port: parseInt(process.env.VALKEY_PORT!) }],
  useTLS: true,
  credentials: {
    username: process.env.VALKEY_USERNAME,
    password: process.env.VALKEY_PASSWORD!,
  },
  requestTimeout: 5000,
  clientName: 'vercel_message_queue_client',
}
```

## Step 3: Environment Variables on Vercel

Set these in your Vercel project settings (Settings → Environment Variables):

| Variable | Example | Required |
| -------- | ------- | -------- |
| `VALKEY_ENDPOINT` | `your-cluster.example.com:6380` | Yes |
| `VALKEY_PASSWORD` | `(secret)` | If auth enabled |
| `VALKEY_USERNAME` | `default` | If ACLs used |

For production, use Vercel's encrypted environment variables — they are never exposed in build logs or client bundles.

## Step 4: Connection Resilience

The sample implements a health-check reconnection pattern:

```typescript
let client: GlideClient | undefined

async function getClient(): Promise<GlideClient> {
  if (client) {
    try {
      await client.ping()
      return client
    } catch {
      client = undefined  // Connection dead, recreate
    }
  }
  // ... create new client
}
```

This handles:

- Cold starts (no existing connection)
- Stale connections (Valkey restarted or network blip)
- Connection pool exhaustion (single client reused across requests)

### Serverless Considerations

| Concern | Solution |
| ------- | -------- |
| Cold start latency | Client is cached in module scope; reused across invocations in the same instance |
| Connection limits | One connection per function instance; scale is bounded by concurrent executions |
| Timeouts | `requestTimeout: 5000` ensures fast failure |
| Reconnection | `ping()` health check detects stale connections |

## Step 5: Error Handling

The application separates user-facing errors from internal details:

```typescript
function handleError(error: unknown, defaultMessage: string) {
  console.error('API Error:', error)  // Full error logged server-side

  const message = error instanceof Error ? error.message : ''

  if (message.includes('ECONNREFUSED') || message.includes('timeout')) {
    // Connection problem — tell the user what's wrong
    return NextResponse.json(
      { error: `${defaultMessage}: Unable to connect to Valkey.` },
      { status: 503 }
    )
  }

  // Generic error — never leak internal details
  return NextResponse.json({ error: defaultMessage }, { status: 500 })
}
```

This pattern:

- Logs full error details to Vercel's function logs (visible in dashboard)
- Returns safe messages to clients (no hostnames, ports, or stack traces)
- Uses 503 for connection issues (clients can retry)
- Uses 500 for unexpected errors

## Step 6: Monitoring

### Valkey-Side Monitoring

Use `CLIENT LIST` to verify your application is connected with the expected name:

```bash
valkey-cli CLIENT LIST
# Look for: name=vercel_message_queue_client
```

Monitor stream health:

```bash
# Stream length and consumer group lag
valkey-cli XINFO STREAM contact-messages
valkey-cli XPENDING contact-messages contact-processors

# Memory usage
valkey-cli MEMORY USAGE contact-messages
```

### Vercel-Side Monitoring

- **Function logs**: All `console.error` calls appear in Vercel's Runtime Logs
- **Function duration**: Monitor for timeouts (if a consumer hangs, messages accumulate in the PEL)
- **Invocations**: Correlate with stream length to ensure consumers keep up with producers

## Step 7: Deploy

```bash
# From the sample/ directory
npx vercel --prod
```

Or use the deploy button (once the upstream template is published):

[![Deploy with Vercel](https://vercel.com/button)](https://vercel.com/new/clone?repository-url=https://github.com/vercel/examples/tree/main/solutions/aws-message-queue-elasticache&project-name=valkey-message-queue&repository-name=valkey-message-queue&env=VALKEY_ENDPOINT&envDescription=Valkey%20endpoint%20in%20host:port%20format)

## Configuration Reference

| Variable | Default | Description |
| -------- | ------- | ----------- |
| `VALKEY_ENDPOINT` | `localhost:6379` | Valkey address (`host:port`) |
| `VALKEY_PASSWORD` | _(none)_ | Authentication password |
| `VALKEY_USERNAME` | _(none)_ | ACL username |
| `NODE_ENV` | `production` | Set by Vercel automatically |

## Security Checklist

- [ ] Valkey bound to private network or authenticated endpoint
- [ ] TLS enabled for production connections
- [ ] `VALKEY_PASSWORD` stored in encrypted env vars (not `.env` files)
- [ ] API routes protected by authentication middleware
- [ ] Stream MAXLEN prevents unbounded memory growth
- [ ] `requestTimeout` set to prevent hanging connections

## Teardown

To remove the deployment:

```bash
npx vercel rm valkey-message-queue
```

To stop local Valkey:

```bash
docker compose down -v
```

---

[← Streams Deep Dive](./02-streams-deep-dive.md) | [README](./README.md)
