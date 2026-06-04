package com.flicenjoyer;

import com.flicenjoyer.db.CatalogRepository;
import com.flicenjoyer.db.DatabaseProvider;
import com.flicenjoyer.db.WatchHistoryRepository;
import com.flicenjoyer.service.CatalogService;
import com.flicenjoyer.service.UploadService;
import com.flicenjoyer.service.WatchHistoryService;
import com.flicenjoyer.ui.MainController;
import com.flicenjoyer.valkey.AppConfig;
import com.flicenjoyer.valkey.AppPaths;
import com.flicenjoyer.valkey.IndexManager;
import com.flicenjoyer.valkey.UserProfileManager;
import com.flicenjoyer.valkey.ValkeyClient;
import com.flicenjoyer.valkey.ValkeyClientProvider;
import javafx.application.Application;
import javafx.scene.Scene;
import javafx.stage.Stage;

/** JavaFX application entry point. Initializes DB, Valkey, services, and the main UI. */
public class FlicEnjoyerApp extends Application {

  private static final java.util.logging.Logger LOG =
      java.util.logging.Logger.getLogger(FlicEnjoyerApp.class.getName());

  // Initialized in main() before JavaFX launch to avoid GLIDE JNI/JavaFX callback deadlock
  private static ValkeyClientProvider valkeyProvider;
  private static DatabaseProvider dbProvider;
  private static CatalogRepository catalogRepo;
  private static WatchHistoryRepository watchRepo;
  private static ValkeyClient valkeyClient;

  @Override
  public void start(Stage primaryStage) throws Exception {
    var config = AppConfig.load();

    var profileManager = new UserProfileManager();
    if (!profileManager.profileExists()) {
      var dialog = new javafx.scene.control.TextInputDialog();
      dialog.setTitle("Welcome to FlicEnjoyer");
      dialog.setHeaderText("Enter your full name");
      dialog.setContentText("Name:");
      var name = dialog.showAndWait().orElse("").trim();
      profileManager.createProfile(name.isEmpty() ? "Anonymous" : name);
    } else {
      profileManager.load();
    }

    var uploadService = new UploadService(valkeyClient, catalogRepo);
    var catalogService = new CatalogService(valkeyClient, catalogRepo);
    var watchHistoryService = new WatchHistoryService(valkeyClient, profileManager, watchRepo);
    var aggregationService = new com.flicenjoyer.service.AggregationService(valkeyClient);
    var mainController =
        new MainController(
            primaryStage,
            uploadService,
            catalogService,
            watchHistoryService,
            aggregationService,
            config.adminEnabled());

    var scene = new Scene(mainController.getRoot(), 1014, 676);
    var css = getClass().getResource("/styles.css");
    if (css != null) scene.getStylesheets().add(css.toExternalForm());
    primaryStage.setTitle("FlicEnjoyer — " + profileManager.getDisplayName());
    primaryStage.setScene(scene);
    primaryStage.show();
    javafx.application.Platform.runLater(primaryStage::centerOnScreen);
  }

  @Override
  public void stop() throws Exception {
    if (valkeyProvider != null) valkeyProvider.close();
    if (dbProvider != null) dbProvider.close();
  }

  @SuppressWarnings("unused") // JVM entry point
  public static void main(String[] args) {
    try (var is = FlicEnjoyerApp.class.getResourceAsStream("/logging.properties")) {
      if (is != null) {
        java.nio.file.Files.createDirectories(AppPaths.HOME);
        java.util.logging.LogManager.getLogManager().readConfiguration(is);
      }
    } catch (Exception e) {
      LOG.warning("Failed to load logging config: " + e.getMessage());
    }

    // Initialize DB + Valkey BEFORE JavaFX launch to avoid GLIDE JNI callback deadlock
    try {
      var config = AppConfig.load();
      LOG.info("Connecting to PostgreSQL at " + config.dbHost() + ":" + config.dbPort());
      dbProvider = new DatabaseProvider(config);
      catalogRepo = new CatalogRepository(dbProvider.getDataSource());
      watchRepo = new WatchHistoryRepository(dbProvider.getDataSource());

      LOG.info("Connecting to Valkey at " + config.valkeyHost() + ":" + config.valkeyPort());
      valkeyProvider = new ValkeyClientProvider(config.valkeyHost(), config.valkeyPort());
      valkeyClient = valkeyProvider.getValkeyClient();

      var indexManager = new IndexManager(valkeyClient, catalogRepo);
      indexManager.ensureIndexes();
      indexManager.syncFromDatabase();
    } catch (Exception e) {
      LOG.severe("Failed to initialize: " + e.getMessage());
      System.exit(1);
    }

    launch(args);
  }
}
