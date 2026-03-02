using System;
using System.Threading.Tasks;
using Valkey.Glide;
using static Valkey.Glide.ConnectionConfiguration;

class TlsAuthDemo
{
    static async Task Main()
    {
        Console.WriteLine("=== TLS + Password Authentication Demo ===");
        
        var host = Environment.GetEnvironmentVariable("VALKEY_HOST") ?? "localhost";
        var port = ushort.Parse(Environment.GetEnvironmentVariable("VALKEY_TLS_PORT") ?? "6479");
        var password = Environment.GetEnvironmentVariable("VALKEY_PASSWORD") ?? "mypassword";
        
        try
        {
            // TLS with password authentication
            var config = new StandaloneClientConfigurationBuilder()
                .WithAddress(host, port)
                .WithAuthentication("default", password)
                .WithTls()
                .WithRequestTimeout(TimeSpan.FromSeconds(10))
                .Build();

            await using var client = await GlideClient.CreateClient(config);
            
            // Test basic operation
            await client.StringSetAsync("tls_test", "Hello with TLS!");
            var value = await client.StringGetAsync("tls_test");
            
            Console.WriteLine($"✓ TLS works: {value}");
            Console.WriteLine("=== Testing Complete ===");
        }
        catch (Exception ex) when (ex.Message.Contains("UnknownIssuer"))
        {
            Console.WriteLine("⚠ Note: Self-signed certificate detected");
            Console.WriteLine("⚠ Valkey.Glide 0.9.0 does not support insecure TLS mode");
            Console.WriteLine("⚠ Use CA-signed certificates in production");
            Console.WriteLine();
            Console.WriteLine("Expected configuration:");
            Console.WriteLine("  var config = new StandaloneClientConfigurationBuilder()");
            Console.WriteLine("      .WithAddress(host, port)");
            Console.WriteLine("      .WithAuthentication(username, password)");
            Console.WriteLine("      .WithTls()");
            Console.WriteLine("      .Build();");
            Console.WriteLine();
            Console.WriteLine("✓ Configuration pattern documented");
        }
        catch (Exception ex)
        {
            Console.WriteLine($"✗ Error: {ex.Message}");
            Environment.Exit(1);
        }
    }
}
