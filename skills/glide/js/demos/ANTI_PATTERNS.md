# Node.js GLIDE Anti-Pattern Demonstrations

This demo proves common Node.js anti-patterns and shows the correct alternatives.

## Running the Demo

```bash
cd js/demos
npm install
timeout 10 node anti_patterns_demo.js
```

**Note:** Use `timeout` because the demo intentionally creates resource leaks to demonstrate anti-patterns.

## Demonstrations

### 1. ❌ forEach with async (Fire-and-Forget)

**Problem:** `forEach` doesn't await async callbacks
```javascript
keys.forEach(async (key) => {
  await client.set(key, value);
});
console.log("Done!"); // LIE - operations still running
```

**Proof:** Demo shows "completed in 1ms" but operations take 200ms

**Solutions:**
- ✅ `for...of` - Sequential execution
- ✅ `Promise.all` - Parallel execution  
- ✅ Batch operations - Single round-trip (best for GLIDE)

### 2. ❌ Missing finally Block

**Problem:** Client not closed if error occurs
```javascript
const client = await GlideClient.createClient({...});
await client.set("key", "value");
client.close(); // Never runs if error occurs
```

**Proof:** Demo shows "Client NOT closed - resource leak!"

**Solution:**
```javascript
try {
  await client.set("key", "value");
} finally {
  client.close(); // Always runs
}
```

## Results

All demonstrations prove:
1. ✅ forEach completes immediately (0-1ms) - fire-and-forget confirmed
2. ✅ for...of waits for all operations - sequential confirmed
3. ✅ Promise.all waits for all operations - parallel confirmed
4. ✅ Batch is fastest - single round-trip confirmed
5. ✅ Missing finally causes resource leak - confirmed
6. ✅ finally block ensures cleanup - confirmed

## Related Documentation

See [JS.md](../JS.md) for:
- Best Practices section
- Common Pitfalls #5 and #6
- Complete anti-pattern documentation
