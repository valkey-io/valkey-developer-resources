package com.flicenjoyer.ui;

import com.flicenjoyer.model.Movie;
import com.flicenjoyer.service.CatalogService;
import com.flicenjoyer.service.WatchHistoryService;
import java.io.File;
import java.util.logging.Logger;
import javafx.geometry.Insets;
import javafx.geometry.Pos;
import javafx.scene.control.Button;
import javafx.scene.control.Label;
import javafx.scene.control.Slider;
import javafx.scene.layout.HBox;
import javafx.scene.layout.Priority;
import javafx.scene.layout.StackPane;
import javafx.scene.layout.VBox;
import javafx.scene.media.Media;
import javafx.scene.media.MediaPlayer;
import javafx.scene.media.MediaView;
import javafx.util.Duration;

/**
 * Video playback view with transport controls, auto-save resume, rating, and keyboard shortcuts.
 */
public class PlayerView {

  private static final Logger LOG = Logger.getLogger(PlayerView.class.getName());

  private final StackPane rootStack = new StackPane();
  private final NotificationBanner banner = new NotificationBanner(NotificationBanner.Style.BUBBLE);
  private final WatchHistoryService watchHistoryService;
  private final CatalogService catalogService;
  private final Button backBtn = new Button("<< Back");
  private Runnable onBack;

  private final Label titleLabel = new Label("No video loaded");
  private final Label metaLabel = new Label();
  private final Label timeLabel = new Label("0:00");
  private final Label durationLabel = new Label("0:00");
  private final Slider scrubber = new Slider(0, 1, 0);
  private final MediaView mediaView = new MediaView();
  private final Button playBtn = new Button("▶ Play");
  private final Button muteBtn = new Button("Vol");
  private final Slider volumeSlider = new Slider(0, 1, 1);

  private MediaPlayer player;
  private Movie currentMovie;
  private boolean scrubbing;
  private boolean finished;
  private javafx.animation.Timeline autoSaveTimer;
  private double savedVolume = 1.0;
  private boolean savedMute = false;

  private final StarRating starRating = new StarRating();

