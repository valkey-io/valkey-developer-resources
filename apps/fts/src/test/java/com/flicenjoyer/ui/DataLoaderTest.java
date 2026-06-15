package com.flicenjoyer.ui;

import static org.junit.jupiter.api.Assertions.*;

import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicReference;
import org.junit.jupiter.api.Test;

class DataLoaderTest {

  @Test
  void loadDoesNotBlockCallingThread() throws Exception {
    var loader = new DataLoader<String>();
    var started = new CountDownLatch(1);
    var done = new CountDownLatch(1);

    long before = System.nanoTime();
    loader.load(
        () -> {
          started.countDown();
          try {
            Thread.sleep(200);
          } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
          }
          return "result";
        },
        result -> done.countDown(),
        ex -> done.countDown());
    long elapsed = (System.nanoTime() - before) / 1_000_000;

    // load() should return almost immediately (< 50ms), not wait 200ms
    assertTrue(elapsed < 50, "load() blocked for " + elapsed + "ms, expected < 50ms");
    assertTrue(started.await(2, TimeUnit.SECONDS), "task should have started");
    assertTrue(done.await(2, TimeUnit.SECONDS), "task should have completed");
  }

  @Test
  void loadDeliversResultOnCompletion() throws Exception {
    var loader = new DataLoader<Integer>();
    var result = new AtomicReference<Integer>();
    var done = new CountDownLatch(1);

    loader.load(
        () -> 42,
        val -> {
          result.set(val);
          done.countDown();
        },
        ex -> done.countDown());

    assertTrue(done.await(2, TimeUnit.SECONDS));
    assertEquals(42, result.get());
  }

  @Test
  void loadDeliversFailureOnException() throws Exception {
    var loader = new DataLoader<String>();
    var error = new AtomicReference<Exception>();
    var done = new CountDownLatch(1);

    loader.load(
        () -> {
          throw new RuntimeException("boom");
        },
        val -> done.countDown(),
        ex -> {
          error.set(ex);
          done.countDown();
        });

    assertTrue(done.await(2, TimeUnit.SECONDS));
    assertNotNull(error.get());
    assertEquals("boom", error.get().getMessage());
  }

  @Test
  void cancelPreventsResultDelivery() throws Exception {
    var loader = new DataLoader<String>();
    var resultDelivered = new AtomicBoolean(false);
    var taskStarted = new CountDownLatch(1);
    var taskCanProceed = new CountDownLatch(1);
    var done = new CountDownLatch(1);

    loader.load(
        () -> {
          taskStarted.countDown();
          try {
            taskCanProceed.await(2, TimeUnit.SECONDS);
          } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
          }
          return "should not deliver";
        },
        val -> {
          resultDelivered.set(true);
          done.countDown();
        },
        ex -> done.countDown());

    assertTrue(taskStarted.await(2, TimeUnit.SECONDS));
    loader.cancel();
    taskCanProceed.countDown();

    // Give time for task to finish
    Thread.sleep(200);
    assertFalse(resultDelivered.get(), "cancelled task should not deliver result");
  }

  @Test
  void tasksAreSerializedNotConcurrent() throws Exception {
    var loader = new DataLoader<Integer>();
    var order = new java.util.concurrent.CopyOnWriteArrayList<Integer>();
    var done = new CountDownLatch(2);

    loader.load(
        () -> {
          try {
            Thread.sleep(100);
          } catch (InterruptedException e) {
          }
          order.add(1);
          return 1;
        },
        val -> done.countDown(),
        ex -> done.countDown());

    // Second load cancels first, but since executor is single-threaded,
    // second task waits for first to finish
    loader.load(
        () -> {
          order.add(2);
          return 2;
        },
        val -> done.countDown(),
        ex -> done.countDown());

    assertTrue(done.await(3, TimeUnit.SECONDS));
    // Task 1 should complete before task 2 starts (serialized)
    assertEquals(1, order.getFirst());
    assertEquals(2, order.get(1));
  }
}
