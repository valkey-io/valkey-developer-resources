using System.Text.Json;

namespace MicrosoftAgentFramework.Valkey.Sample;

public static class JsonContracts
{
    public static JsonSerializerOptions Options { get; } = new(JsonSerializerDefaults.Web);
}
