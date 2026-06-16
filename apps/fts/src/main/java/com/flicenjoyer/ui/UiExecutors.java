package com.flicenjoyer.ui;

import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/** Shared background executor for UI tasks. */
public final class UiExecutors {
  private UiExecutors() {}

  public static final ExecutorService BACKGROUND =
      Executors.newFixedThreadPool(
          2,
          r -> {
            var t = new Thread(r, "ui-background");
            t.setDaemon(true);
            return t;
          });
}
