package com.flicenjoyer.service;

import static org.junit.jupiter.api.Assertions.*;

import org.junit.jupiter.api.Test;

class BenchmarkServiceTest {

  @Test
  void benchmarkComputesStatistics() throws Exception {
    BenchmarkService.BenchmarkResult result =
        BenchmarkService.benchmark(
            () -> {
              // simulate ~1ms work
              Thread.sleep(1);
            },
            100);

    assertTrue(result.medianMs() > 0);
    assertTrue(result.p95Ms() >= result.medianMs());
    assertTrue(result.p99Ms() >= result.p95Ms());
    assertTrue(result.opsPerSecond() > 0);
  }

  @Test
  void benchmarkHandlesZeroWorkTask() throws Exception {
    BenchmarkService.BenchmarkResult result = BenchmarkService.benchmark(() -> {}, 50);

    assertTrue(result.medianMs() >= 0);
    assertTrue(result.opsPerSecond() > 0);
  }
}
