import { NextResponse } from 'next/server'
import { GlideClient, GlideClientConfiguration } from '@valkey/valkey-glide'
import { validateContactForm, buildMessageResponse, type ValidationError, type ValidationSuccess } from './helpers'

// Force Node.js runtime for native modules (@valkey/valkey-glide uses Rust bindings)
// NOTE: This demo has no authentication. In production, add auth middleware.
export const runtime = 'nodejs'

const STREAM_NAME = 'contact-messages'
const CONSUMER_GROUP = 'contact-processors'
// NOTE: HOSTNAME is not a Vercel-provided env var, so this defaults to 'consumer-default'
// in production. This is fine — consumer groups deliver messages regardless of consumer name.
// For per-instance tracking, use VERCEL_DEPLOYMENT_ID or crypto.randomUUID().
const CONSUMER_NAME = `consumer-${process.env.VERCEL_DEPLOYMENT_ID || process.env.HOSTNAME || 'default'}`

let client: GlideClient | undefined

/**
 * Get or initialize Valkey client with health check.
 * The client is reused across requests in the same function instance.
 */
async function getClient(): Promise<GlideClient> {
  if (client) {
    try {
      await client.ping()
      return client
    } catch {
      client = undefined
    }
  }

  const endpoint = process.env.VALKEY_ENDPOINT || 'localhost:6379'
  const [host, portStr] = endpoint.split(':')
  const port = parseInt(portStr || '6379', 10)

  if (!host || isNaN(port)) {
    throw new Error('VALKEY_ENDPOINT must be in format host:port')
  }

  const config: GlideClientConfiguration = {
    addresses: [{ host, port }],
    requestTimeout: 5000,
    clientName: 'vercel_message_queue_client',
  }

  client = await GlideClient.createClient(config)
  return client
}

let groupCreated = false

async function ensureConsumerGroup(valkeyClient: GlideClient): Promise<void> {
  if (groupCreated) return
  try {
    await valkeyClient.xgroupCreate(STREAM_NAME, CONSUMER_GROUP, '0', { mkStream: true })
  } catch (error: unknown) {
    // BUSYGROUP means group already exists — safe to ignore
    if (!(error instanceof Error && error.message.includes('BUSYGROUP'))) {
      throw error
    }
  }
  groupCreated = true
}

function handleError(error: unknown, defaultMessage: string) {
  console.error('API Error:', error)

  const message = error instanceof Error ? error.message : ''

  // Connection errors get a helpful explanation without leaking internals
  if (
    message.includes('ECONNREFUSED') ||
    message.includes('ETIMEDOUT') ||
    message.includes('ENOTFOUND') ||
    message.includes('connection') ||
    message.includes('timeout')
  ) {
    return NextResponse.json(
      { error: `${defaultMessage}: Unable to connect to Valkey. Ensure VALKEY_ENDPOINT is configured and the server is reachable.` },
      { status: 503 }
    )
  }

  return NextResponse.json({ error: defaultMessage }, { status: 500 })
}

/**
 * POST /api/messages — Produce a message
 * Adds a contact form submission to the Valkey stream.
 */
export async function POST(request: Request) {
  try {
    const body = await request.json()
    const validation = validateContactForm(body)

    if (!validation.valid) {
      return NextResponse.json({ error: (validation as ValidationError).error }, { status: 400 })
    }

    const { name, email, message } = (validation as ValidationSuccess).data
    const valkeyClient = await getClient()
    const timestamp = new Date().toISOString()

    // XADD with approximate MAXLEN trimming to bound stream growth
    const streamMessageId = await valkeyClient.xadd(STREAM_NAME, [
      ['name', name],
      ['email', email],
      ['message', message],
      ['timestamp', timestamp],
    ], { trim: { method: 'maxlen', threshold: 10000, exact: false } })

    return NextResponse.json({ streamMessageId, timestamp }, { status: 201 })
  } catch (error: unknown) {
    return handleError(error, 'Failed to produce message')
  }
}

/**
 * GET /api/messages — Consume a message
 * First tries XAUTOCLAIM for idle messages (> 60s), then XREADGROUP for new ones.
 */
export async function GET() {
  try {
    const valkeyClient = await getClient()
    await ensureConsumerGroup(valkeyClient)

    // Try to reclaim messages idle > 60 seconds
    const claimResponse = await valkeyClient.xautoclaim(
      STREAM_NAME,
      CONSUMER_GROUP,
      CONSUMER_NAME,
      60000,
      '0-0',
      { count: 1 }
    )

    const [, claimMessages] = claimResponse
    const messageIds = Object.keys(claimMessages)
    if (messageIds.length > 0) {
      const streamMessageId = messageIds[0]
      const fieldsArray = claimMessages[streamMessageId]
      return NextResponse.json(
        { message: buildMessageResponse(streamMessageId, fieldsArray, { claimed: true }) },
        { status: 200 }
      )
    }

    // No pending messages — read next undelivered message
    const response = await valkeyClient.xreadgroup(
      CONSUMER_GROUP,
      CONSUMER_NAME,
      { [STREAM_NAME]: '>' },
      { count: 1 }
    )

    if (!response || response.length === 0) {
      return NextResponse.json({ message: null }, { status: 200 })
    }

    const streamData = response[0]
    const messages = streamData.value

    if (!messages || Object.keys(messages).length === 0) {
      return NextResponse.json({ message: null }, { status: 200 })
    }

    const streamMessageId = Object.keys(messages)[0]
    const fieldsArray = messages[streamMessageId]

    if (!fieldsArray) {
      return NextResponse.json({ message: null }, { status: 200 })
    }

    return NextResponse.json(
      { message: buildMessageResponse(streamMessageId, fieldsArray) },
      { status: 200 }
    )
  } catch (error: unknown) {
    return handleError(error, 'Failed to consume message')
  }
}

/**
 * DELETE /api/messages?messageId=<id> — Acknowledge a message
 * Removes it from the pending entries list.
 */
export async function DELETE(request: Request) {
  try {
    const { searchParams } = new URL(request.url)
    const messageId = searchParams.get('messageId')

    if (!messageId) {
      return NextResponse.json(
        { error: 'messageId query parameter is required' },
        { status: 400 }
      )
    }

    const valkeyClient = await getClient()
    await valkeyClient.xack(STREAM_NAME, CONSUMER_GROUP, [messageId])

    return NextResponse.json({ success: true }, { status: 200 })
  } catch (error: unknown) {
    return handleError(error, 'Failed to acknowledge message')
  }
}
