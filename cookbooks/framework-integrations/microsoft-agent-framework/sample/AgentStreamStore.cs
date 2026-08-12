using System.Text.Json;
using Valkey.Glide;

namespace MicrosoftAgentFramework.Valkey.Sample;

public sealed record StreamChunk(string Content);
public sealed record StoredStreamEntry(ValkeyValue Id, StreamChunk Chunk);

public sealed class AgentStreamStore(IConnectionMultiplexer connection, int? maxLength = null)
{
    private readonly IDatabase database = connection.GetDatabase();
    private readonly int? maxLength = maxLength;

    public async Task<ValkeyValue> AppendAsync(string responseId, StreamChunk chunk, CancellationToken cancellationToken = default)
    {
        var content = Serialize(chunk);
        cancellationToken.ThrowIfCancellationRequested();
        var key = Key(responseId);
        var id = await database.StreamAddAsync(key, new[] { new NameValueEntry("content", content) }).ConfigureAwait(false);
        if (maxLength is { } limit) await database.StreamTrimAsync(key, limit, useApproximateMaxLength: true).ConfigureAwait(false);
        return id;
    }

    public Task<IReadOnlyList<StoredStreamEntry>> ReplayAsync(string responseId) => ReadRangeAsync(Key(responseId), "-");
    public Task<IReadOnlyList<StoredStreamEntry>> ReplayAfterAsync(string responseId, ValkeyValue lastId) => ReadRangeAsync(Key(responseId), $"({lastId}");
    public Task<long> LengthAsync(string responseId) => database.StreamLengthAsync(Key(responseId));
    public Task<bool> DeleteAsync(string responseId) => database.KeyDeleteAsync(Key(responseId));
    private static string Key(string id) => $"agent_stream:{ValidateId(id)}";
    private static string ValidateId(string value) => string.IsNullOrWhiteSpace(value) ? throw new ArgumentException("An identifier is required.", nameof(value)) : value;
    private static string Serialize(StreamChunk chunk)
    {
        if (chunk is null || chunk.Content is null) throw new ArgumentException("Content is required.", nameof(chunk));
        return JsonSerializer.Serialize(chunk, JsonContracts.Options);
    }

    private async Task<IReadOnlyList<StoredStreamEntry>> ReadRangeAsync(string key, string minId)
    {
        var entries = await database.StreamRangeAsync(key, minId: minId, maxId: "+").ConfigureAwait(false);
        return entries.Select(Parse).ToArray();
    }

    private static StoredStreamEntry Parse(StreamEntry entry)
    {
        var content = entry["content"].ToString();
        if (string.IsNullOrWhiteSpace(content)) throw new InvalidDataException("Stream entry is missing content.");
        try
        {
            var chunk = JsonSerializer.Deserialize<StreamChunk>(content, JsonContracts.Options);
            if (chunk is null || chunk.Content is null) throw new InvalidDataException("Stream entry content is invalid.");
            return new StoredStreamEntry(entry.Id, chunk);
        }
        catch (JsonException ex) { throw new InvalidDataException("Stream entry content is not valid JSON.", ex); }
    }
}
