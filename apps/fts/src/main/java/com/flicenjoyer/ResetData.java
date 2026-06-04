package com.flicenjoyer;

import com.flicenjoyer.db.DatabaseProvider;
import com.flicenjoyer.valkey.AppConfig;
import com.flicenjoyer.valkey.AppPaths;
import com.flicenjoyer.valkey.ValkeyClientProvider;
import com.flicenjoyer.valkey.ValkeyKeys;
import glide.api.GlideClient;
import glide.api.models.commands.scan.ScanOptions;

/** CLI utility to erase all data from PostgreSQL, Valkey, and local media files. */
public class ResetData {

  public static void main(String[] args) throws Exception {
    var config = AppConfig.load();

    // Clear PostgreSQL
    System.out.println(
        "Connecting to PostgreSQL at " + config.dbHost() + ":" + config.dbPort());
    var dbProvider = new DatabaseProvider(config);
    try (var conn = dbProvider.getDataSource().getConnection();
        var stmt = conn.createStatement()) {
      stmt.execute("DELETE FROM watch_history");
      stmt.execute("DELETE FROM catalog");
      System.out.println("Cleared PostgreSQL tables");
    }
    dbProvider.close();

    // Clear Valkey
    System.out.println(
        "Connecting to Valkey at " + config.valkeyHost() + ":" + config.valkeyPort());
    try (var provider = new ValkeyClientProvider(config.valkeyHost(), config.valkeyPort())) {
      var client = provider.getClient();

      int deleted = 0;
      deleted += scanAndDelete(client, ValkeyKeys.CATALOG_PREFIX + "*");
      int catalogCount = deleted;
      deleted += scanAndDelete(client, ValkeyKeys.WATCH_PREFIX + "*");
      int watchCount = deleted - catalogCount;

      System.out.println(
          "Deleted "
              + deleted
              + " Valkey keys ("
              + catalogCount
              + " catalog, "
              + watchCount
              + " watch)");
    }

    // Clean local media files
    var mediaDir = AppPaths.MEDIA;
    if (java.nio.file.Files.exists(mediaDir)) {
      try (var walk = java.nio.file.Files.walk(mediaDir)) {
        var files = walk.sorted(java.util.Comparator.reverseOrder()).toList();
        for (var f : files) {
          java.nio.file.Files.deleteIfExists(f);
        }
      }
      System.out.println("Cleaned local media directory: " + mediaDir);
    }

    System.out.println("Reset complete.");
  }

  private static int scanAndDelete(GlideClient client, String pattern) throws Exception {
    var opts = ScanOptions.builder().matchPattern(pattern).count(100L).build();
    String cursor = "0";
    int deleted = 0;
    do {
      Object[] result = client.scan(cursor, opts).get();
      cursor = (String) result[0];
      Object[] keyObjs = (Object[]) result[1];
      if (keyObjs.length > 0) {
        var keys = new String[keyObjs.length];
        for (int i = 0; i < keyObjs.length; i++) keys[i] = (String) keyObjs[i];
        client.del(keys).get();
        deleted += keys.length;
      }
    } while (!cursor.equals("0"));
    return deleted;
  }
}
