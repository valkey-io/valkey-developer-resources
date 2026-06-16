package com.flicenjoyer.ui;

import static org.junit.jupiter.api.Assertions.*;

import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicReference;
import org.junit.jupiter.api.Test;

class BackgroundTaskTest {

  @Test
  void successCallbackFires() throws Exception {
    var successCalled = new AtomicBoolean(false);
    var finallyCalled = new AtomicBoolean(false);
    var done = new CountDownLatch(1);

    var task =
        new BackgroundTask() {
          @Override
          protected void execute() {}

          @Override
          protected void onSuccess() {
            successCalled.set(true);
          }

          @Override
          protected void onFinally() {
            finallyCalled.set(true);
            done.countDown();
          }
        };
    task.start();

    assertTrue(done.await(3, TimeUnit.SECONDS));
    assertTrue(successCalled.get());
    assertTrue(finallyCalled.get());
  }

  @Test
  void failureCallbackFiresOnException() throws Exception {
    var failureCalled = new AtomicBoolean(false);
    var caughtMessage = new AtomicReference<String>();
    var done = new CountDownLatch(1);

    var task =
        new BackgroundTask() {
          @Override
          protected void execute() throws Exception {
            throw new RuntimeException("boom");
          }

          @Override
          protected void onFailure(Exception ex) {
            failureCalled.set(true);
            caughtMessage.set(ex.getMessage());
          }

          @Override
          protected void onFinally() {
            done.countDown();
          }
        };
    task.start();

    assertTrue(done.await(3, TimeUnit.SECONDS));
    assertTrue(failureCalled.get());
    assertEquals("boom", caughtMessage.get());
  }

  @Test
  void cancelAbortsCleanly() throws Exception {
    var executionStarted = new CountDownLatch(1);
    var cancelledCalled = new AtomicBoolean(false);
    var successCalled = new AtomicBoolean(false);
    var done = new CountDownLatch(1);

    var task =
        new BackgroundTask() {
          @Override
          protected void execute() throws Exception {
            executionStarted.countDown();
            // Simulate long work — will be interrupted by cancel
            Thread.sleep(10_000);
          }

          @Override
          protected void onSuccess() {
            successCalled.set(true);
          }

          @Override
          protected void onCancelled() {
            cancelledCalled.set(true);
          }

          @Override
          protected void onFinally() {
            done.countDown();
          }
        };
    task.start();

    assertTrue(executionStarted.await(2, TimeUnit.SECONDS));
    task.cancel();

    assertTrue(done.await(3, TimeUnit.SECONDS));
    assertTrue(task.isCancelled());
    assertFalse(successCalled.get());
  }
}
