using System.Text.Json;
using Valkey.Glide;

namespace MicrosoftAgentFramework.Valkey.Sample;

public sealed record FrameworkMessage(string Role, string Content);

public sealed class ChatHistoryStore(IConnectionMultiplexer connection, int? maxMessages = null)
{
    private readonly IDatabase database = connection.GetDatabase();
    private readonly int? maxMessages = maxMessages;

    public async Task AppendAsync(string conversationId, IEnumerable<FrameworkMessage> messages, CancellationToken cancellationToken = default)
    {
        var values = messages.Select(Serialize).Select(static value => (ValkeyValue)value).ToArray();
        if (values.Length == 0) return;
        cancellationToken.ThrowIfCancellationRequested();
        var key = Key(conversationId);
        await database.ListRightPushAsync(key, values).ConfigureAwait(false);
        if (maxMessages is { } limit) await database.ListTrimAsync(key, -limit, -1).ConfigureAwait(false);
    }

    public async Task<IReadOnlyList<FrameworkMessage>> ReadAsync(string conversationId, CancellationToken cancellationToken = default)
    {
        cancellationToken.ThrowIfCancellationRequested();
        var values = await database.ListRangeAsync(Key(conversationId)).ConfigureAwait(false);
        return values.Select(Parse).ToArray();
    }

    public Task<long> LengthAsync(string conversationId) => database.ListLengthAsync(Key(conversationId));
    public Task<bool> DeleteAsync(string conversationId) => database.KeyDeleteAsync(Key(conversationId));
    private static string Key(string id) => $"chat_history:{ValidateId(id)}";
    private static string ValidateId(string value) => string.IsNullOrWhiteSpace(value) ? throw new ArgumentException("An identifier is required.", nameof(value)) : value;
    private static string Serialize(FrameworkMessage message)
    {
        if (message is null || string.IsNullOrWhiteSpace(message.Role) || message.Content is null) throw new ArgumentException("Messages require a role and content.", nameof(message));
        return JsonSerializer.Serialize(message, JsonContracts.Options);
    }
    private static FrameworkMessage Parse(ValkeyValue value)
    {
        try
        {
            var message = JsonSerializer.Deserialize<FrameworkMessage>(value.ToString(), JsonContracts.Options);
            if (message is null || string.IsNullOrWhiteSpace(message.Role) || message.Content is null) throw new InvalidDataException("Stored chat message is missing role or content.");
            return message;
        }
        catch (JsonException ex) { throw new InvalidDataException("Stored chat message is not valid JSON.", ex); }
    }
}
