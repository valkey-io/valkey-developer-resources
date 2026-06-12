package com.flicenjoyer;

import com.flicenjoyer.db.DatabaseProvider;
import com.flicenjoyer.valkey.AppConfig;
import com.flicenjoyer.valkey.ValkeyClientProvider;
import com.flicenjoyer.valkey.ValkeyKeys;
import glide.api.models.commands.scan.ScanOptions;

/**
 * Removes all seeded demo data: catalog entries with "bench-" prefix and watch history entries
 * with "s" user prefix. Restores the database to only real user data.
 *
 * <p>Usage: ./gradlew unseedData
 */
public class UnseedData {

  public static void main(String[] args) throws Exception {
    var config = AppConfig.load();
    var dbProvider = new DatabaseProvider(config);

    try (var conn = dbProvider.getDataSource().getConnection()) {
      // Remove seeded watch history (fake user IDs start with "s")
      try (var ps = conn.prepareStatement("DELETE FROM watch_history WHERE user_id LIKE 's%'")) {
        int deleted = ps.executeUpdate();
        System.out.println("Deleted " + deleted + " seeded watch history entries from PostgreSQL");
      }
      // Remove seeded catalog
      try (var ps = conn.prepareStatement("DELETE FROM catalog WHERE id LIKE ?")) {
        ps.setString(1, SeedData.CATALOG_PREFIX + "%");
        int deleted = ps.executeUpdate();
        System.out.println("Deleted " + deleted + " seeded catalog entries from PostgreSQL");
      }
    }
    dbProvider.close();

    // Clean Valkey keys
    try (var provider = new ValkeyClientProvider(config.valkeyHost(), config.valkeyPort())) {
      var client = provider.getClient();
      int deleted = 0;
      // Catalog keys
      deleted += scanAndDelete(client, ValkeyKeys.CATALOG_PREFIX + SeedData.CATALOG_PREFIX + "*");
      // Watch history keys for seeded users
      deleted += scanAndDelete(client, ValkeyKeys.WATCH_PREFIX + "s*");
      System.out.println("Deleted " + deleted + " seeded keys from Valkey");
    }
  }

  private static int scanAndDelete(glide.api.GlideClient client, String pattern) throws Exception {
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