  public PlayerView(WatchHistoryService watchHistoryService, CatalogService catalogService) {
    this.watchHistoryService = watchHistoryService;
    this.catalogService = catalogService;
    var root = new VBox(8);
    root.setPadding(new Insets(20));

    backBtn.getStyleClass().add("btn-outline");
    backBtn.setOnAction(
        e -> {
          if (onBack != null) onBack.run();
        });
    backBtn.setVisible(false);

    titleLabel.getStyleClass().add("now-playing-title");
    metaLabel.getStyleClass().add("card-meta");

    starRating.setOnRatingChanged(this::persistRating);
    var ratingHint = new Label("(Option+0-5 to set)");
    ratingHint.setStyle("-fx-text-fill: #666; -fx-font-size: 9;");
    var ratingBox = new javafx.scene.layout.VBox(2, starRating, ratingHint);
    ratingBox.setAlignment(javafx.geometry.Pos.CENTER_RIGHT);

    var headerSpacer = new javafx.scene.layout.Region();
    javafx.scene.layout.HBox.setHgrow(headerSpacer, javafx.scene.layout.Priority.ALWAYS);
    var headerRow = new javafx.scene.layout.HBox(8, backBtn, titleLabel, headerSpacer, ratingBox);
    headerRow.setAlignment(javafx.geometry.Pos.CENTER_LEFT);

    mediaView.setPreserveRatio(true);
    mediaView.fitWidthProperty().bind(root.widthProperty().subtract(40));
    mediaView.setFitHeight(360);
    var videoPane = new StackPane(mediaView);
    videoPane.setStyle("-fx-background-color: #0a0a1a; -fx-background-radius: 6;");
    videoPane.setMinHeight(200);

    // Timeline
    scrubber.setMaxWidth(Double.MAX_VALUE);
    HBox.setHgrow(scrubber, Priority.ALWAYS);
    timeLabel.setStyle("-fx-font-family: monospace; -fx-text-fill: #ccc; -fx-font-size: 12;");
    durationLabel.setStyle("-fx-font-family: monospace; -fx-text-fill: #ccc; -fx-font-size: 12;");
    var timeline = new HBox(10, timeLabel, scrubber, durationLabel);
    timeline.setAlignment(Pos.CENTER);

    scrubber.setOnMousePressed(e -> scrubbing = true);
    scrubber.setOnMouseReleased(
        e -> {
          scrubbing = false;
          if (player != null && !finished) {
            var seekSec = (long) scrubber.getValue();
            player.seek(Duration.seconds(seekSec));
            persistResumePoint(seekSec);
          }
        });

    // Transport controls
    var restartBtn = new Button();
    restartBtn.setGraphic(IconLoader.playerIcon("restart"));
    var rwBtn = new Button();
    rwBtn.setGraphic(IconLoader.playerIcon("rewind"));
    var ffBtn = new Button();
    ffBtn.setGraphic(IconLoader.playerIcon("forward"));
    var stopBtn = new Button();
    stopBtn.setGraphic(IconLoader.playerIcon("stop"));

    for (var b : new Button[] {restartBtn, rwBtn, playBtn, ffBtn, stopBtn}) {
      b.getStyleClass().add("btn-outline");
      b.setStyle("-fx-min-width: 44; -fx-padding: 8 14;");
    }
    playBtn.getStyleClass().remove("btn-outline");
    playBtn.getStyleClass().add("btn-primary");
    playBtn.setStyle("-fx-padding: 8 20;");
    updatePlayBtnIcon("play");

    restartBtn.setOnAction(
        e -> {
          if (player != null) player.seek(Duration.ZERO);
        });
    rwBtn.setOnAction(
        e -> {
          if (player != null) player.seek(player.getCurrentTime().subtract(Duration.seconds(10)));
        });
    ffBtn.setOnAction(
        e -> {
          if (player != null) player.seek(player.getCurrentTime().add(Duration.seconds(10)));
        });
    playBtn.setOnAction(e -> togglePlay());
    stopBtn.setOnAction(
        e -> {
          if (player != null) {
            player.pause();
            player.seek(Duration.ZERO);
            stopAutoSave();
            persistResumePoint();
            updatePlayBtnIcon("play");
            finished = false;
          }
        });

    // Volume control
    muteBtn.getStyleClass().add("btn-outline");
    muteBtn.setStyle("-fx-min-width: 36; -fx-padding: 4 8;");
    muteBtn.setText(savedMute ? "Muted" : "Vol");
    volumeSlider.setPrefWidth(80);
    volumeSlider.setMaxWidth(80);
    volumeSlider.setValue(savedVolume);
    muteBtn.setOnAction(
        e -> {
          if (player != null) {
            var wasMuted = player.isMute() || player.getVolume() == 0;
            player.setMute(!player.isMute());
            if (wasMuted && player.getVolume() == 0) {
              player.setVolume(0.07);
              volumeSlider.setValue(0.07);
            }
            muteBtn.setText(player.isMute() ? "Muted" : "Vol");
          }
        });
    volumeSlider
        .valueProperty()
        .addListener(
            (obs, oldV, newV) -> {
              if (player != null) {
                player.setVolume(newV.doubleValue());
                if (player.isMute()) {
                  player.setMute(false);
                }
                muteBtn.setText(newV.doubleValue() == 0 ? "Muted" : "Vol");
              }
            });

    var volumeBox = new HBox(4, muteBtn, volumeSlider);
    volumeBox.setAlignment(Pos.CENTER);

    var transport =
        new HBox(
            8,
            restartBtn,
            rwBtn,
            playBtn,
            ffBtn,
            stopBtn,
            new javafx.scene.layout.Region(),
            volumeBox);
    javafx.scene.layout.HBox.setHgrow(
        transport.getChildren().get(5), javafx.scene.layout.Priority.ALWAYS);
    transport.setAlignment(Pos.CENTER);

    root.getChildren().addAll(headerRow, metaLabel, videoPane, timeline, transport);
    rootStack.getChildren().add(root);
    banner.attachTo(rootStack);

    rootStack.addEventFilter(javafx.scene.input.KeyEvent.KEY_PRESSED, this::handleKeyPress);
    rootStack.setFocusTraversable(true);
  }

