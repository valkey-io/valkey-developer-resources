package com.flicenjoyer.ui;

import com.flicenjoyer.model.Genre;
import com.flicenjoyer.model.Movie;
import com.flicenjoyer.service.CatalogService;
import com.flicenjoyer.service.WatchHistoryService;
import javafx.geometry.Insets;
import javafx.geometry.Pos;
import javafx.scene.control.ComboBox;
import javafx.scene.control.Label;
import javafx.scene.control.ProgressIndicator;
import javafx.scene.layout.FlowPane;
import javafx.scene.layout.HBox;
import javafx.scene.layout.VBox;

/** Browse view displaying the catalog as a filterable, sortable card grid. */
public class CatalogView {

  private static final java.util.logging.Logger LOG =
      java.util.logging.Logger.getLogger(CatalogView.class.getName());

  private final VBox root = new VBox(16);
  private final FlowPane cardGrid = new FlowPane(16, 16);
  private final CatalogService catalogService;
  private WatchHistoryService watchHistoryService;
  private java.util.function.Consumer<Movie> onPlayMovie;

  private final ComboBox<String> genreBox;
  private final ComboBox<String> sortBox;

  public CatalogView(CatalogService catalogService) {
    this.catalogService = catalogService;
    root.setPadding(new Insets(20));

    genreBox = new ComboBox<>();
    genreBox.getItems().addAll(Genre.displayNamesWithAll());
    genreBox.setValue("All");

    sortBox = new ComboBox<>();
    sortBox.getItems().addAll("Rating ↓", "Year ↓", "Title A-Z");
    sortBox.setValue("Rating ↓");

    var filterBar = new HBox(12);
    filterBar.setAlignment(Pos.CENTER_LEFT);
    filterBar
        .getChildren()
        .addAll(
            UiFactory.styledLabel("Genre:"), genreBox,
            UiFactory.styledLabel("Sort:"), sortBox);

    genreBox.setOnAction(e -> refresh(genreBox.getValue(), sortBox.getValue()));
    sortBox.setOnAction(e -> refresh(genreBox.getValue(), sortBox.getValue()));

    cardGrid.setPrefWrapLength(800);

    root.getChildren().addAll(filterBar, UiFactory.scrollPane(cardGrid));

    refresh("All", "Rating ↓");
  }

  private record CatalogData(java.util.List<Movie> movies, java.util.Map<String, Long> resumeMap) {}

  private final DataLoader<CatalogData> dataLoader = new DataLoader<>();

  private void refresh(String genre, String sortLabel) {
    var sortField =
        switch (sortLabel) {
          case "Rating ↓" -> "rating";
          case "Year ↓" -> "releaseYear";
          default -> "title";
        };
    var descending = !sortLabel.equals("Title A-Z");

    cardGrid.getChildren().clear();
    var spinner = new ProgressIndicator();
    spinner.setPrefSize(40, 40);
    cardGrid.getChildren().add(spinner);

    dataLoader.load(
        () -> {
          var movies = catalogService.browseAll(genre, sortField, descending);
          var resumeMap = new java.util.HashMap<String, Long>();
          if (watchHistoryService != null && !movies.isEmpty()) {
            try {
              resumeMap.putAll(
                  watchHistoryService.getResumePoints(
                      movies.stream().map(m -> m.id()).toList()));
            } catch (InterruptedException e) {
              Thread.currentThread().interrupt();
            } catch (Exception e) {
              // Fall back to empty resume map on failure
            }
          }
          return new CatalogData(movies, resumeMap);
        },
        data -> {
          cardGrid.getChildren().clear();
          if (data.movies().isEmpty()) {
            cardGrid.getChildren().add(new Label("No videos found. Upload some first!"));
            return;
          }
          for (var movie : data.movies()) cardGrid.getChildren().add(createCard(movie, data.resumeMap().getOrDefault(movie.id(), 0L)));
        },
        ex -> {
          LOG.warning("[browse] Error: " + ex.getMessage());
          cardGrid.getChildren().clear();
          cardGrid.getChildren().add(new Label("Failed to load catalog."));
        });
  }

  public void cancelLoad() {
    dataLoader.cancel();
  }

  private VBox createCard(Movie movie, long resumeSec) {
    var action = PlaybackState.resolve(movie, resumeSec);
    var card = MovieCard.create(movie, resumeSec);
    PlaybackState.addProgressBar(MovieCard.thumb(card), movie, resumeSec);
    MovieCard.addActionButton(
        card,
        action,
        () -> {
          if (onPlayMovie != null) onPlayMovie.accept(movie);
        });
    card.setOnMouseClicked(
        e -> {
          if (onPlayMovie != null) onPlayMovie.accept(movie);
        });
    return card;
  }

  public void setWatchHistoryService(WatchHistoryService svc) {
    this.watchHistoryService = svc;
  }

  public void setOnPlayMovie(java.util.function.Consumer<Movie> callback) {
    this.onPlayMovie = callback;
  }

  public void onShow() {
    refresh(genreBox.getValue(), sortBox.getValue());
  }

  public VBox getRoot() {
    return root;
  }
}
