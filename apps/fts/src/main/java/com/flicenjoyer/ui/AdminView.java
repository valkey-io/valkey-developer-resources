package com.flicenjoyer.ui;

import com.flicenjoyer.model.Movie;
import com.flicenjoyer.service.CatalogService;
import com.flicenjoyer.service.WatchHistoryService;
import java.util.function.Consumer;
import java.util.logging.Logger;
import javafx.geometry.Insets;
import javafx.geometry.Pos;
import javafx.scene.control.*;
import javafx.scene.layout.*;

/** Administration view for editing and deleting catalog entries (gated by config flag). */
public class AdminView {

  private static final Logger LOG = Logger.getLogger(AdminView.class.getName());

  private final StackPane rootStack = new StackPane();
  private final VBox root = new VBox(12);
  private final VBox listBox = new VBox(8);
  private final TextField filterField = new TextField();
  private final NotificationBanner banner = new NotificationBanner(NotificationBanner.Style.BUBBLE);
  private final CatalogService catalogService;
  private final WatchHistoryService watchHistoryService;
  private Consumer<Movie> onEditMovie;

  public AdminView(CatalogService catalogService, WatchHistoryService watchHistoryService) {
    this.catalogService = catalogService;
    this.watchHistoryService = watchHistoryService;
    root.setPadding(new Insets(20));

    var header = new Label("Video Administration");
    header.setStyle("-fx-text-fill: #ccc; -fx-font-size: 15; -fx-font-weight: bold;");

    filterField.setPromptText("Filter videos...");
    var debounce = new javafx.animation.PauseTransition(javafx.util.Duration.millis(150));
    debounce.setOnFinished(e -> refresh());
    filterField.textProperty().addListener((obs, o, n) -> debounce.playFromStart());

    var scrollPane = new ScrollPane(listBox);
    scrollPane.setFitToWidth(true);
    scrollPane.setStyle("-fx-background: transparent; -fx-background-color: transparent;");
    VBox.setVgrow(scrollPane, Priority.ALWAYS);

    root.getChildren().addAll(header, filterField, scrollPane);
    rootStack.getChildren().add(root);
    banner.attachTo(rootStack);
  }

  public void setOnEditMovie(Consumer<Movie> callback) {
    this.onEditMovie = callback;
  }

  public void onShow() {
    refresh();
  }

  private final DataLoader<java.util.List<Movie>> dataLoader = new DataLoader<>();

  private void refresh() {
    listBox.getChildren().clear();
    var spinner = new ProgressIndicator();
    spinner.setPrefSize(40, 40);
    listBox.getChildren().add(spinner);

    var filter = filterField.getText();

    dataLoader.load(
        () -> catalogService.browseAll(null, "title", false),
        movies -> {
          listBox.getChildren().clear();
          for (var movie : movies) {
            if (filter != null && !filter.isBlank()) {
              var f = filter.toLowerCase();
              if (!movie.title().toLowerCase().contains(f)
                  && !movie.genre().toLowerCase().contains(f)
                  && !movie.description().toLowerCase().contains(f)) continue;
            }
            listBox.getChildren().add(createRow(movie));
          }
          if (listBox.getChildren().isEmpty()) {
            listBox.getChildren().add(new Label("No videos found."));
          }
        },
        ex -> {
          LOG.warning("[admin] Error loading videos: " + ex.getMessage());
          listBox.getChildren().clear();
          listBox.getChildren().add(new Label("Failed to load videos."));
        });
  }

  public void cancelLoad() {
    dataLoader.cancel();
  }

  private HBox createRow(Movie movie) {
    var row = new HBox(12);
    row.setAlignment(Pos.CENTER_LEFT);
    row.setPadding(new Insets(6, 8, 6, 8));
    row.setStyle(
        "-fx-background-color: #1a1a2e; -fx-background-radius: 6; -fx-border-color: #333; -fx-border-radius: 6;");

    // Small thumbnail
    var thumb = new StackPane();
    thumb.setPrefSize(64, 36);
    thumb.setMinSize(64, 36);
    PlaybackState.loadThumbnail(thumb, movie.thumbnailPath(), 64, 36);

    var title = new Label(movie.title());
    title.setStyle("-fx-text-fill: #e0e0e0; -fx-font-size: 13; -fx-font-weight: bold;");
    title.setMaxWidth(300);

    var meta = new Label(movie.genre() + " · " + movie.releaseYear());
    meta.setStyle("-fx-text-fill: #888; -fx-font-size: 11;");

    var info = new VBox(2, title, meta);
    HBox.setHgrow(info, Priority.ALWAYS);

    var editBtn = new Button(" Edit");
    editBtn.setGraphic(IconLoader.plainIcon("edit", 12, javafx.scene.paint.Color.web("#e94560")));
    editBtn.getStyleClass().add("btn-outline");
    editBtn.setStyle("-fx-font-size: 11;");
    editBtn.setOnAction(
        e -> {
          if (onEditMovie != null) onEditMovie.accept(movie);
        });

    var deleteBtn = new Button(" Delete");
    deleteBtn.setGraphic(IconLoader.plainIcon("delete", 12, javafx.scene.paint.Color.WHITE));
    deleteBtn.getStyleClass().add("btn-delete");
    deleteBtn.setOnAction(e -> confirmDelete(movie));

    row.getChildren().addAll(thumb, info, editBtn, deleteBtn);
    return row;
  }

  private void confirmDelete(Movie movie) {
    var yesBtn = new ButtonType("Yes");
    var alert =
        new Alert(
            Alert.AlertType.CONFIRMATION,
            "Delete \""
                + movie.title()
                + "\"? This will also remove all watch history for this video.",
            yesBtn,
            new ButtonType("No", ButtonBar.ButtonData.CANCEL_CLOSE));
    alert.setTitle("Confirm Delete");
    alert.setHeaderText(null);
    alert
        .showAndWait()
        .ifPresent(
            btn -> {
              if (btn == yesBtn) {
                var id = movie.id();
                var title = movie.title();
                new BackgroundTask() {
                  @Override
                  protected void execute() throws Exception {
                    watchHistoryService.deleteWatchHistoryForVideo(id);
                    catalogService.deleteVideo(id);
                  }

                  @Override
                  protected void onSuccess() {
                    LOG.info("[admin] Deleted video: " + title + " (" + id + ")");
                    banner.success("Deleted: " + title);
                    refresh();
                  }

                  @Override
                  protected void onFailure(Exception ex) {
                    LOG.severe("[admin] Delete failed: " + ex.getMessage());
                    banner.error("Delete failed: " + ex.getMessage());
                  }
                }.start();
              }
            });
  }

  public void showBanner(String message) {
    banner.success(message);
  }

  public StackPane getRoot() {
    return rootStack;
  }
}
