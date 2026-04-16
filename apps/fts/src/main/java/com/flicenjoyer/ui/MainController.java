package com.flicenjoyer.ui;

import com.flicenjoyer.service.CatalogService;
import com.flicenjoyer.service.UploadService;
import com.flicenjoyer.service.WatchHistoryService;
import java.util.LinkedHashMap;
import java.util.Map;
import javafx.geometry.Insets;
import javafx.geometry.Pos;
import javafx.scene.Node;
import javafx.scene.control.Button;
import javafx.scene.control.Label;
import javafx.scene.layout.*;
import javafx.stage.Stage;

/** Top-level UI controller: navigation menu, view registry, and view lifecycle management. */
public class MainController {

  private final BorderPane root = new BorderPane();
  private final StackPane contentArea = new StackPane();
  private final Label viewLabel = new Label("Upload");
  private final VBox navMenu = new VBox();
  private final StackPane overlay = new StackPane();
  private final Map<ViewId, Node> views = new LinkedHashMap<>();
  private final Map<ViewId, Button> navButtons = new LinkedHashMap<>();
  private final Map<ViewId, Runnable> onShowCallbacks = new LinkedHashMap<>();
  private final Map<ViewId, Runnable> onLeaveCallbacks = new LinkedHashMap<>();
  private ViewId currentView;

  public MainController(
      Stage stage,
      UploadService uploadService,
      CatalogService catalogService,
      WatchHistoryService watchHistoryService,
      com.flicenjoyer.service.AggregationService aggregationService,
      boolean adminEnabled) {
    buildTitleBar();
    buildNavMenu();
    buildOverlay();

    var catalogView = new CatalogView(catalogService);
    var uploadForm = new VideoFormView(stage, VideoFormView.Mode.UPLOAD);
    uploadForm.setUploadService(uploadService);
    var playerView = new PlayerView(watchHistoryService, catalogService);
    var historyView = new WatchHistoryView(watchHistoryService, catalogService);
    var searchView = new SearchView(catalogService);

    catalogView.setWatchHistoryService(watchHistoryService);
    catalogView.setOnPlayMovie(
        movie -> {
          playerView.setBackNavigation(ViewId.BROWSE, () -> showView(ViewId.BROWSE));
          playerView.loadMovie(movie);
          showView(ViewId.PLAYER);
        });

    historyView.setOnResumeMovie(
        movie -> {
          playerView.setBackNavigation(ViewId.HISTORY, () -> showView(ViewId.HISTORY));
          playerView.loadMovie(movie);
          showView(ViewId.PLAYER);
        });

    searchView.setWatchHistoryService(watchHistoryService);
    searchView.setOnPlayMovie(
        movie -> {
          playerView.setBackNavigation(ViewId.SEARCH, () -> showView(ViewId.SEARCH));
          playerView.loadMovie(movie);
          showView(ViewId.PLAYER);
        });

    views.put(ViewId.SEARCH, searchView.getRoot());
    views.put(ViewId.UPLOAD, uploadForm.getRoot());
    views.put(ViewId.BROWSE, catalogView.getRoot());
    views.put(ViewId.HISTORY, historyView.getRoot());
    views.put(ViewId.PLAYER, playerView.getRoot());
    var benchmarkView = new BenchmarkView(catalogService, watchHistoryService, aggregationService);
    views.put(ViewId.BENCHMARKS, benchmarkView.getRoot());
    views.put(ViewId.REPORTS, new ReportsView(aggregationService).getRoot());

    onShowCallbacks.put(ViewId.BROWSE, catalogView::onShow);
    onShowCallbacks.put(ViewId.HISTORY, historyView::onShow);
    onLeaveCallbacks.put(ViewId.SEARCH, searchView::cancelSearch);
    onLeaveCallbacks.put(ViewId.BROWSE, catalogView::cancelLoad);
    onLeaveCallbacks.put(ViewId.HISTORY, historyView::cancelLoad);
    onLeaveCallbacks.put(ViewId.UPLOAD, uploadForm::cancelTask);
    onLeaveCallbacks.put(ViewId.PLAYER, playerView::onLeave);
    onLeaveCallbacks.put(ViewId.BENCHMARKS, benchmarkView::cancelBenchmark);

    // Admin section
    if (adminEnabled) {
      var adminView = new AdminView(catalogService, watchHistoryService);
      var editForm = new VideoFormView(stage, VideoFormView.Mode.EDIT);
      editForm.setCatalogService(catalogService);

      adminView.setOnEditMovie(
          movie -> {
            editForm.loadMovie(movie);
            editForm.setBackNavigation(
                ViewId.ADMINISTRATION, () -> showView(ViewId.ADMINISTRATION));
            editForm.setOnComplete(
                () -> {
                  showView(ViewId.ADMINISTRATION);
                  adminView.showBanner("Changes saved!");
                });
            showView(ViewId.EDIT_VIDEO);
          });

      views.put(ViewId.ADMINISTRATION, adminView.getRoot());
      views.put(ViewId.EDIT_VIDEO, editForm.getRoot());
      onShowCallbacks.put(ViewId.ADMINISTRATION, adminView::onShow);
      onLeaveCallbacks.put(ViewId.ADMINISTRATION, adminView::cancelLoad);
      onLeaveCallbacks.put(ViewId.EDIT_VIDEO, editForm::cancelTask);

      // Add separator and admin nav item
      var separator = new javafx.scene.control.Separator();
      separator.setStyle("-fx-background-color: #1a3a6e;");
      separator.setPadding(new Insets(8, 16, 8, 16));
      navMenu.getChildren().add(separator);
      addNavItem("nav-admin", ViewId.ADMINISTRATION);
    }

    root.setCenter(new StackPane(contentArea, overlay, navMenu));
    showView(ViewId.BROWSE);
  }

