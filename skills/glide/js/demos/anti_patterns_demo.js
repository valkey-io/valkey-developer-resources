const { GlideClient, Batch } = require("@valkey/valkey-glide");

// Anti-Pattern #1: forEach with async callbacks (fire-and-forget)
async function demonstrateForEachAntiPattern() {
    console.log("\n=== Anti-Pattern: forEach with async ===");
    
    const client = await GlideClient.createClient({
        addresses: [{ host: process.env.VALKEY_HOST || "localhost", port: 6379 }],
    });

    try {
        const keys = ["key1", "key2", "key3"];
        
        // ❌ WRONG: forEach doesn't await
        console.log("Starting forEach (fire-and-forget)...");
        const startTime = Date.now();
        
        keys.forEach(async (key) => {
            await client.set(key, `value-${key}`);
        });
        
        const endTime = Date.now();
        console.log(`forEach "completed" in ${endTime - startTime}ms`);
        console.log("❌ This is a LIE - operations still running!");
        
        // Wait for operations to actually finish
        await new Promise(resolve => setTimeout(resolve, 200));
        console.log("(After 200ms delay, operations actually finished)\n");
        
    } finally {
        client.close();
    }
}

// Correct Pattern #1: for...of with await (sequential)
async function demonstrateForOfPattern() {
    console.log("=== Correct: for...of with await ===");
    
    const client = await GlideClient.createClient({
        addresses: [{ host: process.env.VALKEY_HOST || "localhost", port: 6379 }],
    });

    try {
        const keys = ["key1", "key2", "key3"];
        
        console.log("Starting for...of (sequential)...");
        const startTime = Date.now();
        
        for (const key of keys) {
            await client.set(key, `value-${key}`);
        }
        
        const endTime = Date.now();
        console.log(`✅ for...of completed in ${endTime - startTime}ms`);
        console.log("All operations ACTUALLY finished!\n");
        
    } finally {
        client.close();
    }
}

// Correct Pattern #2: Promise.all (parallel)
async function demonstratePromiseAllPattern() {
    console.log("=== Correct: Promise.all (parallel) ===");
    
    const client = await GlideClient.createClient({
        addresses: [{ host: process.env.VALKEY_HOST || "localhost", port: 6379 }],
    });

    try {
        const keys = ["key1", "key2", "key3"];
        
        console.log("Starting Promise.all (parallel)...");
        const startTime = Date.now();
        
        await Promise.all(keys.map(key => 
            client.set(key, `value-${key}`)
        ));
        
        const endTime = Date.now();
        console.log(`✅ Promise.all completed in ${endTime - startTime}ms`);
        console.log("All operations finished in parallel!\n");
        
    } finally {
        client.close();
    }
}

// Correct Pattern #3: Batch operations (best for GLIDE)
async function demonstrateBatchPattern() {
    console.log("=== Best: Batch operations ===");
    
    const client = await GlideClient.createClient({
        addresses: [{ host: process.env.VALKEY_HOST || "localhost", port: 6379 }],
    });

    try {
        const keys = ["key1", "key2", "key3"];
        
        console.log("Starting batch...");
        const startTime = Date.now();
        
        const batch = new Batch(false);
        keys.forEach(key => batch.set(key, `value-${key}`));
        
        const results = await client.exec(batch, true);
        
        const endTime = Date.now();
        console.log(`✅ Batch completed in ${endTime - startTime}ms`);
        console.log(`Set ${results.length} keys in single round-trip!\n`);
        
    } finally {
        client.close();
    }
}

// Anti-Pattern #2: Missing finally block
async function demonstrateMissingFinally() {
    console.log("=== Anti-Pattern: Missing finally block ===");
    
    const client = await GlideClient.createClient({
        addresses: [{ host: process.env.VALKEY_HOST || "localhost", port: 6379 }],
    });

    try {
        await client.set("test", "value");
        
        // Simulate error
        throw new Error("Simulated error");
        
        // ❌ This never runs if error occurs
        client.close();
        console.log("❌ Client closed (never reached)");
        
    } catch (err) {
        console.log(`Error caught: ${err.message}`);
        console.log("❌ Client NOT closed - resource leak!\n");
    }
}

// Correct Pattern: finally block ensures cleanup
async function demonstrateProperFinally() {
    console.log("=== Correct: finally block ===");
    
    const client = await GlideClient.createClient({
        addresses: [{ host: process.env.VALKEY_HOST || "localhost", port: 6379 }],
    });

    try {
        await client.set("test", "value");
        
        // Simulate error
        throw new Error("Simulated error");
        
    } catch (err) {
        console.log(`Error caught: ${err.message}`);
        
    } finally {
        client.close();
        console.log("✅ Client closed in finally block");
        console.log("Cleanup guaranteed even with error!\n");
    }
}

// Run all demonstrations
async function main() {
    console.log("=== Node.js GLIDE Anti-Pattern Demonstrations ===");
    
    try {
        await demonstrateForEachAntiPattern();
        await demonstrateForOfPattern();
        await demonstratePromiseAllPattern();
        await demonstrateBatchPattern();
        await demonstrateMissingFinally();
        await demonstrateProperFinally();
        
        console.log("=== All demonstrations complete ===");
    } catch (err) {
        console.error("Demo error:", err);
    }
}

main();
