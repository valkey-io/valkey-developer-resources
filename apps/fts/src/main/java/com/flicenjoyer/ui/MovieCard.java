package com.flicenjoyer.ui;

import com.flicenjoyer.model.Movie;
import javafx.geometry.Insets;
import javafx.scene.control.Label;
import javafx.scene.layout.HBox;
import javafx.scene.layout.Priority;
import javafx.scene.layout.StackPane;
import javafx.scene.layout.VBox;

/** Shared factory for catalog card widgets used across Browse, Search, and History views. */
public final class MovieCard {
  private MovieCard() {}

  private static final double CARD_WIDTH = 180;
  private static final double THUMB_HEIGHT = 100;

  /**
   * Creates a card with thumbnail, title, genre/year meta, and rating. Callers can add overlays to
   * the returned thumb pane or append children to the card VBox.
   */
  public static VBox create(Movie movie, long resumeSec) {
    var card = new VBox();
    card.getStyleClass().add("card");
    card.setPrefWidth(CARD_WIDTH);

    var thumb = new StackPane();
    thumb.setPrefHeight(THUMB_HEIGHT);
    thumb.getStyleClass().add("card-thumb");
    PlaybackState.loadThumbnail(thumb, movie.thumbnailPath(), CARD_WIDTH, THUMB_HEIGHT);
    PlaybackState.addProgressBar(thumb, movie, resumeSec);

    var title = new Label(movie.title());
    title.getStyleClass().add("card-title");
    var meta = new Label(movie.releaseYear() + " · " + movie.genre());
    meta.getStyleClass().add("card-meta");
    var rating = new Label("⭐ " + movie.rating());
    rating.getStyleClass().add("card-rating");

    var body = new VBox(2, title, meta, rating);
    body.setPadding(new Insets(8));
    card.getChildren().addAll(thumb, body);
    return card;
  }

  /** Returns the thumbnail StackPane (first child) for adding overlays. */
  public static StackPane thumb(VBox card) {
    return (StackPane) card.getChildren().getFirst();
  }

  /** Appends a full-width action button row to the card. */
  public static void addActionButton(VBox card, PlaybackState.Action action, Runnable onClick) {
    var btn = PlaybackState.createButton(action);
    btn.setMaxWidth(Double.MAX_VALUE);
    btn.setOnAction(e -> onClick.run());
    var row = new HBox(btn);
    row.setPadding(new Insets(0, 8, 8, 8));
    HBox.setHgrow(btn, Priority.ALWAYS);
    card.getChildren().add(row);
  }
}
