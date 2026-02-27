using Valkey.Glide;
using Valkey.Glide.Pipeline;
using static Valkey.Glide.ConnectionConfiguration;

class BatchPipeline
{
    static async Task Main()
    {
        var host = Environment.GetEnvironmentVariable("VALKEY_HOST") ?? "localhost";
        
        var config = new StandaloneClientConfigurationBuilder()
            .WithAddress(host, 6379)
            .Build();

        await using var client = await GlideClient.CreateClient(config);
        Console.WriteLine("✓ Connected");

        // Atomic batch (transaction)
        var batch = new Batch(atomic: true);
        batch.StringSet("counter", "0");
        batch.StringIncrement("counter");
        batch.StringIncrement("counter");
        batch.StringGet("counter");
        
        var results = await client.Exec(batch, raiseOnError: true);
        Console.WriteLine($"✓ Atomic batch: counter={results![3]}");

        // Non-atomic pipeline
        var pipeline = new Batch(atomic: false);
        pipeline.StringSet("key1", "value1");
        pipeline.StringSet("key2", "value2");
        pipeline.StringSet("key3", "value3");
        pipeline.StringGet("key1");
        pipeline.StringGet("key2");
        
        var pipeResults = await client.Exec(pipeline, raiseOnError: true);
        Console.WriteLine($"✓ Pipeline: executed {pipeResults!.Length} commands");

        Console.WriteLine("✓ Batch operations completed");
    }
}
