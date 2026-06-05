package com.flicenjoyer;

import com.flicenjoyer.db.CatalogRepository;
import com.flicenjoyer.db.DatabaseProvider;
import com.flicenjoyer.db.WatchHistoryRepository;
import com.flicenjoyer.service.BenchmarkService;
import com.flicenjoyer.service.CatalogService;
import com.flicenjoyer.service.WatchHistoryService;
import com.flicenjoyer.valkey.AppConfig;
import com.flicenjoyer.valkey.IndexManager;
import com.flicenjoyer.valkey.UserProfileManager;
import com.flicenjoyer.valkey.ValkeyClientProvider;
import java.util.concurrent.ThreadLocalRandom;

/**
 * CLI benchmark tool. Outputs machine-parseable results to stdout.
 *
 * <p>Usage: ./gradlew benchmark [--args="--threads=32 --ops=500 --operation=catalog"]
 *
 * <p>Operations: catalog, resume, search
 */
public class BenchmarkCli {

  public static void main(String[] args) throws Exception {
    int threads = intArg(args, "threads", 32);
    int opsPerThread = intArg(args, "ops", 500);
    String operation = strArg(args, "operation", "catalog");

    var config = AppConfig.load();
    var dbProvider = new DatabaseProvider(config);
    try (var valkeyProvider = new ValkeyClientProvider(config.valkeyHost(), config.valkeyPort())) {
    var catalogRepo = new CatalogRepository(dbProvider.getDataSource());
    var watchRepo = new WatchHistoryRepository(dbProvider.getDataSource());

    var client = valkeyProvider.getValkeyClient();

    var profileManager = new UserProfileManager();
    if (!profileManager.profileExists()) {
      profileManager.createProfile("BenchmarkUser");
    } else {
      profileManager.load();
    }

    var indexManager = new IndexManager(client, catalogRepo, watchRepo);
    indexManager.ensureIndexes();
    indexManager.syncFromDatabase();

    var catalogService = new CatalogService(client, catalogRepo);
    var watchHistoryService = new WatchHistoryService(client, profileManager, watchRepo);

    var movies = catalogService.browseAll(null, "title", false);
    if (movies.isEmpty()) {
      System.err.println("ERROR: No catalog entries. Upload some videos first.");
      System.exit(1);
    }
    var ids = movies.stream().map(m -> m.id()).toArray(String[]::new);

    var dbCounter = new java.util.concurrent.atomic.AtomicInteger(0);
    var valkeyCounter = new java.util.concurrent.atomic.AtomicInteger(0);

    BenchmarkService.BenchmarkTask dbTask;
    BenchmarkService.BenchmarkTask valkeyTask;

    switch (operation) {
      case "resume" -> {
        dbTask =
            () -> {
              var rid = ids[ThreadLocalRandom.current().nextInt(ids.length)];
              if (dbCounter.incrementAndGet() % 8 == 0) {
                watchHistoryService.updateResumePointInDbOnly(rid, 100);
              } else {
                watchHistoryService.getResumePointFromDb(rid);
              }
            };
        valkeyTask =
            () -> {
              var rid = ids[ThreadLocalRandom.current().nextInt(ids.length)];
              if (valkeyCounter.incrementAndGet() % 8 == 0) {
                watchHistoryService.updateResumePoint(rid, 100);
              } else {
                watchHistoryService.getResumePoint(rid);
              }
            };
      }
      case "search" -> {
        dbTask =
            () -> catalogService.getByIdFromDb(ids[ThreadLocalRandom.current().nextInt(ids.length)]);
        valkeyTask = () -> catalogService.searchPrefix("S", 10);
      }
      default -> {
        dbTask =
            () -> {
              var rid = ids[ThreadLocalRandom.current().nextInt(ids.length)];
              if (dbCounter.incrementAndGet() % 8 == 0) {
                catalogService.updateRatingInDbOnly(rid, 7.5);
              } else {
                catalogService.getByIdFromDb(rid);
              }
            };
        valkeyTask =
            () -> {
              var rid = ids[ThreadLocalRandom.current().nextInt(ids.length)];
              if (valkeyCounter.incrementAndGet() % 8 == 0) {
                catalogService.updateRating(rid, 7.5);
              } else {
                catalogService.getById(rid);
              }
            };
      }
    }

    System.err.println(
        "Running: operation=" + operation + " threads=" + threads + " ops/thread=" + opsPerThread);

    var result =
        BenchmarkService.concurrentComparison(dbTask, valkeyTask, threads, opsPerThread, null);

    // Machine-parseable output
    System.out.println("operation=" + operation);
    System.out.println("threads=" + threads);
    System.out.println("ops_per_thread=" + opsPerThread);
    System.out.println("db_ops_per_sec=" + String.format("%.1f", result.dbOpsPerSecond()));
    System.out.println("valkey_ops_per_sec=" + String.format("%.1f", result.valkeyOpsPerSecond()));
    System.out.println("speedup=" + String.format("%.2f", result.speedup()));
    System.out.println("catalog_size=" + ids.length);
    } finally { // try-with-resources for valkeyProvider
      dbProvider.close();
    }
  }

  private static int intArg(String[] args, String name, int defaultVal) {
    for (var arg : args) {
      if (arg.startsWith("--" + name + "=")) {
        return Integer.parseInt(arg.substring(name.length() + 3));
      }
    }
    return defaultVal;
  }

  private static String strArg(String[] args, String name, String defaultVal) {
    for (var arg : args) {
      if (arg.startsWith("--" + name + "=")) {
        return arg.substring(name.length() + 3);
      }
    }
    return defaultVal;
  }
}
