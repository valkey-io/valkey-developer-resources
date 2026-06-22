package com.flicenjoyer.ui;

import javafx.scene.Node;
import javafx.scene.control.Button;
import javafx.scene.control.Label;
import javafx.scene.control.ScrollPane;
import javafx.scene.layout.HBox;
import javafx.scene.layout.Priority;
import javafx.scene.layout.Region;
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

  /** Creates a section header row with a label and a "Generate" button. */
  public static HBox sectionHeader(String title, Runnable onGenerate) {
    var label = new Label(title);
    label.setStyle("-fx-text-fill: #ccc; -fx-font-size: 14; -fx-font-weight: bold;");
    var btn = new Button(" Generate");
    btn.getStyleClass().add("btn-primary");
    btn.setStyle("-fx-font-size: 11;");
    btn.setOnAction(e -> onGenerate.run());
    var spacer = new Region();
    javafx.scene.layout.HBox.setHgrow(spacer, Priority.ALWAYS);
    return new HBox(8, label, spacer, btn);
  }
}
