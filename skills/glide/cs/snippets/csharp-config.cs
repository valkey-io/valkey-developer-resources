// C# GLIDE Configuration Template
// Optimized for production web applications
// See: https://github.com/valkey-io/valkey-glide-csharp

using Valkey.Glide;
using static Valkey.Glide.ConnectionConfiguration;

public static class GlideConfig
{
    // Standalone Client Configuration
    public static StandaloneClientConfiguration StandaloneConfig()
    {
        return new StandaloneClientConfigurationBuilder()
            .WithAddress("localhost", 6379)

            // Request timeout (500ms recommended for web apps)
            .WithRequestTimeout(TimeSpan.FromMilliseconds(500))

            // Connection retry strategy
            .WithConnectionRetryStrategy(
                numberOfRetries: 10,
                factor: 500,        // Base delay in ms
                exponentBase: 2     // Exponential backoff
            )

            // Client name for debugging
            .WithClientName("my-app-client")

            // Lazy connect for serverless/Lambda
            .WithLazyConnect(false)  // Set to true for Lambda

            .Build();
    }

    // Cluster Client Configuration
    public static ClusterClientConfiguration ClusterConfig()
    {
        return new ClusterClientConfigurationBuilder()
            .WithAddress("cluster.endpoint.cache.amazonaws.com", 6379)

            // Request timeout
            .WithRequestTimeout(TimeSpan.FromMilliseconds(500))

            // AZ Affinity for cost optimization (read-heavy workloads)
            .WithReadFrom(new ReadFrom(ReadFromStrategy.AzAffinity, "us-east-1a"))

            // Connection retry strategy
            .WithConnectionRetryStrategy(
                numberOfRetries: 10,
                factor: 500,
                exponentBase: 2
            )

            // Client name
            .WithClientName("my-app-cluster-client")

            .Build();
    }

    // Create clients (do this once at application startup)
    public static async Task<(GlideClient Standalone, GlideClusterClient Cluster)> CreateClientsAsync()
    {
        var standalone = await GlideClient.CreateClient(StandaloneConfig());
        var cluster = await GlideClusterClient.CreateClient(ClusterConfig());

        return (standalone, cluster);
    }

    // Graceful shutdown
    public static async ValueTask CloseClientsAsync(
        GlideClient standalone,
        GlideClusterClient cluster)
    {
        await standalone.DisposeAsync();
        await cluster.DisposeAsync();
    }
}
