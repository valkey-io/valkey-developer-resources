package com.flicenjoyer.ui;

import com.flicenjoyer.model.Genre;
import com.flicenjoyer.model.Movie;
import com.flicenjoyer.service.CatalogService;
import com.flicenjoyer.service.UploadService;
import com.flicenjoyer.valkey.AppPaths;
import java.io.File;
import java.util.logging.Logger;
import javafx.geometry.Insets;
import javafx.geometry.Pos;
import javafx.scene.control.*;
import javafx.scene.image.Image;
import javafx.scene.image.ImageView;
import javafx.scene.layout.*;
import javafx.stage.FileChooser;
import javafx.stage.Stage;

/**
 * Configurable video form — used for both Upload (new video) and Edit (existing video metadata).
 */
public class VideoFormView {

  private static final Logger LOG = Logger.getLogger(VideoFormView.class.getName());

  public enum Mode {
    UPLOAD,
    EDIT
  }

  private final StackPane rootStack = new StackPane();
  private final VBox root = new VBox(20);
  private final NotificationBanner banner = new NotificationBanner();
  private final Stage stage;
  private final Mode mode;

  private final TextField titleField = new TextField();
  private final ComboBox<String> genreBox = new ComboBox<>();
  private final Spinner<Integer> yearSpinner = new Spinner<>(1900, 2100, 2026);
  private final TextArea descArea = new TextArea();
  private final TextField tagsField = new TextField();
  private final Label videoFileLabel = new Label("No file selected");
  private final ImageView thumbPreview = new ImageView();

  private File selectedVideo;
  private File selectedThumbnail;
  private Button submitBtn;
  private ProgressIndicator submitSpinner;
  private HBox formPane;
  private BackgroundTask currentTask;

  // For edit mode
  private UploadService uploadService;
  private CatalogService catalogService;
  private Movie editingMovie;
  private Runnable onComplete;

  public VideoFormView(Stage stage, Mode mode) {
    this.stage = stage;
    this.mode = mode;
    root.setPadding(new Insets(20));
    thumbPreview.setFitWidth(120);
    thumbPreview.setFitHeight(68);
    thumbPreview.setPreserveRatio(true);

    var columns = new HBox(24);

    // Left column — metadata
    var leftCol = new VBox(10);
    leftCol.setMinWidth(300);
    HBox.setHgrow(leftCol, Priority.ALWAYS);

    titleField.setPromptText("Title *");
    leftCol.getChildren().add(labeled("Title *", titleField));

    genreBox.getItems().addAll(Genre.displayNames());
    genreBox.setEditable(false);
    genreBox.setPromptText("Select genre");
    genreBox.setMaxWidth(Double.MAX_VALUE);
    leftCol.getChildren().add(labeled("Genre", genreBox));

    yearSpinner.setEditable(true);
    leftCol.getChildren().add(labeled("Year", yearSpinner));

    descArea.setPromptText("Description");
    descArea.setPrefRowCount(3);
    leftCol.getChildren().add(labeled("Description", descArea));

    tagsField.setPromptText("comma-separated tags");
    leftCol.getChildren().add(labeled("Tags", tagsField));

    // Right column — file pickers
    var rightCol = new VBox(16);
    rightCol.setMinWidth(250);

    if (mode == Mode.UPLOAD) {
      var chooseVideoBtn = new Button("Choose File");
      chooseVideoBtn.getStyleClass().add("btn-outline");
      chooseVideoBtn.setOnAction(e -> pickVideo());
      videoFileLabel.getStyleClass().add("file-label");
      rightCol
          .getChildren()
          .add(labeled("Video File *", new HBox(8, chooseVideoBtn, videoFileLabel)));
    }

    var chooseThumbBtn = new Button("Choose Image");
    chooseThumbBtn.getStyleClass().add("btn-outline");
    chooseThumbBtn.setOnAction(e -> pickThumbnail());

    var extractBtn = new Button("Extract from video ⚗️");
    extractBtn.getStyleClass().add("btn-outline");
    extractBtn.setOnAction(e -> extractThumbnail(extractBtn));

    rightCol
        .getChildren()
        .add(
            labeled(
                "Thumbnail", new VBox(8, new HBox(8, chooseThumbBtn, extractBtn), thumbPreview)));

    columns.getChildren().addAll(leftCol, rightCol);

    // Submit button
    var submitLabel = mode == Mode.UPLOAD ? " Upload Video" : " Save Changes";
    submitBtn = new Button(submitLabel);
    submitBtn.getStyleClass().add("btn-primary");
    submitBtn.setGraphic(
        IconLoader.plainIcon(
            mode == Mode.UPLOAD ? "nav-upload" : "edit", 14, javafx.scene.paint.Color.WHITE));
    submitBtn.setOnAction(e -> handleSubmit());

    submitSpinner = new ProgressIndicator();
    submitSpinner.setPrefSize(20, 20);
    submitSpinner.setVisible(false);

    var btnRow = new HBox(8, submitSpinner, submitBtn);
    btnRow.setAlignment(Pos.CENTER_RIGHT);

    formPane = columns;

    // Back button (edit mode only, set via setBackNavigation)
    backBtn = new Button();
    backBtn.getStyleClass().add("btn-outline");
    backBtn.setVisible(false);
    backBtn.setGraphic(IconLoader.plainIcon("back", 14, javafx.scene.paint.Color.web("#e94560")));
    backBtn.setOnAction(
        e -> {
          if (onBack != null) onBack.run();
        });

    root.getChildren().addAll(backBtn, columns, btnRow);
    rootStack.getChildren().add(root);
    banner.attachTo(rootStack);
  }

