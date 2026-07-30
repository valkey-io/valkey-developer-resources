import { describe, it, before, after, beforeEach } from "node:test";
import assert from "node:assert/strict";
import { createClient } from "redis";

const PREFIX = "test:voltagent";
const AGENT_ID = "test-agent";

function taskKey(prefix, agentId, taskId) {
  return `${prefix}:${agentId}::${taskId}`;
}

describe("VoltAgent Task Store Patterns", () => {
  let client;

  before(async () => {
    client = createClient({ url: "redis://localhost:6379" });
    await client.connect();
  });

  after(async () => {
    await client.quit();
  });

  beforeEach(async () => {
    // Clean up test keys
    const keys = await client.keys(`${PREFIX}:*`);
    if (keys.length > 0) {
      await client.del(keys);
    }
  });

  it("should connect and respond to PING", async () => {
    const result = await client.ping();
    assert.equal(result, "PONG");
  });

  it("should store and retrieve a task as JSON string", async () => {
    const task = {
      id: "task_001",
      status: "submitted",
      input: "Hello, agent!",
      createdAt: "2025-01-01T00:00:00.000Z",
    };

    const key = taskKey(PREFIX, AGENT_ID, task.id);
    await client.set(key, JSON.stringify(task));

    const stored = await client.get(key);
    assert.notEqual(stored, null);

    const parsed = JSON.parse(stored);
    assert.equal(parsed.id, "task_001");
    assert.equal(parsed.status, "submitted");
    assert.equal(parsed.input, "Hello, agent!");
  });

  it("should generate composite keys with prefix:agentId::taskId pattern", async () => {
    const key = taskKey("a2a:tasks", "weather-agent", "task_abc123");
    assert.equal(key, "a2a:tasks:weather-agent::task_abc123");

    // Verify the double-colon separates agentId from taskId
    const parts = key.split("::");
    assert.equal(parts.length, 2);
    assert.equal(parts[0], "a2a:tasks:weather-agent");
    assert.equal(parts[1], "task_abc123");
  });

  it("should support TTL expiration via SET with EX", async () => {
    const key = taskKey(PREFIX, AGENT_ID, "task_ttl");
    const task = { id: "task_ttl", status: "completed" };

    // Set with 1-second TTL
    await client.set(key, JSON.stringify(task), { EX: 1 });

    // Should exist immediately
    const before = await client.get(key);
    assert.notEqual(before, null);

    // Wait for expiration
    await new Promise((resolve) => setTimeout(resolve, 1100));

    // Should be gone
    const afterExpiry = await client.get(key);
    assert.equal(afterExpiry, null);
  });

  it("should overwrite task state on update (SET replaces value)", async () => {
    const key = taskKey(PREFIX, AGENT_ID, "task_update");

    // Initial state
    await client.set(key, JSON.stringify({ id: "task_update", status: "submitted" }));

    // Update state
    await client.set(key, JSON.stringify({ id: "task_update", status: "completed", result: "Done" }));

    const stored = JSON.parse(await client.get(key));
    assert.equal(stored.status, "completed");
    assert.equal(stored.result, "Done");
  });

  it("should isolate tasks by prefix", async () => {
    const prefix1 = `${PREFIX}:agent-one`;
    const prefix2 = `${PREFIX}:agent-two`;

    await client.set(`${prefix1}::task_1`, JSON.stringify({ agent: "one" }));
    await client.set(`${prefix2}::task_1`, JSON.stringify({ agent: "two" }));

    const val1 = JSON.parse(await client.get(`${prefix1}::task_1`));
    const val2 = JSON.parse(await client.get(`${prefix2}::task_1`));

    assert.equal(val1.agent, "one");
    assert.equal(val2.agent, "two");

    // Cleanup
    await client.del(`${prefix1}::task_1`);
    await client.del(`${prefix2}::task_1`);
  });
});

