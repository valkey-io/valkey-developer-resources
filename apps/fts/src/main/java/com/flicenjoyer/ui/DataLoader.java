package com.flicenjoyer.ui;

import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.function.Consumer;
import java.util.logging.Logger;

/**
 * Serialized background data loader. Runs data-fetching tasks on a single-thread executor so they
 * never overlap, keeping the FX thread free. Supports cancellation and delivers results on the FX
 * thread.
 *
 * @param <T> the result type
 */
public class DataLoader<T> {

  private static final Logger LOG = Logger.getLogger(DataLoader.class.getName());
  private static final ExecutorService EXECUTOR =
      Executors.newSingleThreadExecutor(
          r -> {
            var t = new Thread(r, "data-loader");
            t.setDaemon(true);
            return t;
          });

  private final AtomicBoolean cancelled = new AtomicBoolean(false);
  private Future<?> future;

  @FunctionalInterface
  public interface ThrowingSupplier<T> {
    T get() throws Exception;
  }

  /**
   * Loads data asynchronously.
   *
   * @param supplier fetches data on the background thread (may throw)
   * @param onSuccess receives the result on the FX thread
   * @param onFailure receives the exception on the FX thread
   */
  public void load(
      ThrowingSupplier<T> supplier, Consumer<T> onSuccess, Consumer<Exception> onFailure) {
    cancel();
    cancelled.set(false);
    future =
        EXECUTOR.submit(
            () -> {
              try {
                var result = supplier.get();
                if (!cancelled.get()) {
                  FxThread.run(() -> onSuccess.accept(result));
                }
              } catch (Exception ex) {
                if (!cancelled.get()) {
                  LOG.warning("[data-loader] Failed: " + ex.getMessage());
                  FxThread.run(() -> onFailure.accept(ex));
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