  private void handleKeyPress(javafx.scene.input.KeyEvent e) {
    if (e.isAltDown()) {
      var digit =
          switch (e.getCode()) {
            case DIGIT0 -> 0;
            case DIGIT1 -> 1;
            case DIGIT2 -> 2;
            case DIGIT3 -> 3;
            case DIGIT4 -> 4;
            case DIGIT5 -> 5;
            default -> -1;
          };
      if (digit >= 0) {
        starRating.setRating(digit);
        e.consume();
        return;
      }
    }
    switch (e.getCode()) {
      case SPACE -> {
        togglePlay();
        e.consume();
      }
      case HOME -> {
        if (player != null) {
          player.seek(Duration.ZERO);
          persistResumePoint(0);
        }
        e.consume();
      }
      case END -> {
        if (player != null) player.seek(player.getTotalDuration());
        e.consume();
      }
      case LEFT -> {
        if (player != null) {
          var t = player.getCurrentTime().subtract(Duration.seconds(5));
          player.seek(t.lessThan(Duration.ZERO) ? Duration.ZERO : t);
        }
        e.consume();
      }
      case RIGHT -> {
        if (player != null) player.seek(player.getCurrentTime().add(Duration.seconds(5)));
        e.consume();
      }
      case UP -> {
        if (player != null) {
          var v = Math.min(player.getVolume() + 0.1, 1.0);
          player.setVolume(v);
          volumeSlider.setValue(v);
        }
        e.consume();
      }
      case DOWN -> {
        if (player != null) {
          var v = Math.max(player.getVolume() - 0.1, 0.0);
          player.setVolume(v);
          volumeSlider.setValue(v);
        }
        e.consume();
      }
      case M -> {
        if (player != null) {
          player.setMute(!player.isMute());
          muteBtn.setText(player.isMute() ? "Muted" : "Vol");
        }
        e.consume();
      }
      default -> {}
    }
  }

  public void loadMovie(Movie movie) {
    stopPlayback();
    currentMovie = movie;
    finished = false;
    titleLabel.setText("Now Playing: " + movie.title());
    metaLabel.setText(
        movie.genre()
            + " · "
            + movie.releaseYear()
            + " · "
            + PlaybackState.formatTime(movie.durationMinutes() * 60));
    starRating.setRating((int) movie.rating());
    LOG.info("[player] Loading: " + movie.title() + " path=" + movie.videoPath());

    var videoFile = new File(movie.videoPath());
    if (!videoFile.exists()) {
      banner.error("Video file not found: " + movie.videoPath());
      LOG.severe("[player] File not found: " + movie.videoPath());
      return;
    }

    var media = new Media(videoFile.toURI().toString());
    player = new MediaPlayer(media);
    mediaView.setMediaPlayer(player);

    player.setOnReady(
        () -> {
          var total = player.getTotalDuration().toSeconds();
          scrubber.setMax(total);
          durationLabel.setText(PlaybackState.formatTime(total));

          // Restore volume state
          player.setVolume(savedVolume);
          player.setMute(savedMute);
          volumeSlider.setValue(savedVolume);
          muteBtn.setText(savedMute ? "Muted" : "Vol");

          // Persist actual duration if not already set
          var actualMinutes = total / 60.0;
          if (Math.abs(movie.durationMinutes() - actualMinutes) > 0.01) {
            var mid = movie.id();
            asyncSafe(
                "Failed to update duration",
                () -> {
                  catalogService.updateDuration(mid, actualMinutes);
                  LOG.info("[player] Updated duration to " + actualMinutes + " min");
                });
          }

          // Resume from last position (async)
          var mid1 = movie.id();
          java.util.concurrent.CompletableFuture.supplyAsync(
                  () -> {
                    try {
                      return watchHistoryService.getResumePoint(mid1);
                    } catch (Exception ex) {
                      LOG.warning("[player] Failed to load resume point: " + ex.getMessage());
                      return 0L;
                    }
                  })
              .thenAcceptAsync(
                  resumeSec -> {
                    if (resumeSec > 0) {
                      player.seek(Duration.seconds(resumeSec));
                      LOG.info("[player] Resuming from " + PlaybackState.formatTime(resumeSec));
                      banner.success("Resuming from " + PlaybackState.formatTime(resumeSec));
                    }
                  },
                  javafx.application.Platform::runLater);

          // Start watching entry if new
          var mid2 = movie.id();
          var mtitle = movie.title();
          asyncSafe(
              "Failed to create watch entry",
              () -> watchHistoryService.startWatching(mid2, mtitle));

          player.play();
          updatePlayBtnIcon("pause");
          startAutoSave();
        });

    player
        .currentTimeProperty()
        .addListener(
            (obs, oldT, newT) -> {
              if (!scrubbing) {
                scrubber.setValue(newT.toSeconds());
                timeLabel.setText(PlaybackState.formatTime(newT.toSeconds()));
              }
            });

    player.setOnEndOfMedia(
        () -> {
          player.pause();
          finished = true;
          stopAutoSave();
          updatePlayBtnIcon("restart");
          persistResumePoint();
          var mid3 = movie.id();
          var mt3 = movie.title();
          asyncSafe(
              "Failed to mark completed",
              () -> {
                watchHistoryService.markCompleted(mid3);
                LOG.info("[player] Marked completed: " + mt3);
              });
        });

    player.setOnError(
        () -> {
          banner.error("Playback error: " + player.getError().getMessage());
          LOG.severe("[player] Error: " + player.getError().getMessage());
        });
  }

