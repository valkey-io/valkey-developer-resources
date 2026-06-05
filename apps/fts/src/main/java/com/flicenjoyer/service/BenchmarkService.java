package com.flicenjoyer.service;

import java.util.Arrays;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicLong;

/** Measures operation throughput under concurrent load and single-thread latency. */
public final class BenchmarkService {
  private BenchmarkService() {}

  @FunctionalInterface
  public interface BenchmarkTask {
    void run() throws Exception;
  }

  public record BenchmarkResult(double medianMs, double p95Ms, double p99Ms, double opsPerSecond) {}

  /** Result of a concurrent load comparison between DB and Valkey. */
  public record ConcurrentComparisonResult(
      double dbOpsPerSecond, double valkeyOpsPerSecond, double speedup, int threads) {}

  /**
   * Runs a task concurrently with N threads, each performing opsPerThread operations. Includes a
   * warmup phase (first 10% discarded). Returns aggregate throughput (total ops / wall-clock time).
   */
  public static double concurrentThroughput(
      BenchmarkTask task, int threads, int opsPerThread, java.util.function.IntConsumer onProgress)
      throws InterruptedException {
    int warmupOps = Math.max(1, opsPerThread / 10);
    int timedOps = opsPerThread - warmupOps;
    int totalTimedOps = threads * timedOps;
    var completed = new AtomicInteger(0);

    // Warmup phase — not timed
    var warmupLatch = new CountDownLatch(threads);
    ExecutorService warmupPool = Executors.newFixedThreadPool(threads);
    for (int t = 0; t < threads; t++) {
      warmupPool.submit(
          () -> {
            try {
              for (int i = 0; i < warmupOps; i++) task.run();
            } catch (Exception e) {
              java.util.logging.Logger.getLogger(BenchmarkService.class.getName())
                  .fine("[bench] Warmup error: " + e.getMessage());
            } finally {
              warmupLatch.countDown();
            }
          });
    }
    warmupLatch.await();
    warmupPool.shutdown();
    warmupPool.awaitTermination(5, java.util.concurrent.TimeUnit.SECONDS);

    // Timed phase
    var latch = new CountDownLatch(threads);
    var errors = new AtomicInteger(0);
    ExecutorService pool = Executors.newFixedThreadPool(threads);

    long startNs = System.nanoTime();
    for (int t = 0; t < threads; t++) {
      pool.submit(
          () -> {
            try {
              for (int i = 0; i < timedOps; i++) {
                task.run();
                int done = completed.incrementAndGet();
                if (onProgress != null && done % 50 == 0) {
                  onProgress.accept(done);
                }
              }
            } catch (Exception e) {
              errors.incrementAndGet();
              java.util.logging.Logger.getLogger(BenchmarkService.class.getName())
                  .warning("[bench] Thread error: " + e.getMessage());
            } finally {
              latch.countDown();
            }
          });
    }
    latch.await();
    long elapsedNs = System.nanoTime() - startNs;
    pool.shutdown();
    pool.awaitTermination(5, java.util.concurrent.TimeUnit.SECONDS);

    int actualCompleted = completed.get();
    if (onProgress != null) onProgress.accept(actualCompleted);
    return actualCompleted / (elapsedNs / 1_000_000_000.0);
  }

  /**
   * Runs both DB and Valkey tasks under concurrent load (with warmup), returns comparison.
   */
  public static ConcurrentComparisonResult concurrentComparison(
      BenchmarkTask dbTask,
      BenchmarkTask valkeyTask,
      int threads,
      int opsPerThread,
      java.util.function.IntConsumer onProgress)
      throws InterruptedException {
    int timedOps = threads * (opsPerThread - Math.max(1, opsPerThread / 10));
    int grandTotal = timedOps * 2;

    double dbOps =
        concurrentThroughput(
            dbTask,
            threads,
            opsPerThread,
            done -> {
              if (onProgress != null) onProgress.accept(done);
            });

    double valkeyOps =
        concurrentThroughput(
            valkeyTask,
            threads,
            opsPerThread,
            done -> {
              if (onProgress != null) onProgress.accept(timedOps + done);
            });

    double speedup = valkeyOps / dbOps;
    return new ConcurrentComparisonResult(dbOps, valkeyOps, speedup, threads);
  }

  /** Single-threaded benchmark for latency percentiles. */
  public static BenchmarkResult benchmark(BenchmarkTask task, int iterations) throws Exception {
    return benchmark(task, iterations, null);
  }

  /** Single-threaded benchmark for latency percentiles with progress callback. */
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
