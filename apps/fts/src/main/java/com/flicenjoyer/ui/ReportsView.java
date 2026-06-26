package com.flicenjoyer.ui;

import com.flicenjoyer.model.AggregationResult;
import com.flicenjoyer.service.AggregationService;
import java.util.List;
import java.util.logging.Logger;
import javafx.geometry.Insets;
import javafx.scene.control.*;
import javafx.scene.layout.VBox;

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

    var separator = new Separator();
    separator.setStyle("-fx-background-color: #333;");

    root.getChildren()
        .addAll(
            UiFactory.sectionHeader("Top Titles by Viewers", this::loadTopTitles),
            topTitlesBox,
            separator,
            UiFactory.sectionHeader("Catalog Summary by Genre", this::loadGenreSummary),
            genreSummaryBox);
  }

  private interface ReportSupplier {
    List<AggregationResult> get() throws Exception;
  }

  private void loadReport(
      VBox container,
      String emptyMsg,
      String[] columns,
      ReportSupplier supplier,
      java.util.function.Function<AggregationResult, String[]> rowMapper) {
    container.getChildren().clear();
    var spinner = new ProgressIndicator();
    spinner.setPrefSize(30, 30);
    container.getChildren().add(spinner);

    new BackgroundTask() {
      private List<AggregationResult> results;

      @Override
      protected void execute() throws Exception {
        results = supplier.get();
      }

      @Override
      protected void onSuccess() {
        container.getChildren().clear();
        if (results.isEmpty()) {
          container.getChildren().add(new Label(emptyMsg));
          return;
        }
        var table = createTable(columns);
        for (var r : results) table.getItems().add(rowMapper.apply(r));
        container.getChildren().add(table);
      }

      @Override
      protected void onFailure(Exception ex) {
        LOG.warning("[reports] Failed: " + ex.getMessage());
        container.getChildren().clear();
        container.getChildren().add(new Label("Failed to generate report."));
      }
    }.start();
  }

  private void loadTopTitles() {
    loadReport(
        topTitlesBox,
        "No watch data yet.",
        new String[] {"Title", "Viewers"},
        () -> aggregationService.topTitlesByViewers(20),
        r -> new String[] {r.label(), r.metrics().getOrDefault("viewerCount", "0").toString()});
  }

  private void loadGenreSummary() {
    loadReport(
        genreSummaryBox,
        "No catalog data yet.",
        new String[] {"Genre", "Titles", "Avg Rating"},
        aggregationService::catalogSummaryByGenre,
        r -> {
          var avgRating = r.metrics().getOrDefault("avgRating", "0").toString();
          try {
            avgRating = String.format("%.1f", Double.parseDouble(avgRating));
          } catch (Exception ignored) {
          }
          return new String[] {
            r.label(), r.metrics().getOrDefault("titleCount", "0").toString(), avgRating
          };
        });
  }

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
