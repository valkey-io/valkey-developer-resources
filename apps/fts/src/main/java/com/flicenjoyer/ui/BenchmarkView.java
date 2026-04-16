package com.flicenjoyer.ui;

import com.flicenjoyer.service.BenchmarkService;
import com.flicenjoyer.service.BenchmarkService.BenchmarkResult;
import com.flicenjoyer.service.CatalogService;
import com.flicenjoyer.service.WatchHistoryService;
import java.util.logging.Logger;
import javafx.geometry.Insets;
import javafx.geometry.Pos;
import javafx.scene.control.*;
import javafx.scene.layout.*;

/** Runs and displays performance benchmarks for search, resume, and aggregation operations. */
public class BenchmarkView {

  private static final Logger LOG = Logger.getLogger(BenchmarkView.class.getName());

  private final VBox root = new VBox(16);
  private final CatalogService catalogService;
  private final WatchHistoryService watchHistoryService;
  private final com.flicenjoyer.service.AggregationService aggregationService;

  private final ComboBox<String> operationBox = new ComboBox<>();
  private final Spinner<Integer> iterationSpinner = new Spinner<>(10, 10000, 1000, 100);
  private final ProgressBar progressBar = new ProgressBar(0);
  private final Label progressLabel = new Label("Ready");
  private final Label medianLabel = new Label("—");
  private final Label p95Label = new Label("—");
  private final Label p99Label = new Label("—");
  private final Label opsLabel = new Label("—");
  private final Button runBtn = new Button(" Run Benchmark");
  private BackgroundTask currentBenchmark;

  public BenchmarkView(
      CatalogService catalogService,
      WatchHistoryService watchHistoryService,
      com.flicenjoyer.service.AggregationService aggregationService) {
    this.catalogService = catalogService;
    this.watchHistoryService = watchHistoryService;
    this.aggregationService = aggregationService;
    root.setPadding(new Insets(20));

    operationBox
        .getItems()
        .addAll(
            "Prefix Search",
            "Fuzzy Search",
            "Browse All",
            "Resume Point Retrieval",
            "Aggregate: Genre Summary");
    operationBox.setValue("Prefix Search");

    iterationSpinner.setEditable(true);
    iterationSpinner.setPrefWidth(100);

    runBtn.getStyleClass().add("btn-primary");
    runBtn.setGraphic(IconLoader.plainIcon("nav-bench", 14, javafx.scene.paint.Color.WHITE));
    runBtn.setOnAction(e -> runBenchmark());

    var configRow = new HBox(12);
    configRow.setAlignment(Pos.CENTER_LEFT);
    configRow
        .getChildren()
        .addAll(
            UiFactory.styledLabel("Operation:"),
            operationBox,
            UiFactory.styledLabel("Iterations:"),
            iterationSpinner,
            runBtn);

    progressBar.setMaxWidth(Double.MAX_VALUE);
    progressBar.setPrefHeight(8);
    HBox.setHgrow(progressBar, Priority.ALWAYS);
    var progressRow = new HBox(10, progressLabel, progressBar);
    progressRow.setAlignment(Pos.CENTER_LEFT);

    var grid = new GridPane();
    grid.setHgap(16);
    grid.setVgap(16);
    grid.add(metricCard("Median", medianLabel), 0, 0);
    grid.add(metricCard("p95", p95Label), 1, 0);
    grid.add(metricCard("p99", p99Label), 0, 1);
    grid.add(metricCard("Ops/sec", opsLabel), 1, 1);
    var col = new ColumnConstraints();
    col.setPercentWidth(50);
    grid.getColumnConstraints().addAll(col, col);

    root.getChildren().addAll(configRow, progressRow, grid);
  }

  private void runBenchmark() {
    if (currentBenchmark != null) currentBenchmark.cancel();

    var operation = operationBox.getValue();
    var iterations = iterationSpinner.getValue();
    runBtn.setDisable(true);
    progressBar.setProgress(0);
    progressLabel.setText("Running " + operation + "...");
    clearResults();

    currentBenchmark =
        new BackgroundTask() {
          private BenchmarkResult result;

          @Override
          protected void execute() throws Exception {
            BenchmarkService.BenchmarkTask task =
                switch (operation) {
                  case "Prefix Search" -> () -> catalogService.searchPrefix("S", 10);
                  case "Fuzzy Search" -> () -> catalogService.searchFuzzy("Incetpion", 10);
                  case "Browse All" -> () -> catalogService.browseAll(null, "title", false);
                  case "Resume Point Retrieval" ->
                      () -> {
                        var movies = catalogService.browseAll(null, "title", false);
                        if (!movies.isEmpty())
                          watchHistoryService.getResumePoint(movies.getFirst().id());
                      };
                  case "Aggregate: Genre Summary" -> aggregationService::catalogSummaryByGenre;
                  default -> () -> {};
                };

            result =
                BenchmarkService.benchmark(
                    task,
                    iterations,
                    completed -> {
                      javafx.application.Platform.runLater(
                          () -> progressBar.setProgress((double) completed / iterations));
                    });
            LOG.info(
                "[bench] "
                    + operation
                    + ": median="
                    + result.medianMs()
                    + "ms, p95="
                    + result.p95Ms()
                    + "ms, p99="
                    + result.p99Ms()
                    + "ms, ops/sec="
                    + result.opsPerSecond());
          }

          @Override
          protected void onSuccess() {
            medianLabel.setText(String.format("%.2f ms", result.medianMs()));
            p95Label.setText(String.format("%.2f ms", result.p95Ms()));
            p99Label.setText(String.format("%.2f ms", result.p99Ms()));
            opsLabel.setText(String.format("%.0f", result.opsPerSecond()));
            progressBar.setProgress(1.0);
            progressLabel.setText("Done — " + iterations + " iterations");
          }

          @Override
          protected void onFailure(Exception ex) {
            LOG.warning("[bench] Failed: " + ex.getMessage());
            progressLabel.setText("Failed: " + ex.getMessage());
          }

          @Override
          protected void onFinally() {
            runBtn.setDisable(false);
            currentBenchmark = null;
          }
        };
    currentBenchmark.start();
  }

  private void clearResults() {
    medianLabel.setText("—");
    p95Label.setText("—");
    p99Label.setText("—");
    opsLabel.setText("—");
  }

  private VBox metricCard(String title, Label valueLabel) {
    valueLabel.setStyle("-fx-font-size: 24; -fx-font-weight: bold; -fx-text-fill: #e94560;");
    var titleLabel = new Label(title);
    titleLabel.setStyle("-fx-font-size: 11; -fx-text-fill: #888; -fx-text-transform: uppercase;");
    var card = new VBox(4, valueLabel, titleLabel);
    card.setAlignment(Pos.CENTER);
    card.setPadding(new Insets(16));
    card.setStyle(
        "-fx-background-color: #1a1a2e; -fx-border-color: #333; -fx-border-radius: 6; -fx-background-radius: 6;");
    return card;
  }

  public void cancelBenchmark() {
    if (currentBenchmark != null) currentBenchmark.cancel();
  }

  public VBox getRoot() {
    return root;
  }
}
