package com.flicenjoyer.ui;

import javafx.scene.Node;
import javafx.scene.control.Label;
import javafx.scene.control.ScrollPane;
import javafx.scene.layout.Priority;
import javafx.scene.layout.VBox;

/** Shared UI factory methods for common widget patterns. */
public final class UiFactory {
  private UiFactory() {}

  public static Label styledLabel(String text) {
    var l = new Label(text);
    l.getStyleClass().add("field-label");
    return l;
  }

  /** Creates a transparent ScrollPane that fills available VBox height. */
  public static ScrollPane scrollPane(Node content) {
    var sp = new ScrollPane(content);
    sp.setFitToWidth(true);
    VBox.setVgrow(sp, Priority.ALWAYS);
    return sp;
  }
}
