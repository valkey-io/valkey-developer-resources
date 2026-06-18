package com.flicenjoyer.ui;

import javafx.application.Platform;

/**
 * Utility for dispatching work to the JavaFX Application Thread. Falls back to direct execution in
 * tests.
 */
public final class FxThread {
  private FxThread() {}

  public static void run(Runnable action) {
    try {
      Platform.runLater(action);
    } catch (IllegalStateException e) {
      action.run();
    }
  }
}
