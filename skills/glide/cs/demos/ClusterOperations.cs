using System;
using System.Threading.Tasks;
using Valkey.Glide;
using Valkey.Glide.Pipeline;
using static Valkey.Glide.ConnectionConfiguration;

class ClusterOperations
{
    static async Task Main()
    {
        var host = Environment.GetEnvironmentVariable("VALKEY_HOST") ?? "localhost";
        
        var config = new ClusterClientConfigurationBuilder()
            .WithAddress(host, 7000)
            .WithAddress(host, 7001)
            .WithAddress(host, 7002)
            .Build();

        await using var client = await GlideClusterClient.CreateClient(config);
        Console.WriteLine("✓ Connected to cluster");

        // Hash tags ensure same slot
        await client.StringSetAsync("{user}:1:name", "Alice");
        await client.StringSetAsync("{user}:1:email", "alice@example.com");
        await client.StringSetAsync("{user}:2:name", "Bob");
        
        var name1 = await client.StringGetAsync("{user}:1:name");
        var name2 = await client.StringGetAsync("{user}:2:name");
        Console.WriteLine($"✓ Hash tags: {name1}, {name2}");

        // Cluster batch (atomic requires same slot)
        var batch = new ClusterBatch(isAtomic: true);
        batch.StringSetAsync("{order}:100:status", "pending");
        batch.StringSetAsync("{order}:100:total", "99.99");
        batch.StringGetAsync("{order}:100:status");
        
        var results = await client.Exec(batch, raiseOnError: true);
        Console.WriteLine($"✓ Cluster batch: status={results![2]}");

        // Non-atomic pipeline (can span slots)
        var pipeline = new ClusterBatch(isAtomic: false);
        pipeline.StringSetAsync("product:1", "Widget");
        pipeline.StringSetAsync("product:2", "Gadget");
        pipeline.StringSetAsync("product:3", "Doohickey");
        
        var pipeResults = await client.Exec(pipeline, raiseOnError: true);
        Console.WriteLine($"✓ Pipeline: {pipeResults!.Length} commands across slots");

        Console.WriteLine("✓ Cluster operations completed");
    }
}
