using Valkey.Glide;

namespace MicrosoftAgentFramework.Valkey.Sample;

public static class ValkeyConnection
{
    public static async Task<IConnectionMultiplexer> ConnectAsync()
    {
        var host = Environment.GetEnvironmentVariable("VALKEY_HOST") ?? "127.0.0.1";
        var port = int.Parse(Environment.GetEnvironmentVariable("VALKEY_PORT") ?? "6379");
        var timeout = int.Parse(Environment.GetEnvironmentVariable("VALKEY_REQUEST_TIMEOUT_MS") ?? "5000");
        var options = new ConfigurationOptions { ResponseTimeout = timeout };
        options.EndPoints.Add(host, port);
        return await ConnectionMultiplexer.ConnectAsync(options).ConfigureAwait(false);
    }
}
