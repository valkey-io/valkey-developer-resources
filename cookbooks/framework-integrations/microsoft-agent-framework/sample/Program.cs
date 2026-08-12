using MicrosoftAgentFramework.Valkey.Sample;
using Valkey.Glide;

var connection = await ValkeyConnection.ConnectAsync();
ChatHistoryStore? history = null;
AgentStreamStore? stream = null;
string? conversation = null;
string? response = null;
Exception? applicationException = null;
try
{
    if (args.Contains("--contract-tests", StringComparer.Ordinal))
    {
        await ContractTests.RunAsync(connection);
        Console.WriteLine("Contract tests passed.");
        return;
    }

    conversation = Environment.GetEnvironmentVariable("CONVERSATION_ID") ?? $"demo-{Guid.NewGuid():N}";
    response = Environment.GetEnvironmentVariable("RESPONSE_ID") ?? $"demo-{Guid.NewGuid():N}";
    history = new ChatHistoryStore(connection, maxMessages: ReadLimit("CHAT_HISTORY_LIMIT", 20));
    stream = new AgentStreamStore(connection, maxLength: ReadLimit("MAX_LENGTH", 100));
    await history.AppendAsync(conversation, [new("user", "Remember that Valkey stores our history."), new("assistant", "I will remember it.")]);
    Console.WriteLine($"History messages: {(await history.ReadAsync(conversation)).Count}");
    var first = await stream.AppendAsync(response, new("first token"));
    await stream.AppendAsync(response, new("second token"));
    var continuation = Environment.GetEnvironmentVariable("CONTINUATION_ID");
    var resumeAfter = string.IsNullOrWhiteSpace(continuation) ? first : new ValkeyValue(continuation);
    Console.WriteLine($"Stream entries: {await stream.LengthAsync(response)}; after continuation: {(await stream.ReplayAfterAsync(response, resumeAfter)).Count}");
}
catch (Exception ex)
{
    applicationException = ex;
    throw;
}
finally
{
    var cleanupActions = new List<Func<Task>> { () => connection.CloseAsync() };
    if (stream is not null && response is not null) cleanupActions.Insert(0, () => stream.DeleteAsync(response));
    if (history is not null && conversation is not null) cleanupActions.Insert(0, () => history.DeleteAsync(conversation));
    await SampleCleanup.RunAsync(applicationException, Console.Error, cleanupActions.ToArray());
}

static int ReadLimit(string name, int fallback)
{
    return int.TryParse(Environment.GetEnvironmentVariable(name), out var value) && value > 0 ? value : fallback;
}