  private void togglePlay() {
    if (player == null) return;
    if (finished) {
      finished = false;
      player.seek(Duration.ZERO);
      player.play();
      updatePlayBtnIcon("pause");
      startAutoSave();
      var rid = currentMovie.id();
      asyncSafe(
          "Failed to reset resume point", () -> watchHistoryService.updateResumePoint(rid, 0));
    } else if (player.getStatus() == MediaPlayer.Status.PLAYING) {
      player.pause();
      updatePlayBtnIcon("play");
      stopAutoSave();
      persistResumePoint();
    } else {
      player.play();
      updatePlayBtnIcon("pause");
      startAutoSave();
    }
  }

  private void stopPlayback() {
    stopAutoSave();
    if (player != null) {
      savedVolume = player.getVolume();
      savedMute = player.isMute();
      persistResumePoint();
      player.stop();
      player.dispose();
      player = null;
      mediaView.setMediaPlayer(null);
      updatePlayBtnIcon("play");
      scrubber.setValue(0);
      timeLabel.setText("0:00");
    }
  }

  private void persistRating(int rating) {
    if (currentMovie == null) return;
    var id = currentMovie.id();
    var title = currentMovie.title();
    asyncSafe(
        "Failed to save rating",
        () -> {
          catalogService.updateRating(id, rating);
          LOG.info("[player] Rating set to " + rating + " for " + title);
        });
  }

  private void persistResumePoint() {
    if (player == null || currentMovie == null) return;
    persistResumePoint((long) player.getCurrentTime().toSeconds());
  }

  private void persistResumePoint(long seconds) {
    if (currentMovie == null) return;
    var id = currentMovie.id();
    asyncSafe(
        "Failed to save resume point",
        () -> {
          watchHistoryService.updateResumePoint(id, seconds);
          LOG.fine("[player] Resume point saved: " + PlaybackState.formatTime(seconds));
        });
  }

  private void startAutoSave() {
    stopAutoSave();
    autoSaveTimer =
        new javafx.animation.Timeline(
            new javafx.animation.KeyFrame(Duration.seconds(3), e -> persistResumePoint()));
    autoSaveTimer.setCycleCount(javafx.animation.Animation.INDEFINITE);
    autoSaveTimer.play();
  }

  private void stopAutoSave() {
    if (autoSaveTimer != null) {
      autoSaveTimer.stop();
      autoSaveTimer = null;
    }
  }

  public void setBackNavigation(ViewId viewId, Runnable action) {
    backBtn.setGraphic(IconLoader.plainIcon("back", 16, javafx.scene.paint.Color.web("#e94560")));
    backBtn.setText(" Back to " + viewId.label());
    backBtn.setVisible(true);
    onBack = action;
  }

  public void onLeave() {
    stopPlayback();
  }

  private void updatePlayBtnIcon(String state) {
    var iconName =
        switch (state) {
          case "play" -> "play";
          case "pause" -> "pause";
          case "restart" -> "start-over";
          default -> "play";
        };
    var label =
        switch (state) {
          case "play" -> " Play";
          case "pause" -> " Pause";
          case "restart" -> " Start Over";
          default -> "";
        };
    playBtn.setGraphic(IconLoader.playerIcon(iconName));
    playBtn.setText(label);
  }

  public StackPane getRoot() {
    return rootStack;
  }

  private static void asyncSafe(String label, ThrowingRunnable task) {
    java.util.concurrent.CompletableFuture.runAsync(
        () -> {
          try {
            task.run();
          } catch (InterruptedException ex) {
            Thread.currentThread().interrupt();
            LOG.warning("[player] " + label + " interrupted");
          } catch (java.util.concurrent.ExecutionException ex) {
            LOG.warning("[player] " + label + ": " + ex.getCause().getMessage());
          } catch (Exception ex) {
            LOG.warning("[player] " + label + ": " + ex.getMessage());
          }
        });
  }

  @FunctionalInterface
  private interface ThrowingRunnable {
    void run() throws Exception;
  }
}
