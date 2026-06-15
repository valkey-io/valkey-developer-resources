package com.flicenjoyer.ui;

import javafx.animation.FadeTransition;
import javafx.animation.PauseTransition;
import javafx.animation.TranslateTransition;
import javafx.geometry.Insets;
import javafx.geometry.Pos;
import javafx.scene.control.Label;
import javafx.scene.layout.StackPane;
import javafx.util.Duration;

/**
 * Temporary overlay banner for in-app notifications. Two variants:
 *
 * <ul>
 *   <li><b>Wide</b> (default) — full-width bar at the top of the view
 *   <li><b>Bubble</b> — fixed-width rounded pill anchored top-right, for views where a wide banner
 *       would obstruct controls
 * </ul>
 */
public class NotificationBanner {

  public enum Style {
    WIDE,
    BUBBLE
  }

  private final Label banner = new Label();
  private final Style style;
  private PauseTransition dismissTimer;
  private FadeTransition fadeOut;

  public NotificationBanner() {
    this(Style.WIDE);
  }

  public NotificationBanner(Style style) {
    this.style = style;
    banner.setPadding(new Insets(10, 20, 10, 20));
    banner.setStyle("-fx-font-size: 13px; -fx-font-weight: bold;");
    banner.setVisible(false);
    banner.setManaged(false);

    if (style == Style.WIDE) {
      banner.setMaxWidth(Double.MAX_VALUE);
      StackPane.setAlignment(banner, Pos.TOP_CENTER);
    } else {
      banner.setMaxWidth(javafx.scene.layout.Region.USE_PREF_SIZE);
      StackPane.setAlignment(banner, Pos.TOP_RIGHT);
      StackPane.setMargin(banner, new Insets(8, 12, 0, 0));
    }
  }

  public void attachTo(StackPane parent) {
    if (!parent.getChildren().contains(banner)) {
      parent.getChildren().add(banner);
    }
  }

  public void success(String message) {
    show("check", message, "#2d6a4f");
  }

  public void error(String message) {
    show("x-circle", message, "#c73650");
  }

  public void warning(String message) {
    show("alert", message, "#b8860b");
  }

  private void show(String iconName, String text, String bgColor) {
    if (dismissTimer != null) dismissTimer.stop();
    if (fadeOut != null) fadeOut.stop();
    var radius = style == Style.BUBBLE ? "16" : "0 0 6 6";
    banner.setGraphic(IconLoader.plainIcon(iconName, 16, javafx.scene.paint.Color.WHITE));
    banner.setText(text);
    banner.setStyle(
        "-fx-background-color: "
            + bgColor
            + ";"
            + " -fx-text-fill: white; -fx-font-size: 13px; -fx-font-weight: bold;"
            + " -fx-background-radius: "
            + radius
            + "; -fx-padding: 10 20;");
    banner.setVisible(true);
    banner.setManaged(true);
    banner.setOpacity(1.0);
    banner.setTranslateY(-30);

    var slideIn = new TranslateTransition(Duration.millis(200), banner);
    slideIn.setToY(0);
    slideIn.play();

    dismissTimer = new PauseTransition(Duration.seconds(4));
    dismissTimer.setOnFinished(e -> dismiss());
    dismissTimer.play();
  }

  private void dismiss() {
    fadeOut = new FadeTransition(Duration.millis(400), banner);
    fadeOut.setToValue(0);
    fadeOut.setOnFinished(
        e -> {
          banner.setVisible(false);
          banner.setManaged(false);
        });
    fadeOut.play();
  }
}
