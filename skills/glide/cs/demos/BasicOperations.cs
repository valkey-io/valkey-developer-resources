using Valkey.Glide;
using static Valkey.Glide.ConnectionConfiguration;

class BasicOperations
{
    static async Task Main()
    {
        var host = Environment.GetEnvironmentVariable("VALKEY_HOST") ?? "localhost";
        
        // Create standalone client
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
        await client.HashSetAsync("user:1000", "email", "alice@example.com");
        var name = await client.HashGetAsync("user:1000", "name");
        var allFields = await client.HashGetAllAsync("user:1000");
        Console.WriteLine($"✓ Hash: name={name}, fields={allFields.Count}");

        // List operations
        await client.ListPushAsync("tasks", "task1", ListDirection.Left);
        await client.ListPushAsync("tasks", "task2", ListDirection.Left);
        var task = await client.ListPopAsync("tasks", ListDirection.Right);
        Console.WriteLine($"✓ List: popped={task}");

        // Set operations
        await client.SetAddAsync("tags", "csharp");
        await client.SetAddAsync("tags", "dotnet");
        var isMember = await client.SetIsMemberAsync("tags", "csharp");
        var members = await client.SetMembersAsync("tags");
        Console.WriteLine($"✓ Set: isMember={isMember}, count={members.Count}");

        // Error handling
        try
        {
            await client.StringGetAsync("nonexistent");
        }
        catch (ConnectionException ex)
        {
            Console.WriteLine($"Connection error: {ex.Message}");
        }
        catch (TimeoutException ex)
        {
            Console.WriteLine($"Timeout: {ex.Message}");
        }
        catch (ValkeyException ex)
        {
            Console.WriteLine($"Valkey error: {ex.Message}");
        }

        Console.WriteLine("✓ All operations completed");
    }
}