  private void buildTitleBar() {
    var hamburger = new Button("☰");
    hamburger.getStyleClass().add("hamburger");
    hamburger.setOnAction(e -> toggleMenu());

    var appName = new Label("🎬 FlicEnjoyer");
    appName.getStyleClass().add("app-name");

    var dash = new Label("—");
    dash.getStyleClass().add("title-dash");

    viewLabel.getStyleClass().add("view-label");

    var spacer = new Region();
    HBox.setHgrow(spacer, Priority.ALWAYS);

    var titleBar = new HBox(8, hamburger, appName, dash, viewLabel);
    titleBar.setAlignment(Pos.CENTER_LEFT);
    titleBar.getStyleClass().add("title-bar");
    titleBar.setPadding(new Insets(10, 16, 10, 16));

    root.setTop(titleBar);
  }

  private void buildNavMenu() {
    var header = new HBox();
    var headerLabel = new Label("🎬 FlicEnjoyer");
    headerLabel.getStyleClass().add("nav-header-label");
    var closeBtn = new Button("✕");
    closeBtn.getStyleClass().add("nav-close");
    closeBtn.setOnAction(e -> toggleMenu());
    var spacer = new Region();
    HBox.setHgrow(spacer, Priority.ALWAYS);
    header.getChildren().addAll(headerLabel, spacer, closeBtn);
    header.getStyleClass().add("nav-header");
    header.setPadding(new Insets(10, 16, 16, 16));

    navMenu.getChildren().add(header);

    addNavItem("nav-search", ViewId.SEARCH);
    addNavItem("nav-browse", ViewId.BROWSE);
    addNavItem("nav-upload", ViewId.UPLOAD);
    addNavItem("nav-history", ViewId.HISTORY);
    addNavItem("nav-reports", ViewId.REPORTS);
    addNavItem("nav-bench", ViewId.BENCHMARKS);

    navMenu.getStyleClass().add("nav-menu");
    navMenu.setPrefWidth(240);
    navMenu.setMaxWidth(240);
    navMenu.setVisible(false);
    navMenu.setManaged(false);
    StackPane.setAlignment(navMenu, Pos.TOP_LEFT);
  }

  private void addNavItem(String iconName, ViewId viewId) {
    var btn = new Button(viewId.label());
    btn.setGraphic(IconLoader.plainIcon(iconName, 18, javafx.scene.paint.Color.web("#aaa")));
    btn.getStyleClass().add("nav-item");
    btn.setMaxWidth(Double.MAX_VALUE);
    btn.setOnAction(e -> showView(viewId));
    navMenu.getChildren().add(btn);
    navButtons.put(viewId, btn);
  }

  private void buildOverlay() {
    overlay.getStyleClass().add("nav-overlay");
    overlay.setVisible(false);
    overlay.setOnMouseClicked(e -> toggleMenu());
  }

  private void toggleMenu() {
    var open = !navMenu.isVisible();
    navMenu.setVisible(open);
    navMenu.setManaged(open);
    overlay.setVisible(open);
  }

  public void showView(ViewId viewId) {
    if (currentView != null) {
      var leave = onLeaveCallbacks.get(currentView);
      if (leave != null) leave.run();
    }
    var view = views.get(viewId);
    if (view != null) {
      contentArea.getChildren().setAll(view);
    }
    viewLabel.setText(viewId.label());
    navButtons.values().forEach(b -> b.getStyleClass().remove("nav-item-active"));
    var active = navButtons.get(viewId);
    if (active != null) active.getStyleClass().add("nav-item-active");
    var callback = onShowCallbacks.get(viewId);
    if (callback != null) callback.run();
    currentView = viewId;
    if (navMenu.isVisible()) toggleMenu();
  }

  public BorderPane getRoot() {
    return root;
  }
}