  private Button backBtn;
  private Runnable onBack;

  public void setBackNavigation(ViewId viewId, Runnable action) {
    backBtn.setText(" Back to " + viewId.label());
    backBtn.setVisible(true);
    onBack = action;
  }

  public void setUploadService(UploadService svc) {
    this.uploadService = svc;
  }

  public void setCatalogService(CatalogService svc) {
    this.catalogService = svc;
  }

  public void setOnComplete(Runnable callback) {
    this.onComplete = callback;
  }

  /** Pre-populate form for edit mode. */
  public void loadMovie(Movie movie) {
    this.editingMovie = movie;
    titleField.setText(movie.title());
    genreBox.setValue(movie.genre());
    yearSpinner.getValueFactory().setValue(movie.releaseYear());
    descArea.setText(movie.description());
    tagsField.setText(movie.tags());
    if (!movie.thumbnailPath().isEmpty()) {
      var file = new File(movie.thumbnailPath());
      if (file.exists()) {
        thumbPreview.setImage(new Image(file.toURI().toString()));
        selectedThumbnail = file;
      }
    }
    // For extract-from-video in edit mode
    if (!movie.videoPath().isEmpty()) {
      selectedVideo = new File(movie.videoPath());
      videoFileLabel.setText(new File(movie.videoPath()).getName());
    }
  }

  public void cancelTask() {
    if (currentTask != null) currentTask.cancel();
  }

  public StackPane getRoot() {
    return rootStack;
  }

  // --- private helpers ---

  private VBox labeled(String text, javafx.scene.Node control) {
    var label = new Label(text);
    label.getStyleClass().add("field-label");
    return new VBox(4, label, control);
  }

  private void pickVideo() {
    var fc = new FileChooser();
    fc.setTitle("Select Video");
    fc.getExtensionFilters()
        .add(new FileChooser.ExtensionFilter("Video Files", "*.mp4", "*.mkv", "*.avi", "*.mov"));
    var file = fc.showOpenDialog(stage);
    if (file != null) {
      selectedVideo = file;
      videoFileLabel.setText(file.getName());
    }
  }

  private void pickThumbnail() {
    var fc = new FileChooser();
    fc.setTitle("Select Thumbnail");
    fc.getExtensionFilters()
        .add(new FileChooser.ExtensionFilter("Image Files", "*.png", "*.jpg", "*.jpeg", "*.gif"));
    var file = fc.showOpenDialog(stage);
    if (file != null) {
      selectedThumbnail = file;
      thumbPreview.setImage(new Image(file.toURI().toString()));
    }
  }

  private static final String EXTRACT_LABEL = "Extract from video ⚗️";
  private static final String EXTRACT_BUSY = "Extracting ⏳";

