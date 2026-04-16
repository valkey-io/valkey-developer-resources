package com.flicenjoyer;

import static glide.api.models.GlideString.gs;

import com.flicenjoyer.valkey.AppConfig;
import com.flicenjoyer.valkey.AppPaths;
import com.flicenjoyer.valkey.ValkeyClientProvider;
import com.flicenjoyer.valkey.ValkeyKeys;

/** CLI utility to erase all catalog and watch history from Valkey and clean local media files. */
public class ResetData {

  public static void main(String[] args) throws Exception {
    var config = AppConfig.load();
    System.out.println(
        "Connecting to Valkey at " + config.valkeyHost() + ":" + config.valkeyPort());

    try (var provider = new ValkeyClientProvider(config.valkeyHost(), config.valkeyPort())) {
      var client = provider.getClient();

      var catalogKeys = client.keys(gs(ValkeyKeys.CATALOG_PREFIX + "*")).get();
      var watchKeys = client.keys(gs(ValkeyKeys.WATCH_PREFIX + "*")).get();

      int deleted = 0;
      if (catalogKeys.length > 0) {
        client.del(catalogKeys).get();
        deleted += catalogKeys.length;
      }
      if (watchKeys.length > 0) {
        client.del(watchKeys).get();
        deleted += watchKeys.length;
      }

      System.out.println(
          "Deleted "
              + deleted
              + " keys ("
              + catalogKeys.length
              + " catalog, "
              + watchKeys.length
              + " watch)");

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
  }
}
