package com.flicenjoyer.ui;

import com.flicenjoyer.model.AggregationResult;
import com.flicenjoyer.service.AggregationService;
import java.util.List;
import java.util.logging.Logger;
import javafx.geometry.Insets;
import javafx.scene.control.*;
import javafx.scene.layout.*;

/** FT.AGGREGATE analytics reports — top titles by viewers and catalog summary by genre. */
public class ReportsView {

  private static final Logger LOG = Logger.getLogger(ReportsView.class.getName());

  private final VBox root = new VBox(20);
  private final AggregationService aggregationService;

  private final VBox topTitlesBox = new VBox(8);
  private final VBox genreSummaryBox = new VBox(8);

  public ReportsView(AggregationService aggregationService) {
    this.aggregationService = aggregationService;
    root.setPadding(new Insets(20));

    // Top Titles section
    var topHeader = new HBox(8);
    var topLabel = new Label("Top Titles by Viewers");
    topLabel.setStyle("-fx-text-fill: #ccc; -fx-font-size: 14; -fx-font-weight: bold;");
    var topBtn = new Button(" Generate");
    topBtn.getStyleClass().add("btn-primary");
    topBtn.setStyle("-fx-font-size: 11;");
    topBtn.setOnAction(e -> loadTopTitles());
    var topSpacer = new Region();
    HBox.setHgrow(topSpacer, Priority.ALWAYS);
    topHeader.getChildren().addAll(topLabel, topSpacer, topBtn);

    var separator = new Separator();
    separator.setStyle("-fx-background-color: #333;");

    // Genre Summary section
    var genreHeader = new HBox(8);
    var genreLabel = new Label("Catalog Summary by Genre");
    genreLabel.setStyle("-fx-text-fill: #ccc; -fx-font-size: 14; -fx-font-weight: bold;");
    var genreBtn = new Button(" Generate");
    genreBtn.getStyleClass().add("btn-primary");
    genreBtn.setStyle("-fx-font-size: 11;");
    genreBtn.setOnAction(e -> loadGenreSummary());
    var genreSpacer = new Region();
    HBox.setHgrow(genreSpacer, Priority.ALWAYS);
    genreHeader.getChildren().addAll(genreLabel, genreSpacer, genreBtn);

    root.getChildren().addAll(topHeader, topTitlesBox, separator, genreHeader, genreSummaryBox);
  }

  private void loadTopTitles() {
    topTitlesBox.getChildren().clear();
    var spinner = new ProgressIndicator();
    spinner.setPrefSize(30, 30);
    topTitlesBox.getChildren().add(spinner);

    new BackgroundTask() {
      private List<AggregationResult> results;

      @Override
      protected void execute() throws Exception {
        results = aggregationService.topTitlesByViewers(20);
      }

      @Override
      protected void onSuccess() {
        topTitlesBox.getChildren().clear();
        if (results.isEmpty()) {
          topTitlesBox.getChildren().add(new Label("No watch data yet."));
          return;
        }
        var table = createTable(new String[] {"Title", "Viewers"});
        for (var r : results) {
          table
              .getItems()
              .add(
                  new String[] {
                    r.label(), r.metrics().getOrDefault("viewerCount", "0").toString()
                  });
        }
        topTitlesBox.getChildren().add(table);
      }

      @Override
      protected void onFailure(Exception ex) {
        LOG.warning("[reports] Top titles failed: " + ex.getMessage());
        topTitlesBox.getChildren().clear();
        topTitlesBox.getChildren().add(new Label("Failed to generate report."));
      }
    }.start();
  }

  private void loadGenreSummary() {
    genreSummaryBox.getChildren().clear();
    var spinner = new ProgressIndicator();
    spinner.setPrefSize(30, 30);
    genreSummaryBox.getChildren().add(spinner);

    new BackgroundTask() {
      private List<AggregationResult> results;

      @Override
      protected void execute() throws Exception {
        results = aggregationService.catalogSummaryByGenre();
      }

      @Override
      protected void onSuccess() {
        genreSummaryBox.getChildren().clear();
        if (results.isEmpty()) {
          genreSummaryBox.getChildren().add(new Label("No catalog data yet."));
          return;
        }
        var table = createTable(new String[] {"Genre", "Titles", "Avg Rating"});
        for (var r : results) {
          var avgRating = r.metrics().getOrDefault("avgRating", "0").toString();
          try {
            avgRating = String.format("%.1f", Double.parseDouble(avgRating));
          } catch (Exception ignored) {
          }
          table
              .getItems()
              .add(
                  new String[] {
                    r.label(), r.metrics().getOrDefault("titleCount", "0").toString(), avgRating
                  });
        }
        genreSummaryBox.getChildren().add(table);
      }

      @Override
      protected void onFailure(Exception ex) {
        LOG.warning("[reports] Genre summary failed: " + ex.getMessage());
        genreSummaryBox.getChildren().clear();
        genreSummaryBox.getChildren().add(new Label("Failed to generate report."));
      }
    }.start();
  }

  @SuppressWarnings("unchecked")
  private TableView<String[]> createTable(String[] columns) {
    var table = new TableView<String[]>();
    table.setColumnResizePolicy(TableView.CONSTRAINED_RESIZE_POLICY_ALL_COLUMNS);
    table.setPrefHeight(250);
    table.setStyle("-fx-background-color: #1a1a2e;");
    for (int i = 0; i < columns.length; i++) {
      final int col = i;
      var tc = new TableColumn<String[], String>(columns[i]);
      tc.setCellValueFactory(
          data -> new javafx.beans.property.SimpleStringProperty(data.getValue()[col]));
      tc.setStyle("-fx-text-fill: #ccc;");
      table.getColumns().add(tc);
    }
    return table;
  }

  public VBox getRoot() {
    return root;
  }
}
