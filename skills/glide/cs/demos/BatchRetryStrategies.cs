using System;
using System.Threading.Tasks;
using Valkey.Glide;
using Valkey.Glide.Pipeline;
using static Valkey.Glide.ConnectionConfiguration;

class BatchRetryStrategies
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
        
        Console.WriteLine("=== Batch Operation Retry Strategies ===\n");
        Console.WriteLine("Note: C# GLIDE v0.9.0 does not support batch retry strategies.");
        Console.WriteLine("This feature may be added in future versions.\n");
        
        Console.WriteLine("Expected API (when available):");
        Console.WriteLine("  var options = new ClusterBatchOptions {");
        Console.WriteLine("      RetryStrategy = new BatchRetryStrategy {");
        Console.WriteLine("          RetryServerError = true,");
        Console.WriteLine("          RetryConnectionError = false");
        Console.WriteLine("      }");
        Console.WriteLine("  };");
        Console.WriteLine("  var results = await client.Exec(batch, raiseOnError: true, options);");
        Console.WriteLine();
        
        // Demonstrate basic batch operation without retry strategies
        Console.WriteLine("Demonstrating basic batch operation:");
        var batch = new ClusterBatch(isAtomic: false);
        batch.StringSetAsync("{user:1}:name", "Alice");
        batch.StringSetAsync("{user:1}:email", "alice@example.com");
        batch.StringGetAsync("{user:1}:name");
        
        var results = await client.Exec(batch, raiseOnError: true);
        Console.WriteLine($"✓ Results: [{string.Join(", ", results!)}]");
        Console.WriteLine();
        
        Console.WriteLine("For production resilience, implement retry logic at application level.");
        Console.WriteLine("See SKILL.md for retry strategy decision matrix (when feature becomes available).");
    }
}