  private void extractThumbnail(Button btn) {
    if (selectedVideo == null) {
      banner.warning("Select a video file first.");
      return;
    }
    btn.setDisable(true);
    btn.setText(EXTRACT_BUSY);
    LOG.info("[form] Starting frame extraction from: " + selectedVideo.getName());

    try {
      var media = new javafx.scene.media.Media(selectedVideo.toURI().toString());
      var player = new javafx.scene.media.MediaPlayer(media);
      var mediaView = new javafx.scene.media.MediaView(player);
      mediaView.setFitWidth(320);
      mediaView.setFitHeight(180);
      mediaView.setPreserveRatio(true);
      player.setMute(true);

      var captured = new java.util.concurrent.atomic.AtomicBoolean(false);

      player.setOnReady(
          () -> {
            player.seek(player.getTotalDuration().multiply(0.1));
            player.play();
          });

      player
          .currentTimeProperty()
          .addListener(
              (obs, oldTime, newTime) -> {
                if (captured.get()) return;
                var seekTarget = player.getTotalDuration().multiply(0.1);
                if (newTime.greaterThanOrEqualTo(
                    seekTarget.subtract(javafx.util.Duration.millis(500)))) {
                  if (captured.compareAndSet(false, true)) {
                    player.pause();
                    var timer =
                        new javafx.animation.PauseTransition(javafx.util.Duration.millis(200));
                    timer.setOnFinished(
                        ev -> {
                          try {
                            var snapshot =
                                mediaView.snapshot(new javafx.scene.SnapshotParameters(), null);
                            thumbPreview.setImage(snapshot);
                            // Clean up previous temp thumbnail
                            if (selectedThumbnail != null
                                && selectedThumbnail.getName().startsWith("thumb-")) {
                              selectedThumbnail.delete();
                            }
                            var tempFile = java.io.File.createTempFile("thumb-", ".png");
                            tempFile.deleteOnExit();
                            javax.imageio.ImageIO.write(
                                javafx.embed.swing.SwingFXUtils.fromFXImage(snapshot, null),
                                "png",
                                tempFile);
                            selectedThumbnail = tempFile;
                          } catch (Exception ex) {
                            LOG.severe("[form] Snapshot failed: " + ex.getMessage());
                            banner.error("Snapshot failed: " + ex.getMessage());
                          } finally {
                            player.dispose();
                            btn.setText(EXTRACT_LABEL);
                            btn.setDisable(false);
                          }
                        });
                    timer.play();
                  }
                }
              });

      player.setOnError(
          () -> {
            LOG.severe("[form] MediaPlayer error: " + player.getError().getMessage());
            banner.error("Failed to extract frame: " + player.getError().getMessage());
            player.dispose();
            btn.setText(EXTRACT_LABEL);
            btn.setDisable(false);
          });

      var timeout = new javafx.animation.PauseTransition(javafx.util.Duration.seconds(10));
      timeout.setOnFinished(
          ev -> {
            if (captured.compareAndSet(false, true)) {
              player.dispose();
              btn.setText(EXTRACT_LABEL);
              btn.setDisable(false);
              banner.warning("Frame extraction timed out.");
            }
          });
      timeout.play();
    } catch (Exception ex) {
      LOG.severe("[form] Exception: " + ex.getMessage());
      banner.error("Frame extraction failed: " + ex.getMessage());
      btn.setText(EXTRACT_LABEL);
      btn.setDisable(false);
    }
  }

  private void handleSubmit() {
    if (titleField.getText().isBlank()) {
      banner.warning("Title is required.");
      return;
    }
    if (mode == Mode.UPLOAD && selectedVideo == null) {
      banner.warning("Video file is required.");
      return;
    }
    setSubmitting(true);

    if (mode == Mode.UPLOAD) {
      handleUpload();
    } else {
      handleEdit();
    }
  }

