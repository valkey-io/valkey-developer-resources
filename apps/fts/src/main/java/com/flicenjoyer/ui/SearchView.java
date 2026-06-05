package com.flicenjoyer.ui;

import com.flicenjoyer.model.Movie;
import com.flicenjoyer.service.CatalogService;
import com.flicenjoyer.service.WatchHistoryService;
import java.util.function.Consumer;
import java.util.logging.Logger;
import javafx.geometry.Insets;
import javafx.geometry.Pos;
import javafx.scene.control.Label;
import javafx.scene.control.TextField;
import javafx.scene.layout.*;

/** Typeahead search view with async prefix and fuzzy matching against the catalog. */
public class SearchView {

  private static final Logger LOG = Logger.getLogger(SearchView.class.getName());

  private final VBox root = new VBox(16);
  private final FlowPane cardGrid = new FlowPane(16, 16);
  private final TextField searchField = new TextField();
  private final CatalogService catalogService;
  private WatchHistoryService watchHistoryService;
  private Consumer<Movie> onPlayMovie;

  // Detail pane
  private final HBox detailPane = new HBox(16);

  private javafx.animation.PauseTransition debounce;

  public SearchView(CatalogService catalogService) {
    this.catalogService = catalogService;
    root.setPadding(new Insets(20));

    searchField.setPromptText("Search movies & shows...");
    searchField.setMaxWidth(Double.MAX_VALUE);
    var searchIcon = IconLoader.plainIcon("nav-search", 18, javafx.scene.paint.Color.web("#888"));
    var searchBar = new HBox(8, searchIcon, searchField);
    searchBar.setAlignment(Pos.CENTER_LEFT);
    HBox.setHgrow(searchField, Priority.ALWAYS);

    // Typeahead: tiny debounce (50ms) to batch rapid keystrokes, then async search
    searchField
        .textProperty()
        .addListener(
            (obs, oldVal, newVal) -> {
              if (debounce != null) debounce.stop();
              debounce = new javafx.animation.PauseTransition(javafx.util.Duration.millis(50));
              debounce.setOnFinished(e -> doSearch(newVal));
              debounce.play();
            });

    cardGrid.setPrefWrapLength(800);

    detailPane.setPadding(new Insets(16));
    detailPane.setStyle(
        "-fx-background-color: #1a1a2e; -fx-border-color: #333; -fx-border-radius: 6; -fx-background-radius: 6;");
    detailPane.setVisible(false);
    detailPane.setManaged(false);

    root.getChildren().addAll(searchBar, UiFactory.scrollPane(cardGrid), detailPane);
  }

  public void setWatchHistoryService(WatchHistoryService svc) {
    this.watchHistoryService = svc;
  }

  public void setOnPlayMovie(Consumer<Movie> callback) {
    this.onPlayMovie = callback;
  }

  private final java.util.concurrent.atomic.AtomicReference<String> pendingQuery =
      new java.util.concurrent.atomic.AtomicReference<>();
  private final java.util.concurrent.atomic.AtomicBoolean searchRunning =
      new java.util.concurrent.atomic.AtomicBoolean(false);

  private void doSearch(String query) {
    detailPane.setVisible(false);
    detailPane.setManaged(false);

    if (query == null || query.isBlank()) {
      pendingQuery.set(null);
      cardGrid.getChildren().clear();
      return;
    }

    pendingQuery.set(query.trim());
    if (searchRunning.compareAndSet(false, true)) {
      Thread.startVirtualThread(this::searchLoop);
    }
  }

  private void searchLoop() {
    while (true) {
      var query = pendingQuery.getAndSet(null);
      if (query == null) {
        searchRunning.set(false);
        return;
      }

      try {
        var results = catalogService.search(query, 20);
        // Check if superseded before fetching resume points
        if (pendingQuery.get() != null) continue;

        var resumePoints = new java.util.HashMap<String, Long>();
        if (watchHistoryService != null) {
          for (var m : results) {
            if (pendingQuery.get() != null) break;
            try {
              resumePoints.put(m.id(), watchHistoryService.getResumePoint(m.id()));
            } catch (InterruptedException e) {
              Thread.currentThread().interrupt();
              break;
            } catch (Exception e) {
              resumePoints.put(m.id(), 0L);
            }
          }
        }
        // Check again — discard if superseded
        if (pendingQuery.get() != null) continue;

        LOG.info("[search] Query: '" + query + "' → " + results.size() + " results");
        javafx.application.Platform.runLater(
            () -> {
              cardGrid.getChildren().clear();
              if (results.isEmpty()) {
                cardGrid.getChildren().add(new Label("No results found."));
                return;
              }
              for (var movie : results) {
                cardGrid
                    .getChildren()
                    .add(createCard(movie, resumePoints.getOrDefault(movie.id(), 0L)));
              }
            });
      } catch (Exception ex) {
        if (pendingQuery.get() == null) {
          LOG.warning("[search] Error: " + ex.getMessage());
          javafx.application.Platform.runLater(
              () -> {
                cardGrid.getChildren().clear();
                cardGrid.getChildren().add(new Label("Search failed."));
              });
        }
      }
    }
  }

  public void cancelSearch() {
    pendingQuery.set(null);
  }

  private VBox createCard(Movie movie, long resumeSec) {
    var card = MovieCard.create(movie, resumeSec);
    card.setOnMouseClicked(e -> showDetail(movie));
    return card;
  }

  private void showDetail(Movie movie) {
    detailPane.getChildren().clear();

    var thumb = new StackPane();
    thumb.setPrefSize(140, 80);
    thumb.setMinSize(140, 80);
    thumb.setMaxSize(140, 80);
    PlaybackState.loadThumbnail(thumb, movie.thumbnailPath(), 140, 80);

    var title = new Label(movie.title());
    title.setStyle("-fx-text-fill: #e94560; -fx-font-size: 15; -fx-font-weight: bold;");
    var meta =
        new Label(
            movie.releaseYear()
                + " · "
                + movie.genre()
                + " · "
                + String.format("%.1f", movie.durationMinutes())
                + " min · ⭐ "
                + movie.rating());
    meta.getStyleClass().add("card-meta");
    var desc = new Label(movie.description());
    desc.setWrapText(true);
    desc.setStyle("-fx-text-fill: #ccc; -fx-font-size: 13;");

    var action = PlaybackState.resolve(movie, watchHistoryService);
    var playBtn = PlaybackState.createButton(action);
    playBtn.setOnAction(
        e -> {
          if (onPlayMovie != null) onPlayMovie.accept(movie);
        });

    var info = new VBox(4, title, meta, desc, playBtn);
    HBox.setHgrow(info, Priority.ALWAYS);

    detailPane.getChildren().addAll(thumb, info);
    detailPane.setVisible(true);
    detailPane.setManaged(true);
  }

  public VBox getRoot() {
    return root;
  }
}
