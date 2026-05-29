package com.flicenjoyer.ui;

import com.flicenjoyer.service.BenchmarkService;
import com.flicenjoyer.service.BenchmarkService.ConcurrentComparisonResult;
import com.flicenjoyer.service.CatalogService;
import com.flicenjoyer.service.WatchHistoryService;
import java.util.logging.Logger;
import javafx.geometry.Insets;
import javafx.geometry.Pos;
import javafx.scene.control.*;
import javafx.scene.layout.*;

/**
 * Runs concurrent load benchmarks comparing DB-direct vs Valkey-cached throughput under parallel
 * threads.
 */
public class BenchmarkView {

  private static final Logger LOG = Logger.getLogger(BenchmarkView.class.getName());

  private final VBox root = new VBox(16);
  private final CatalogService catalogService;
  private final WatchHistoryService watchHistoryService;
  private final com.flicenjoyer.service.AggregationService aggregationService;

  private final ComboBox<String> operationBox = new ComboBox<>();
  private final Spinner<Integer> threadSpinner = new Spinner<>(1, 128, 32, 8);
  private final Spinner<Integer> opsSpinner = new Spinner<>(10, 10000, 500, 100);
  private final ProgressBar progressBar = new ProgressBar(0);
  private final Label progressLabel = new Label("Ready");
  private final Button runBtn = new Button(" Run Benchmark");
  private BackgroundTask currentBenchmark;

  // Results
  private final Label dbOpsLabel = new Label("—");
  private final Label valkeyOpsLabel = new Label("—");
  private final Label speedupLabel = new Label("—");
  private final Label configLabel = new Label("");

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
        .addAll("Catalog Lookup", "Resume Point Retrieval", "Search (ValkeySearch FTS)");
    operationBox.setValue("Catalog Lookup");

