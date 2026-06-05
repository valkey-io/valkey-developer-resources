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
import com.flicenjoyer.valkey.ValkeyClientProvider;
import javafx.application.Application;
import javafx.scene.Scene;
import javafx.stage.Stage;

/** JavaFX application entry point. Initializes DB, Valkey, services, and the main UI. */
public class FlicEnjoyerApp extends Application {

  private static final java.util.logging.Logger LOG =
      java.util.logging.Logger.getLogger(FlicEnjoyerApp.class.getName());

  private ValkeyClientProvider valkeyProvider;
  private DatabaseProvider dbProvider;

  @Override
  public void start(Stage primaryStage) throws Exception {
    var config = AppConfig.load();

    // Initialize PostgreSQL
    LOG.info(
        "Connecting to PostgreSQL at " + config.dbHost() + ":" + config.dbPort() + "/"
            + config.dbName());
    dbProvider = new DatabaseProvider(config);
    var catalogRepo = new CatalogRepository(dbProvider.getDataSource());
    var watchRepo = new WatchHistoryRepository(dbProvider.getDataSource());

    // Initialize Valkey
    LOG.info("Connecting to Valkey at " + config.valkeyHost() + ":" + config.valkeyPort());
    valkeyProvider = new ValkeyClientProvider(config.valkeyHost(), config.valkeyPort());
    var valkeyClient = valkeyProvider.getValkeyClient();

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

    var indexManager = new IndexManager(valkeyClient, catalogRepo, watchRepo);
    indexManager.ensureIndexes();
    indexManager.syncFromDatabase();

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
    launch(args);
  }
}
