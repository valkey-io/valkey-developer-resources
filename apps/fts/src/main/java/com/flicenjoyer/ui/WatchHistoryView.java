package com.flicenjoyer.ui;

import com.flicenjoyer.model.Movie;
import com.flicenjoyer.model.WatchHistoryEntry;
import com.flicenjoyer.service.CatalogService;
import com.flicenjoyer.service.WatchHistoryService;
import java.time.Instant;
import java.time.LocalDate;
import java.time.ZoneId;
import java.util.function.Consumer;
import java.util.logging.Logger;
import javafx.geometry.Insets;
import javafx.geometry.Pos;
import javafx.scene.control.Label;
import javafx.scene.control.ProgressIndicator;
import javafx.scene.layout.*;

/** Watch history view showing per-user session cards with resume progress and status badges. */
public class WatchHistoryView {

  private static final Logger LOG = Logger.getLogger(WatchHistoryView.class.getName());

  private final VBox root = new VBox(16);
  private final FlowPane cardGrid = new FlowPane(16, 16);
  private final WatchHistoryService watchHistoryService;
  private final CatalogService catalogService;
  private Consumer<Movie> onResumeMovie;

  public WatchHistoryView(WatchHistoryService watchHistoryService, CatalogService catalogService) {
    this.watchHistoryService = watchHistoryService;
    this.catalogService = catalogService;
    root.setPadding(new Insets(20));
    cardGrid.setPrefWrapLength(800);

    var header = new Label("Watch History");
    header.setStyle("-fx-text-fill: #ccc; -fx-font-size: 15px; -fx-font-weight: bold;");

    root.getChildren().addAll(header, UiFactory.scrollPane(cardGrid));
  }

  public void setOnResumeMovie(Consumer<Movie> callback) {
    this.onResumeMovie = callback;
  }

  private record HistoryData(
      java.util.List<WatchHistoryEntry> entries, java.util.Map<String, Movie> movieMap) {}

  private final DataLoader<HistoryData> dataLoader = new DataLoader<>();

  public void onShow() {
    cardGrid.getChildren().clear();
    var spinner = new ProgressIndicator();
    spinner.setPrefSize(40, 40);
    cardGrid.getChildren().add(spinner);

    dataLoader.load(
        () -> {
          var entries = watchHistoryService.getUserHistory();
          var movieMap = new java.util.LinkedHashMap<String, Movie>();
          for (var e : entries) movieMap.put(e.catalogId(), catalogService.getById(e.catalogId()));
          return new HistoryData(entries, movieMap);
        },
        data -> {
          cardGrid.getChildren().clear();
          if (data.entries().isEmpty()) {
            cardGrid
                .getChildren()
                .add(new Label("No watch history yet. Browse and play some videos!"));
            return;
          }
          for (var entry : data.entries())
            cardGrid.getChildren().add(createCard(entry, data.movieMap().get(entry.catalogId())));
        },
        ex -> {
          LOG.warning("[history] Error loading history: " + ex.getMessage());
          cardGrid.getChildren().clear();
          cardGrid.getChildren().add(new Label("Failed to load watch history."));
        });
  }

  public void cancelLoad() {
    dataLoader.cancel();
  }

  private VBox createCard(WatchHistoryEntry entry, Movie movie) {
    var card = new VBox();
    card.getStyleClass().add("card");
    card.setPrefWidth(180);

    var thumb = new StackPane();
    thumb.setPrefHeight(100);
    thumb.getStyleClass().add("card-thumb");

    PlaybackState.loadThumbnail(thumb, movie != null ? movie.thumbnailPath() : "", 180, 100);

    // Status badge
    var badge = new Label(entry.completed() ? "Completed" : "In Progress");
    var badgeColor = entry.completed() ? "rgba(82,183,136,0.9)" : "rgba(244,162,97,0.9)";
    badge.setStyle(
        "-fx-background-color: "
            + badgeColor
            + "; -fx-text-fill: #1a1a2e; -fx-padding: 2 8; -fx-background-radius: 3; -fx-font-size: 10; -fx-font-weight: bold;");
    StackPane.setAlignment(badge, Pos.TOP_LEFT);
    StackPane.setMargin(badge, new Insets(6, 0, 0, 6));
    thumb.getChildren().add(badge);

    // Timestamp overlay for in-progress
    if (!entry.completed() && movie != null && movie.durationMinutes() > 0) {
      var timeText =
          PlaybackState.formatTime(entry.resumeTimestamp())
              + " / "
              + PlaybackState.formatTime((long) (movie.durationMinutes() * 60));
      var timeLabel = new Label(timeText);
      timeLabel.setStyle(
          "-fx-background-color: rgba(0,0,0,0.7); -fx-text-fill: #ccc; -fx-padding: 2 6; -fx-background-radius: 3; -fx-font-size: 10;");
      StackPane.setAlignment(timeLabel, Pos.BOTTOM_RIGHT);
      StackPane.setMargin(timeLabel, new Insets(0, 6, 6, 0));
      thumb.getChildren().add(timeLabel);
    }

    // Progress bar
    var progressBar = new Region();
    progressBar.setMaxHeight(3);
    progressBar.setMinHeight(3);
    progressBar.setStyle("-fx-background-color: #e94560;");
    double pct = 0;
    if (movie != null && movie.durationMinutes() > 0) {
      pct = Math.min(entry.resumeTimestamp() / (movie.durationMinutes() * 60.0), 1.0);
    }
    if (entry.completed()) pct = 1.0;
    double finalPct = pct;
    progressBar.maxWidthProperty().bind(thumb.widthProperty().multiply(finalPct));
    StackPane.setAlignment(progressBar, Pos.BOTTOM_LEFT);
    thumb.getChildren().add(progressBar);

    // Card body
    var title = new Label(entry.title());
    title.getStyleClass().add("card-title");

    var dateStr =
        LocalDate.ofInstant(Instant.ofEpochSecond(entry.lastWatched()), ZoneId.systemDefault())
            .toString();
    var meta = new Label("Last watched: " + dateStr);
    meta.getStyleClass().add("card-meta");

    var body = new VBox(2, title, meta);
    body.setPadding(new Insets(8));

    card.getChildren().addAll(thumb, body);

    // Action button based on watch state
    if (movie != null) {
      var action = PlaybackState.resolve(movie, watchHistoryService);
      if (action != PlaybackState.Action.PLAY) {
        var actionBtn = PlaybackState.createButton(action);
        actionBtn.setMaxWidth(Double.MAX_VALUE);
        actionBtn.setOnAction(
            e -> {
              if (onResumeMovie != null) onResumeMovie.accept(movie);
            });
        var btnBox = new HBox(actionBtn);
        btnBox.setPadding(new Insets(0, 8, 8, 8));
        HBox.setHgrow(actionBtn, Priority.ALWAYS);
        card.getChildren().add(btnBox);
      }
    }

    // Click card to resume too
    card.setOnMouseClicked(
        e -> {
          if (movie != null && onResumeMovie != null) onResumeMovie.accept(movie);
        });

    return card;
  }

  public VBox getRoot() {
    return root;
  }
}
