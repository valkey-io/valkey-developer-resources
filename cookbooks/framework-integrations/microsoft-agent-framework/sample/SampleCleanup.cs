namespace MicrosoftAgentFramework.Valkey.Sample;

public static class SampleCleanup
{
    public static async Task RunAsync(Exception? applicationException, TextWriter errorWriter, params Func<Task>[] cleanupActions)
    {
        var cleanupFailures = new List<Exception>();
        foreach (var cleanupAction in cleanupActions)
        {
            try
            {
                await cleanupAction().ConfigureAwait(false);
            }
            catch (Exception ex)
            {
                cleanupFailures.Add(ex);
            }
        }

        if (cleanupFailures.Count == 0) return;

        var cleanupException = new AggregateException("One or more cleanup operations failed.", cleanupFailures);
        if (applicationException is not null)
        {
            await errorWriter.WriteLineAsync($"Cleanup failed while preserving the application error: {cleanupException}").ConfigureAwait(false);
            return;
        }

        throw cleanupException;
    }
}
