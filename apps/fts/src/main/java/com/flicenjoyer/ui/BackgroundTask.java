package com.flicenjoyer.ui;

import java.util.concurrent.atomic.AtomicBoolean;
import java.util.logging.Logger;

/**
 * A cancellable background task that runs work off the JavaFX Application Thread and delivers
 * results back on it. Cancel via {@link #cancel()} — the task checks {@link #isCancelled()}
 * periodically and skips completion callbacks if cancelled.
 */
public abstract class BackgroundTask {

  private static final Logger LOG = Logger.getLogger(BackgroundTask.class.getName());
  private static final java.util.concurrent.ExecutorService EXECUTOR = UiExecutors.BACKGROUND;

  private final AtomicBoolean cancelled = new AtomicBoolean(false);
  private java.util.concurrent.Future<?> future;

  /** Override to perform background work. Check {@link #isCancelled()} periodically. */
  protected abstract void execute() throws Exception;

  /** Called on the FX thread when {@link #execute()} completes successfully. */
  protected void onSuccess() {}

  /** Called on the FX thread when {@link #execute()} throws. */
  protected void onFailure(Exception ex) {}

  /** Called on the FX thread when the task is cancelled. */
  protected void onCancelled() {}

  /** Called on the FX thread after completion, failure, or cancellation — always runs. */
  protected void onFinally() {}

  public void start() {
    cancelled.set(false);
    future =
        EXECUTOR.submit(
            () -> {
              try {
                execute();
                if (!cancelled.get()) {
                  FxThread.run(
                      () -> {
                        try {
                          onSuccess();
                        } finally {
                          onFinally();
                        }
                      });
                } else {
                  FxThread.run(
                      () -> {
                        try {
                          onCancelled();
                        } finally {
                          onFinally();
                        }
                      });
                }
              } catch (Exception ex) {
                if (ex instanceof InterruptedException) {
                  Thread.currentThread().interrupt();
                }
                if (!cancelled.get()) {
                  LOG.warning("[task] Failed: " + ex.getMessage());
                  FxThread.run(
                      () -> {
                        try {
                          onFailure(ex);
                        } finally {
                          onFinally();
                        }
                      });
                } else {
                  FxThread.run(this::onFinally);
                }
              }
            });
  }

  public void cancel() {
    cancelled.set(true);
    if (future != null) {
      future.cancel(true);
    }
  }

  public boolean isCancelled() {
    return cancelled.get();
  }
}
