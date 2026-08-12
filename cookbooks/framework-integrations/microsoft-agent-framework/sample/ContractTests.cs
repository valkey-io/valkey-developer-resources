using Valkey.Glide;

namespace MicrosoftAgentFramework.Valkey.Sample;

public static class ContractTests
{
    public static async Task RunAsync(IConnectionMultiplexer connection)
    {
        await VerifyCleanupBehaviorAsync();

        var conversationId = $"contract-{Guid.NewGuid():N}";
        var responseId = $"contract-{Guid.NewGuid():N}";
        var history = new ChatHistoryStore(connection, maxMessages: 2);
        var stream = new AgentStreamStore(connection, maxLength: 100);
        await CleanupAsync(history, conversationId, stream, responseId);
        Exception? applicationException = null;
        try
        {
            await history.AppendAsync(conversationId, [new("user", "first"), new("assistant", "second"), new("user", "third")]);
            var messages = await history.ReadAsync(conversationId);
            Assert(messages.Count == 2 && messages[0].Content == "second" && messages[1].Content == "third", "List ordering or trimming failed.");
            Assert(await history.LengthAsync(conversationId) == 2, "List length failed.");

            var firstId = await stream.AppendAsync(responseId, new("first"));
            await stream.AppendAsync(responseId, new("second"));
            var replay = await stream.ReplayAsync(responseId);
            var resumed = await stream.ReplayAfterAsync(responseId, firstId);
            Assert(replay.Count == 2 && replay[0].Chunk.Content == "first", "Full stream replay failed.");
            Assert(resumed.Count == 1 && resumed[0].Chunk.Content == "second", "Exclusive stream replay failed.");
            Assert(await stream.LengthAsync(responseId) == 2, "Stream length failed.");
        }
        catch (Exception ex)
        {
            applicationException = ex;
            throw;
        }
        finally
        {
            await SampleCleanup.RunAsync(applicationException, Console.Error,
                () => history.DeleteAsync(conversationId),
                () => stream.DeleteAsync(responseId));
        }
    }

    private static async Task CleanupAsync(ChatHistoryStore history, string conversationId, AgentStreamStore stream, string responseId)
    {
        await SampleCleanup.RunAsync(null, Console.Error,
            () => history.DeleteAsync(conversationId),
            () => stream.DeleteAsync(responseId));
    }

    private static async Task VerifyCleanupBehaviorAsync()
    {
        var calls = new List<string>();
        var errors = new StringWriter();
        var applicationException = new InvalidOperationException("Application failed.");

        await SampleCleanup.RunAsync(applicationException, errors,
            () => RecordAsync(calls, "history", fail: true),
            () => RecordAsync(calls, "stream"),
            () => RecordAsync(calls, "connection"));

        Assert(calls.SequenceEqual(["history", "stream", "connection"]), "Cleanup did not attempt every operation.");
        Assert(errors.ToString().Contains("Application failed", StringComparison.Ordinal) == false, "Cleanup reporting replaced the application error.");
        Assert(errors.ToString().Contains("history cleanup failed", StringComparison.Ordinal), "Cleanup failure was not reported.");

        try
        {
            await SampleCleanup.RunAsync(null, TextWriter.Null, () => RecordAsync(calls, "cleanup", fail: true));
            throw new InvalidOperationException("Cleanup failure was not propagated.");
        }
        catch (AggregateException ex)
        {
            Assert(ex.InnerExceptions.Single().Message == "cleanup cleanup failed", "Cleanup failure was not preserved.");
        }
    }

    private static Task RecordAsync(List<string> calls, string name, bool fail = false)
    {
        calls.Add(name);
        return fail ? Task.FromException(new InvalidOperationException($"{name} cleanup failed")) : Task.CompletedTask;
    }

    private static void Assert(bool condition, string message)
    {
        if (!condition) throw new InvalidOperationException(message);
    }
}