    threadSpinner.setEditable(true);
    threadSpinner.setPrefWidth(80);
    opsSpinner.setEditable(true);
    opsSpinner.setPrefWidth(100);

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
            UiFactory.styledLabel("Threads:"),
            threadSpinner,
            UiFactory.styledLabel("Ops/thread:"),
            opsSpinner,
            runBtn);

    progressBar.setMaxWidth(Double.MAX_VALUE);
    progressBar.setPrefHeight(8);
    HBox.setHgrow(progressBar, Priority.ALWAYS);
    var progressRow = new HBox(10, progressLabel, progressBar);
    progressRow.setAlignment(Pos.CENTER_LEFT);

    // Results grid
    var grid = new GridPane();
    grid.setHgap(24);
    grid.setVgap(20);

    grid.add(headerLabel(""), 0, 0);
    grid.add(headerLabel("DB Direct"), 1, 0);
    grid.add(headerLabel("Valkey"), 2, 0);

    grid.add(rowLabel("Throughput"), 0, 1);
    grid.add(metricCard(dbOpsLabel), 1, 1);
    grid.add(metricCard(valkeyOpsLabel), 2, 1);

    var col0 = new ColumnConstraints();
    col0.setPrefWidth(90);
    var col1 = new ColumnConstraints();
    col1.setPercentWidth(40);
    var col2 = new ColumnConstraints();
    col2.setPercentWidth(40);
    grid.getColumnConstraints().addAll(col0, col1, col2);

    speedupLabel.setStyle("-fx-font-size: 22; -fx-font-weight: bold; -fx-text-fill: #4ecca3;");
    var speedupBox = new HBox(8, UiFactory.styledLabel("Speedup under load:"), speedupLabel);
    speedupBox.setAlignment(Pos.CENTER_LEFT);

    configLabel.setStyle("-fx-font-size: 11; -fx-text-fill: #666;");

    root.getChildren().addAll(configRow, progressRow, grid, speedupBox, configLabel);
  }

  private void runBenchmark() {
    if (currentBenchmark != null) currentBenchmark.cancel();

    var operation = operationBox.getValue();
    int threads = threadSpinner.getValue();
    int opsPerThread = opsSpinner.getValue();
    int totalOps = threads * opsPerThread;
    runBtn.setDisable(true);
    progressBar.setProgress(0);
    progressLabel.setText("Running " + operation + " (" + threads + " threads)...");
    clearResults();

    currentBenchmark =
        new BackgroundTask() {
          private ConcurrentComparisonResult result;

          @Override
          protected void execute() throws Exception {
            var movies = catalogService.browseAll(null, "title", false);
            if (movies.isEmpty()) throw new Exception("No catalog entries to benchmark");
            // Use all available IDs for diverse access pattern (avoids PG buffer cache best-case)
            var ids = movies.stream().map(m -> m.id()).toArray(String[]::new);

            int grandTotal = totalOps * 2;

            // Mixed workload: 7 reads per 1 write (realistic for content platforms)
            var dbCounter = new java.util.concurrent.atomic.AtomicInteger(0);
            var valkeyCounter = new java.util.concurrent.atomic.AtomicInteger(0);

            BenchmarkService.BenchmarkTask dbTask;
            BenchmarkService.BenchmarkTask valkeyTask;

            switch (operation) {
              case "Catalog Lookup" -> {
                dbTask =
                    () -> {
                      var rid = ids[java.util.concurrent.ThreadLocalRandom.current().nextInt(ids.length)];
                      if (dbCounter.incrementAndGet() % 8 == 0) {
                        catalogService.updateRatingInDbOnly(rid, 7.5);
                      } else {
                        catalogService.getByIdFromDb(rid);
                      }
                    };
                valkeyTask =
                    () -> {
                      var rid = ids[java.util.concurrent.ThreadLocalRandom.current().nextInt(ids.length)];
                      if (valkeyCounter.incrementAndGet() % 8 == 0) {
                        catalogService.updateRating(rid, 7.5);
                      } else {
                        catalogService.getById(rid);
                      }
                    };
              }
              case "Resume Point Retrieval" -> {
                dbTask =
                    () -> {
                      var rid = ids[java.util.concurrent.ThreadLocalRandom.current().nextInt(ids.length)];
                      if (dbCounter.incrementAndGet() % 8 == 0) {
                        watchHistoryService.updateResumePointInDbOnly(rid, 100);
                      } else {
                        watchHistoryService.getResumePointFromDb(rid);
                      }
                    };
                valkeyTask =
                    () -> {
                      var rid = ids[java.util.concurrent.ThreadLocalRandom.current().nextInt(ids.length)];
                      if (valkeyCounter.incrementAndGet() % 8 == 0) {
                        watchHistoryService.updateResumePoint(rid, 100);
                      } else {
                        watchHistoryService.getResumePoint(rid);
                      }
                    };
              }
              default -> {
                dbTask = () -> {
                  var rid = ids[java.util.concurrent.ThreadLocalRandom.current().nextInt(ids.length)];
                  catalogService.getByIdFromDb(rid);
                };
                valkeyTask = () -> catalogService.searchPrefix("S", 10);
              }
            }

            result =
                BenchmarkService.concurrentComparison(
                    dbTask,
                    valkeyTask,
                    threads,
                    opsPerThread,
                    completed ->
                        javafx.application.Platform.runLater(
                            () -> progressBar.setProgress((double) completed / grandTotal)));
          }

          @Override
          protected void onSuccess() {
            dbOpsLabel.setText(String.format("%.0f ops/sec", result.dbOpsPerSecond()));
            valkeyOpsLabel.setText(String.format("%.0f ops/sec", result.valkeyOpsPerSecond()));
            speedupLabel.setText(String.format("%.1fx", result.speedup()));
            configLabel.setText(
                threads
                    + " threads × "
                    + opsPerThread
                    + " ops = "
                    + totalOps
                    + " total operations per path");
            progressBar.setProgress(1.0);
            progressLabel.setText("Done");
            LOG.info(
                "[bench] "
                    + operation
                    + ": DB="
                    + String.format("%.0f", result.dbOpsPerSecond())
                    + " ops/s, Valkey="
                    + String.format("%.0f", result.valkeyOpsPerSecond())
                    + " ops/s, speedup="
                    + String.format("%.1fx", result.speedup()));
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
    dbOpsLabel.setText("—");
    valkeyOpsLabel.setText("—");
    speedupLabel.setText("—");
    configLabel.setText("");
  }

  private Label headerLabel(String text) {
    var label = new Label(text);
    label.setStyle("-fx-font-size: 13; -fx-font-weight: bold; -fx-text-fill: #ccc;");
    return label;
  }

  private Label rowLabel(String text) {
    var label = new Label(text);
    label.setStyle("-fx-font-size: 11; -fx-text-fill: #888;");
    return label;
  }

  private VBox metricCard(Label valueLabel) {
    valueLabel.setStyle("-fx-font-size: 22; -fx-font-weight: bold; -fx-text-fill: #e94560;");
    var card = new VBox(4, valueLabel);
    card.setAlignment(Pos.CENTER);
    card.setPadding(new Insets(16));
    card.setStyle(
        "-fx-background-color: #1a1a2e; -fx-border-color: #333; -fx-border-radius: 6;"
            + " -fx-background-radius: 6;");
    return card;
  }

  public void cancelBenchmark() {
    if (currentBenchmark != null) currentBenchmark.cancel();
  }

  public VBox getRoot() {
    return root;
  }
}
