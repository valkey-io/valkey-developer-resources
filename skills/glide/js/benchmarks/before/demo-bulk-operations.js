import { GlideClient } from '@valkey/valkey-glide';

const client = await GlideClient.createClient({
  addresses: [{ host: 'localhost', port: 6379 }],
});

// Efficient batch write using pipeline
async function batchWrite(count = 5000) {
  const start = Date.now();
  const pipeline = client.createPipeline();
  
  for (let i = 0; i < count; i++) {
    pipeline.set(`user:${i}`, JSON.stringify({ id: i, name: `User${i}`, active: true }));
  }
  
  await client.exec(pipeline);
  console.log(`Wrote ${count} keys in ${Date.now() - start}ms`);
}

// Efficient batch read using pipeline
async function batchRead(count = 5000) {
  const start = Date.now();
  const pipeline = client.createPipeline();
  
  for (let i = 0; i < count; i++) {
    pipeline.get(`user:${i}`);
  }
  
  const results = await client.exec(pipeline);
  console.log(`Read ${count} keys in ${Date.now() - start}ms`);
  return results.map(r => r ? JSON.parse(r) : null);
}

// Batch operations with MSET/MGET
async function batchMSet(count = 5000) {
  const start = Date.now();
  const keyValues = {};
  
  for (let i = 0; i < count; i++) {
    keyValues[`session:${i}`] = JSON.stringify({ token: `tok_${i}`, exp: Date.now() + 3600000 });
  }
  
  await client.mset(keyValues);
  console.log(`MSET ${count} keys in ${Date.now() - start}ms`);
}

async function batchMGet(count = 5000) {
  const start = Date.now();
  const keys = Array.from({ length: count }, (_, i) => `session:${i}`);
  const results = await client.mget(keys);
  console.log(`MGET ${count} keys in ${Date.now() - start}ms`);
  return results.map(r => r ? JSON.parse(r) : null);
}

// Run demo
await batchWrite(5000);
await batchRead(5000);
await batchMSet(5000);
await batchMGet(5000);

await client.close();