describe("VoltAgent Resumable Stream Patterns", () => {
  let client;
  let subscriber;

  before(async () => {
    client = createClient({ url: "redis://localhost:6379" });
    await client.connect();
    subscriber = client.duplicate();
    await subscriber.connect();
  });

  after(async () => {
    await subscriber.quit();
    await client.quit();
  });

  beforeEach(async () => {
    const keys = await client.keys(`${PREFIX}:stream:*`);
    if (keys.length > 0) {
      await client.del(keys);
    }
  });

  it("should deliver messages via PUB/SUB", async () => {
    const channel = `${PREFIX}:stream:channel:task_pub`;
    const received = [];

    await subscriber.subscribe(channel, (message) => {
      received.push(JSON.parse(message));
    });

    // Publish events
    await client.publish(channel, JSON.stringify({ seq: 1, type: "progress", data: "Working..." }));
    await client.publish(channel, JSON.stringify({ seq: 2, type: "complete", data: "Done" }));

    // Allow pub/sub delivery
    await new Promise((resolve) => setTimeout(resolve, 100));

    assert.equal(received.length, 2);
    assert.equal(received[0].seq, 1);
    assert.equal(received[0].data, "Working...");
    assert.equal(received[1].seq, 2);
    assert.equal(received[1].type, "complete");

    await subscriber.unsubscribe(channel);
  });

  it("should track stream sequence numbers with INCR", async () => {
    const seqKey = `${PREFIX}:stream:seq:task_incr`;

    // INCR starts at 1 if key doesn't exist
    const seq1 = await client.incr(seqKey);
    const seq2 = await client.incr(seqKey);
    const seq3 = await client.incr(seqKey);

    assert.equal(seq1, 1);
    assert.equal(seq2, 2);
    assert.equal(seq3, 3);
  });

  it("should store active stream state with TTL", async () => {
    const activeKey = `${PREFIX}:stream:active:task_state`;
    const streamState = {
      sequence: 5,
      status: "streaming",
      createdAt: "2025-01-01T00:00:00.000Z",
    };

    await client.set(activeKey, JSON.stringify(streamState), { EX: 1 });

    // Should exist
    const stored = JSON.parse(await client.get(activeKey));
    assert.equal(stored.sequence, 5);
    assert.equal(stored.status, "streaming");

    // Wait for TTL
    await new Promise((resolve) => setTimeout(resolve, 1100));

    // Should be expired
    const expired = await client.get(activeKey);
    assert.equal(expired, null);
  });

  it("should support multiple concurrent channels (one-client-per-channel pattern)", async () => {
    const channel1 = `${PREFIX}:stream:channel:task_multi_1`;
    const channel2 = `${PREFIX}:stream:channel:task_multi_2`;
    const received1 = [];
    const received2 = [];

    // In production, each channel gets its own GlideClient.
    // Here we use the same subscriber for simplicity — the pattern is the same.
    await subscriber.subscribe(channel1, (message) => {
      received1.push(JSON.parse(message));
    });
    await subscriber.subscribe(channel2, (message) => {
      received2.push(JSON.parse(message));
    });

    await client.publish(channel1, JSON.stringify({ target: "channel1" }));
    await client.publish(channel2, JSON.stringify({ target: "channel2" }));

    await new Promise((resolve) => setTimeout(resolve, 100));

    assert.equal(received1.length, 1);
    assert.equal(received1[0].target, "channel1");
    assert.equal(received2.length, 1);
    assert.equal(received2[0].target, "channel2");

    await subscriber.unsubscribe(channel1);
    await subscriber.unsubscribe(channel2);
  });

  it("should use INCR for monotonic sequence suitable as Last-Event-ID", async () => {
    const seqKey = `${PREFIX}:stream:seq:task_lastid`;

    // Simulate publishing 5 events
    for (let i = 0; i < 5; i++) {
      await client.incr(seqKey);
    }

    const currentSeq = await client.get(seqKey);
    assert.equal(currentSeq, "5");

    // A reconnecting client with Last-Event-ID: 3 would replay events 4 and 5
    const lastEventId = 3;
    const currentSeqNum = parseInt(currentSeq, 10);
    const missedCount = currentSeqNum - lastEventId;
    assert.equal(missedCount, 2);
  });
});
