import { createClient } from "redis";

const PREFIX = "a2a:tasks";
const AGENT_ID = "demo-agent";
const STREAM_PREFIX = "streams";

function taskKey(agentId, taskId) {
  return `${PREFIX}:${agentId}::${taskId}`;
}

function streamKey(taskId) {
  return `${STREAM_PREFIX}:active:${taskId}`;
}

function channelName(taskId) {
  return `${STREAM_PREFIX}:channel:${taskId}`;
}

async function main() {
  const client = createClient({ url: "redis://localhost:6379" });
  await client.connect();

  try {
    console.log("=== VoltAgent Task Store Simulation ===\n");

    // 1. Create a task (SET with JSON + TTL)
    const task = {
      id: "task_sim_001",
      status: "submitted",
      input: "What is the weather in Austin?",
      createdAt: new Date().toISOString(),
    };

    const key = taskKey(AGENT_ID, task.id);
    await client.set(key, JSON.stringify(task), { EX: 3600 });
    console.log(`✅ Task created: ${key}`);
    console.log(`   Status: ${task.status}`);

    // 2. Update task status (overwrite with new JSON)
    task.status = "working";
    await client.set(key, JSON.stringify(task), { EX: 3600 });
    console.log(`✅ Task updated: status → ${task.status}`);

    // 3. Read task back (GET + parse)
    const stored = JSON.parse(await client.get(key));
    console.log(`✅ Task retrieved: ${stored.id} (${stored.status})`);

    // 4. Complete the task
    task.status = "completed";
    task.result = "Sunny, 72°F";
    await client.set(key, JSON.stringify(task), { EX: 3600 });
    console.log(`✅ Task completed: result = "${task.result}"`);

    // 5. Verify TTL is set
    const ttl = await client.ttl(key);
    console.log(`✅ TTL remaining: ${ttl}s`);

    console.log("\n=== VoltAgent Resumable Stream Simulation ===\n");

    // 6. Create stream state
    const taskId = "task_stream_001";
    const sKey = streamKey(taskId);
    const streamState = {
      sequence: 0,
      status: "streaming",
      createdAt: new Date().toISOString(),
    };
    await client.set(sKey, JSON.stringify(streamState), { EX: 3600 });
    console.log(`✅ Stream state created: ${sKey}`);

    // 7. Simulate publishing events via PUB/SUB
    const channel = channelName(taskId);

    // Create a subscriber
    const subscriber = client.duplicate();
    await subscriber.connect();

    const received = [];
    await subscriber.subscribe(channel, (message) => {
      received.push(JSON.parse(message));
    });
    console.log(`✅ Subscribed to: ${channel}`);

    // Publish events (simulate agent streaming responses)
    for (let seq = 1; seq <= 3; seq++) {
      const event = { seq, type: "progress", data: `Step ${seq} of 3` };
      await client.publish(channel, JSON.stringify(event));
    }

    // Give pub/sub a moment to deliver
    await new Promise((resolve) => setTimeout(resolve, 100));

    console.log(`✅ Published 3 events, received ${received.length}:`);
    for (const event of received) {
      console.log(`   [seq=${event.seq}] ${event.data}`);
    }

    // 8. Track sequence with INCR
    const seqKey = `${STREAM_PREFIX}:seq:${taskId}`;
    await client.set(seqKey, "0");
    const seq1 = await client.incr(seqKey);
    const seq2 = await client.incr(seqKey);
    const seq3 = await client.incr(seqKey);
    console.log(`✅ Sequence numbers via INCR: ${seq1}, ${seq2}, ${seq3}`);

    // Cleanup
    await subscriber.unsubscribe(channel);
    await subscriber.quit();
    await client.del(key);
    await client.del(sKey);
    await client.del(seqKey);

    console.log("\n✅ Simulation complete — all VoltAgent patterns demonstrated.");
  } finally {
    await client.quit();
  }
}

main().catch((err) => {
  console.error("❌ Simulation failed:", err.message);
  process.exit(1);
});