  private void handleUpload() {
    LOG.info("[upload] Starting upload for: " + titleField.getText());
    var videoFile = selectedVideo;
    var thumbFile = selectedThumbnail;
    var title = titleField.getText();
    var genre = genreBox.getValue() != null ? genreBox.getValue() : "";
    var desc = descArea.getText();
    var tags = tagsField.getText();
    var year = yearSpinner.getValue();

    currentTask =
        new BackgroundTask() {
          private String catalogId;

          @Override
          protected void execute() throws Exception {
            double durationMinutes = 0;
            var latch = new java.util.concurrent.CountDownLatch(1);
            var duration = new java.util.concurrent.atomic.AtomicLong(0);
            javafx.application.Platform.runLater(
                () -> {
                  try {
                    var media = new javafx.scene.media.Media(videoFile.toURI().toString());
                    var p = new javafx.scene.media.MediaPlayer(media);
                    p.setMute(true);
                    p.setOnReady(
                        () -> {
                          duration.set(Double.doubleToLongBits(p.getTotalDuration().toMinutes()));
                          p.dispose();
                          latch.countDown();
                        });
                    p.setOnError(
                        () -> {
                          p.dispose();
                          latch.countDown();
                        });
                  } catch (Exception ex) {
                    latch.countDown();
                  }
                });
            if (latch.await(2500, java.util.concurrent.TimeUnit.MILLISECONDS))
              durationMinutes = Double.longBitsToDouble(duration.get());
            if (isCancelled()) return;
            catalogId =
                uploadService.uploadVideo(
                    title,
                    genre,
                    desc,
                    tags,
                    year,
                    durationMinutes,
                    videoFile.toPath(),
                    thumbFile != null ? thumbFile.toPath() : null);
            LOG.info("[upload] Success — catalog ID: " + catalogId);
          }

          @Override
          protected void onSuccess() {
            banner.success("Video uploaded! ID: " + catalogId);
            resetForm();
          }

          @Override
          protected void onFailure(Exception ex) {
            LOG.severe("[upload] Failed: " + ex.getMessage());
            banner.error("Upload failed: " + ex.getMessage());
          }

          @Override
          protected void onFinally() {
            setSubmitting(false);
            currentTask = null;
          }
        };
    currentTask.start();
  }

  private void handleEdit() {
    LOG.info("[edit] Saving changes for: " + editingMovie.id());
    var id = editingMovie.id();
    var title = titleField.getText();
    var genre = genreBox.getValue() != null ? genreBox.getValue() : "";
    var desc = descArea.getText();
    var tags = tagsField.getText();
    var year = yearSpinner.getValue();
    var thumb = selectedThumbnail;
    var oldThumb = editingMovie.thumbnailPath();

    currentTask =
        new BackgroundTask() {
          @Override
          protected void execute() throws Exception {
            catalogService.updateMetadata(id, title, genre, desc, tags, year);
            if (thumb != null && !thumb.getAbsolutePath().equals(oldThumb)) {
              var thumbDir = AppPaths.THUMBNAILS;
              java.nio.file.Files.createDirectories(thumbDir);
              var ext =
                  thumb.getName().contains(".")
                      ? thumb.getName().substring(thumb.getName().lastIndexOf('.'))
                      : ".png";
              var target = thumbDir.resolve(id + ext);
              java.nio.file.Files.copy(
                  thumb.toPath(), target, java.nio.file.StandardCopyOption.REPLACE_EXISTING);
              catalogService.updateThumbnail(id, target.toAbsolutePath().toString());
              if (oldThumb != null && !oldThumb.isEmpty())
                java.nio.file.Files.deleteIfExists(java.nio.file.Path.of(oldThumb));
            }
          }

          @Override
          protected void onSuccess() {
            if (onComplete != null) onComplete.run();
          }

          @Override
          protected void onFailure(Exception ex) {
            LOG.severe("[edit] Failed: " + ex.getMessage());
            banner.error("Save failed: " + ex.getMessage());
          }

          @Override
          protected void onFinally() {
            setSubmitting(false);
            currentTask = null;
          }
        };
    currentTask.start();
  }

  private void resetForm() {
    titleField.clear();
    descArea.clear();
    tagsField.clear();
    selectedVideo = null;
    selectedThumbnail = null;
    videoFileLabel.setText("No file selected");
    thumbPreview.setImage(null);
  }

  private void setSubmitting(boolean busy) {
    formPane.setDisable(busy);
    submitBtn.setDisable(busy);
    submitBtn.setText(
        busy
            ? (mode == Mode.UPLOAD ? "Uploading ⏳" : "Saving ⏳")
            : (mode == Mode.UPLOAD ? " Upload Video" : " Save Changes"));
    submitSpinner.setVisible(busy);
  }
}
