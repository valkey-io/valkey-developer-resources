using System;
using System.Threading.Tasks;
using Valkey.Glide;
using static Valkey.Glide.ConnectionConfiguration;

class BasicOperations
{
    static async Task Main()
    {
        var host = Environment.GetEnvironmentVariable("VALKEY_HOST") ?? "localhost";
        
        var config = new StandaloneClientConfigurationBuilder()
            .WithAddress(host, 6379)
            .WithRequestTimeout(TimeSpan.FromSeconds(10))
            .Build();

        await using var client = await GlideClient.CreateClient(config);
        Console.WriteLine("✓ Connected to Valkey");

        // String operations
        await client.StringSetAsync("greeting", "Hello, Valkey!");
        var greeting = await client.StringGetAsync("greeting");
        Console.WriteLine($"✓ String: {greeting}");

        // Hash operations
        await client.HashSetAsync("user:1000", "name", "Alice");
        var name = await client.HashGetAsync("user:1000", "name");
        Console.WriteLine($"✓ Hash: name={name}");

        // List operations
        await client.ListLeftPushAsync("tasks", ["task1", "task2"]);
        var task = await client.ListRightPopAsync("tasks");
        Console.WriteLine($"✓ List: popped={task}");

        // Set operations
        await client.SetAddAsync("tags", ["csharp", "dotnet"]);
        var members = await client.SetMembersAsync("tags");
        Console.WriteLine($"✓ Set: count={members.Length}");

        Console.WriteLine("✓ All operations completed");
    }
}
