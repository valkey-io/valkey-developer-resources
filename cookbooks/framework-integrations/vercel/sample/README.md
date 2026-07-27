# Vercel + Valkey Streams Sample

A Next.js application demonstrating reliable message queuing with Valkey Streams.

## Prerequisites

- Node.js 20.19+ (LTS)
- Docker or Finch (for running Valkey)

## Setup

```bash
# Start Valkey
docker compose up -d

# Install dependencies
npm install

# Start the dev server
npm run dev
```

Visit <http://localhost:3000> to see the contact form.

## Running Tests

Tests use a mocked GLIDE client — no running Valkey instance required:

```bash
npm test
```

Expected output:

```text
 ✓ __tests__/helpers.test.ts (11 tests)
 ✓ __tests__/route.test.ts (7 tests)

 Test Files  2 passed (2)
      Tests  18 passed (18)
```

## API Endpoints

| Method | Path | Description |
| ------ | ---- | ----------- |
| `POST` | `/api/messages` | Add a message to the stream |
| `GET` | `/api/messages` | Consume next unprocessed message |
| `DELETE` | `/api/messages?messageId=<id>` | Acknowledge a message |

## Complete Flow (curl)

```bash
# 1. Produce
curl -X POST http://localhost:3000/api/messages \
  -H "Content-Type: application/json" \
  -d '{"name": "Test", "email": "test@example.com", "message": "Hello!"}'

# 2. Consume
curl http://localhost:3000/api/messages

# 3. Acknowledge (use streamMessageId from step 2)
curl -X DELETE "http://localhost:3000/api/messages?messageId=<id>"
```

## Configuration

| Variable | Default | Description |
| -------- | ------- | ----------- |
| `VALKEY_ENDPOINT` | `localhost:6379` | Valkey server address (`host:port`) |

## Teardown

```bash
docker compose down -v
```

## Troubleshooting

**Message stuck in pending list:** If you consumed a message (GET) but didn't acknowledge it (DELETE), it stays in the Pending Entries List. After 60 seconds, the next GET will auto-reclaim it.

**Reset the stream:**

```bash
docker exec valkey-vercel valkey-cli DEL contact-messages
```
