package com.flicenjoyer.ui;

import com.flicenjoyer.model.Movie;
import com.flicenjoyer.service.WatchHistoryService;
import java.io.File;
import javafx.geometry.Pos;
import javafx.scene.image.Image;
import javafx.scene.image.ImageView;
import javafx.scene.layout.Region;
import javafx.scene.layout.StackPane;

/** Determines the playback action label for a video based on its watch state. */
public class PlaybackState {

  private static final java.util.logging.Logger LOG =
      java.util.logging.Logger.getLogger(PlaybackState.class.getName());

  public enum Action {
    PLAY("Play", "play"),
    RESUME("Resume", "play"),
    START_OVER("Start Over", "start-over");

    private final String label;
    private final String iconName;

    Action(String label, String iconName) {
      this.label = label;
      this.iconName = iconName;
    }

    public String label() {
      return label;
    }

    public String iconName() {
      return iconName;
    }
  }

  /** Creates a styled button with SVG icon for the given action. */
  public static javafx.scene.control.Button createButton(Action action) {
    var btn = new javafx.scene.control.Button(" " + action.label());
    btn.setGraphic(IconLoader.plainIcon(action.iconName(), 14, javafx.scene.paint.Color.WHITE));
    btn.getStyleClass().add("btn-primary");
    btn.setStyle("-fx-font-size: 11;");
    return btn;
  }

  /** Loads a thumbnail into a StackPane, preserving aspect ratio with black background. */
  public static void loadThumbnail(
      StackPane thumb, String thumbnailPath, double width, double height) {
    // Clip to rounded corners so thumbnail doesn't overflow the card border
    var clip = new javafx.scene.shape.Rectangle(width, height);
    clip.setArcWidth(16);
    clip.setArcHeight(16);
    thumb.setClip(clip);
    thumb.setStyle("-fx-background-color: black;");
    if (thumbnailPath != null && !thumbnailPath.isEmpty()) {
      var file = new File(thumbnailPath);
      if (file.exists()) {
        var img = new Image(file.toURI().toString(), width, height, true, true, true);
        var iv = new ImageView(img);
        iv.setFitWidth(width);
        iv.setFitHeight(height);
        iv.setPreserveRatio(true);
        thumb.getChildren().add(iv);
        return;
      }
    }
    thumb.setStyle("-fx-background-color: linear-gradient(to bottom right, #0f3460, #1a1a4e);");
    thumb.getChildren().add(new javafx.scene.control.Label("🎬"));
  }

  /** Adds a 2px progress bar using a pre-fetched resume point. */
  public static void addProgressBar(StackPane thumb, Movie movie, long resumeSec) {
    if (movie == null || movie.durationMinutes() <= 0 || resumeSec <= 0) return;
    addProgressBar(thumb, movie.durationMinutes(), resumeSec);
  }

  /** Adds a 2px progress bar given duration in minutes and resume position in seconds. */
  public static void addProgressBar(StackPane thumb, double durationMinutes, long resumeSec) {
    if (durationMinutes <= 0 || resumeSec <= 0) return;
    var pct = Math.min(resumeSec / (durationMinutes * 60.0), 1.0);
    var bar = new Region();
    bar.setMaxHeight(2);
    bar.setMinHeight(2);
    bar.setPrefHeight(2);
    bar.setStyle("-fx-background-color: #e94560;");
    bar.maxWidthProperty().bind(thumb.widthProperty().multiply(pct));
    StackPane.setAlignment(bar, Pos.BOTTOM_LEFT);
    thumb.getChildren().add(bar);
  }

  /** Convenience overload that fetches the resume point from Valkey. */
  public static void addProgressBar(StackPane thumb, Movie movie, WatchHistoryService whs) {
    if (whs == null || movie == null) return;
    try {
      addProgressBar(thumb, movie, whs.getResumePoint(movie.id()));
    } catch (InterruptedException e) {
      Thread.currentThread().interrupt();
    } catch (Exception e) {
      LOG.fine("[playback] Failed to get resume point for " + movie.id() + ": " + e.getMessage());
    }
  }

  /** Resolves playback action from a pre-fetched resume point. */
  public static Action resolve(Movie movie, long resumeSec) {
    if (movie == null || resumeSec <= 0) return Action.PLAY;
    if (movie.durationMinutes() > 0 && resumeSec >= movie.durationMinutes() * 60.0 * 0.95)
      return Action.START_OVER;
    return Action.RESUME;
  }

  /** Convenience overload that fetches the resume point from Valkey. */
  public static Action resolve(Movie movie, WatchHistoryService whs) {
    if (whs == null || movie == null) return Action.PLAY;
    try {
      return resolve(movie, whs.getResumePoint(movie.id()));
    } catch (InterruptedException e) {
      Thread.currentThread().interrupt();
      return Action.PLAY;
    } catch (Exception e) {
      return Action.PLAY;
    }
  }

  /** Formats seconds as M:SS. */
  public static String formatTime(double totalSeconds) {
    return formatTime((long) totalSeconds);
  }

  public static String formatTime(long totalSeconds) {
    return String.format("%d:%02d", totalSeconds / 60, totalSeconds % 60);
  }
}
