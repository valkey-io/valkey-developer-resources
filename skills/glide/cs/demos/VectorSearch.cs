using System.Text;
using Valkey.Glide;
using static Valkey.Glide.ConnectionConfiguration;

class VectorSearch
{
    static async Task Main()
    {
        var host = Environment.GetEnvironmentVariable("VALKEY_HOST") ?? "localhost";
        
        var config = new StandaloneClientConfigurationBuilder()
            .WithAddress(host, 6379)
            .Build();

        await using var client = await GlideClient.CreateClient(config);
        Console.WriteLine("✓ Connected");

        var indexName = "products_idx";
        
        // Cleanup
        try
        {
            await client.CustomCommand(["FT.DROPINDEX", indexName]);
            await client.Del(["product:1", "product:2"]);
        }
        catch { }

        // Create index with vector field
        await client.CustomCommand([
            "FT.CREATE", indexName,
            "ON", "HASH",
            "PREFIX", "1", "product:",
            "SCHEMA",
            "name", "TEXT",
            "description_vector", "VECTOR", "HNSW", "6",
            "TYPE", "FLOAT32",
            "DIM", "3",
            "DISTANCE_METRIC", "L2"
        ]);
        Console.WriteLine("✓ Index created");

        // Create vectors as byte arrays
        var vector1 = ToBytes([1.0f, 2.0f, 3.0f]);
        var vector2 = ToBytes([4.0f, 5.0f, 6.0f]);

        // Store documents with vectors
        await client.HashSetAsync("product:1", new Dictionary<string, GlideString>
        {
            ["name"] = "Product A",
            ["description_vector"] = vector1
        });
        await client.HashSetAsync("product:2", new Dictionary<string, GlideString>
        {
            ["name"] = "Product B",
            ["description_vector"] = vector2
        });
        Console.WriteLine("✓ Documents stored");

        // Vector search
        var queryVector = ToBytes([1.5f, 2.5f, 3.5f]);
        var results = await client.CustomCommand([
            "FT.SEARCH", indexName,
            "*=>[KNN 2 @description_vector $vec]",
            "PARAMS", "2", "vec", queryVector,
            "RETURN", "1", "name",
            "DIALECT", "2"
        ]);
        
        Console.WriteLine($"✓ Search results: {results}");

        // Cleanup
        await client.CustomCommand(["FT.DROPINDEX", indexName]);
        await client.Del(["product:1", "product:2"]);
        Console.WriteLine("✓ Vector search completed");
    }

    static byte[] ToBytes(float[] vector)
    {
        var bytes = new byte[vector.Length * sizeof(float)];
        Buffer.BlockCopy(vector, 0, bytes, 0, bytes.Length);
        return bytes;
    }
}
