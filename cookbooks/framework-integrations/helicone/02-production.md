# Production Deployment with Helicone and Valkey

> A guide to operating Helicone's Valkey integration in production — covering TLS, Lua scripting,
> monitoring, and encrypted key storage.

**Intermediate** · JavaScript · ~20 min

**Who is this for:** DevOps engineers and backend developers familiar with Helicone deployment who need
TLS, Lua scripting, monitoring, and encrypted storage guidance.

## Architecture

Helicone's Jawn API server connects to Valkey through a single client shared by all 5 subsystems:

```text
┌─────────────────────────────────────────────────────────┐
│                     Jawn API Server                     │
│                                                         │
│  ┌──────────┐ ┌───────────────┐  ┌───────────────────┐  │
│  │ KV Cache │ │ Proxy Rate    │  │ HTTP API Rate     │  │
│  │ GET/SET  │ │ Limiter       │  │ Limiter           │  │
│  │ PX       │ │ GET/SET EX    │  │ SCRIPT LOAD/      │  │
│  └─────┬────┘ └──────┬────────┘  │ EVALSHA           │  │
│        │             │           └─────────┬─────────┘  │
│  ┌─────┴────┐ ┌──────┴────────┐  ┌─────────┴─────────┐  │
│  │ Usage    │ │ Encrypted Key │  │                   │  │
│  │ Limit    │ │ Cache         │  │    (all share     │  │
│  │ Cache    │ │ GET/SET EX    │  │     one client    │  │
│  │ GET/SET  │ │               │  │     connection)   │  │
│  │ EX       │ │               │  │                   │  │
│  └─────┬────┘ └──────┬────────┘  └────────┬──────────┘  │
│        │             │                    │             │
└────────┼─────────────┼────────────────────┼─────────────┘
         │             │                    │
         └─────────────┼────────────────────┘
                       │
                       ▼
              ┌─────────────────┐
              │  Valkey Server  │
              │  (port 6379)    │
              └─────────────────┘
```

All 5 subsystems use only core Valkey string and scripting commands. No modules or extensions are required.

## TLS Configuration

In production, always encrypt the connection between Jawn and Valkey with TLS:

```javascript
import Redis from "ioredis";

const client = new Redis({
  host: process.env.VALKEY_HOST,
  port: parseInt(process.env.VALKEY_PORT || "6379", 10),
  password: process.env.VALKEY_AUTH,
  tls: process.env.VALKEY_TLS === "true" ? {
    rejectUnauthorized: true,
    // Optionally specify CA certificate for self-signed certs:
    // ca: fs.readFileSync("/path/to/ca.crt"),
  } : undefined,
});
```

When TLS is enabled, the client upgrades the socket to a secure connection before authentication.
This protects credentials and cached data (including encrypted keys) in transit.

> **Warning:** Never disable TLS certificate verification (`rejectUnauthorized: false`) in production.
> Doing so exposes the connection to man-in-the-middle attacks. If you use self-signed certificates,
> configure the `ca` option to pin the certificate authority instead of disabling verification entirely.

## Lua Script Execution

Helicone's HTTP API rate limiter uses a Lua script for atomic increment-and-expire operations.
The script executes `INCR`, `PEXPIRE`, and `PTTL` in a single round-trip via `SCRIPT LOAD` and `EVALSHA`,
ensuring each request is counted and expired atomically.

The Lua script:

```lua
local current = redis.call('INCR', KEYS[1])
if current == 1 then
  redis.call('PEXPIRE', KEYS[1], ARGV[1])
end
local ttl = redis.call('PTTL', KEYS[1])
return {current, ttl}
```

Loading and executing the script:

```javascript
import Redis from "ioredis";

const client = new Redis({ host: process.env.VALKEY_HOST });

const RATE_LIMIT_SCRIPT = `
local current = redis.call('INCR', KEYS[1])
if current == 1 then
  redis.call('PEXPIRE', KEYS[1], ARGV[1])
end
local ttl = redis.call('PTTL', KEYS[1])
return {current, ttl}
`;

// Load script once at startup — returns SHA1 hash
const scriptSha = await client.script("LOAD", RATE_LIMIT_SCRIPT);

// Execute per-request via EVALSHA (avoids re-transmitting script body)
const windowMs = 60000; // 1-minute window
const result = await client.evalsha(scriptSha, 1, "rl:org_123", String(windowMs));

const [current, ttl] = result;
console.log(`Requests: ${current}, TTL: ${ttl}ms`);
```

If Valkey evicts the script from its cache, it returns a `NOSCRIPT` error. Handle this by reloading
the script and retrying:

