package com.flicenjoyer.service;

import java.util.Arrays;

/** Measures operation latency with median, p95, p99, and ops/sec metrics. */
public final class BenchmarkService {
  private BenchmarkService() {}

  @FunctionalInterface
  public interface BenchmarkTask {
    void run() throws Exception;
  }

  public record BenchmarkResult(double medianMs, double p95Ms, double p99Ms, double opsPerSecond) {}

  public static BenchmarkResult benchmark(BenchmarkTask task, int iterations) throws Exception {
    return benchmark(task, iterations, null);
  }

  public static BenchmarkResult benchmark(
      BenchmarkTask task, int iterations, java.util.function.IntConsumer onProgress)
      throws Exception {
    long[] timings = new long[iterations];
    for (int i = 0; i < iterations; i++) {
      long start = System.nanoTime();
      task.run();
      timings[i] = System.nanoTime() - start;
      if (onProgress != null) onProgress.accept(i + 1);
    }
    Arrays.sort(timings);
    double medianMs = timings[iterations / 2] / 1_000_000.0;
    double p95Ms = timings[(int) (iterations * 0.95)] / 1_000_000.0;
    double p99Ms = timings[(int) (iterations * 0.99)] / 1_000_000.0;
    long totalNs = Arrays.stream(timings).sum();
    double opsPerSecond = iterations / (totalNs / 1_000_000_000.0);
    return new BenchmarkResult(medianMs, p95Ms, p99Ms, opsPerSecond);
  }
}
