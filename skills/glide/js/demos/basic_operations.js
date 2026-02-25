const { GlideClient } = require("@valkey/valkey-glide");

async function main() {
    // Create client configuration
    const client = await GlideClient.createClient({
        addresses: [{ host: process.env.VALKEY_HOST, port: 6379 }],
        requestTimeout: 10000,
    });

    try {
        // Set and get
        await client.set("hello", "world");
        const value = await client.get("hello");
        console.log("GET hello:", value);

        // Error handling - wrong type operation
        await client.set("mykey", "string_value");
        try {
            await client.lpop("mykey");
        } catch (err) {
            console.log("Expected error (WRONGTYPE):", err.message);
        }

        console.log("Basic operations completed");
    } finally {
        client.close();
    }
}

main().catch(console.error);