```javascript
try {
  const result = await client.evalsha(scriptSha, 1, key, String(windowMs));
} catch (err) {
  if (err instanceof Error && err.message.includes("NOSCRIPT")) {
    const newSha = await client.script("LOAD", RATE_LIMIT_SCRIPT);
    const result = await client.evalsha(newSha, 1, key, String(windowMs));
  }
}
```

## Monitoring Command Patterns

Monitor Valkey command patterns to understand subsystem behavior and detect performance issues.

Use `INFO commandstats` to see which commands each subsystem generates:

```bash
valkey-cli INFO commandstats
```

Expected output for a healthy Helicone instance:

```text
cmdstat_get:calls=15234,usec=45702,usec_per_call=3.00
cmdstat_set:calls=8921,usec=35684,usec_per_call=4.00
cmdstat_incr:calls=3102,usec=6204,usec_per_call=2.00
cmdstat_evalsha:calls=3102,usec=18612,usec_per_call=6.00
cmdstat_pttl:calls=3102,usec=6204,usec_per_call=2.00
cmdstat_pexpire:calls=412,usec=824,usec_per_call=2.00
```

Use `SLOWLOG GET` to identify slow operations:

```bash
valkey-cli SLOWLOG GET 10
```

For real-time debugging in development, use `MONITOR` to observe commands as they execute:

```bash
valkey-cli MONITOR
```

You can monitor programmatically:

```javascript
import Redis from "ioredis";

const monitor = new Redis({ host: process.env.VALKEY_HOST });

// Track command frequency by type
const commandCounts = new Map();

const monitorClient = await monitor.monitor();
monitorClient.on("monitor", (_time, args) => {
  const cmd = args[0]?.toUpperCase() || "UNKNOWN";
  commandCounts.set(cmd, (commandCounts.get(cmd) || 0) + 1);
});
```

## Encrypted Key Storage

Helicone stores provider API keys and authentication tokens encrypted in Valkey using AES-GCM
(Web Crypto API). Keys are hashed with SHA-256 before storage so original key names are never
exposed in the datastore.

Storage format in Valkey: `{iv: hex-string, content: hex-string}` serialized as JSON.

```javascript
import { webcrypto } from "node:crypto";
import Redis from "ioredis";

const client = new Redis({ host: process.env.VALKEY_HOST });

// Generate encryption key (in production, load from a secrets manager)
const cryptoKey = await webcrypto.subtle.generateKey(
  { name: "AES-GCM", length: 256 },
  false,
  ["encrypt", "decrypt"]
);

async function encryptAndStore(key, value, ttlSeconds) {
  // Hash the key name with SHA-256
  const keyHash = Array.from(
    new Uint8Array(await webcrypto.subtle.digest("SHA-256", new TextEncoder().encode(key)))
  ).map((b) => b.toString(16).padStart(2, "0")).join("");

  // Encrypt the value with AES-GCM
  const iv = webcrypto.getRandomValues(new Uint8Array(12));
  const ciphertext = await webcrypto.subtle.encrypt(
    { name: "AES-GCM", iv },
    cryptoKey,
    new TextEncoder().encode(value)
  );

  const encrypted = JSON.stringify({
    iv: Array.from(iv).map((b) => b.toString(16).padStart(2, "0")).join(""),
    content: Array.from(new Uint8Array(ciphertext)).map((b) => b.toString(16).padStart(2, "0")).join(""),
  });

  // Store with TTL using SET EX
  await client.set(keyHash, encrypted, "EX", ttlSeconds);
}

// Store an encrypted API key with 10-minute TTL
await encryptAndStore("provider:openai:key", "sk-placeholder-key-value", 600);
```

> **Warning:** Never log or expose decrypted secrets in application output, error messages, or
> monitoring systems. Store encryption keys in a dedicated secrets manager (not environment variables)
> and rotate them regularly. The SHA-256 key hashing prevents key enumeration, but the encrypted
> values are only as secure as the encryption key itself.

## Configuration Reference

| Variable | Default | Description |
| -------- | ------- | ----------- |
| `VALKEY_HOST` | _(unset)_ | Valkey hostname. |
| `VALKEY_PORT` | `6379` | Valkey port number. |
| `VALKEY_TLS` | `false` | Set to `true` to enable TLS encryption for the Valkey connection. |
| `VALKEY_AUTH` | _(unset)_ | Valkey AUTH password. Required when the server is configured with `requirepass`. |

## No Modules Required

Helicone's entire Valkey integration uses only core string and scripting commands: `GET`, `SET EX`,
`SET PX`, `INCR`, `PTTL`, `PEXPIRE`, `SCRIPT LOAD`, and `EVALSHA`. No Valkey modules, extensions,
or custom data structures are required. This means any standard Valkey 8+ deployment works
out of the box — no additional installation or configuration needed.
