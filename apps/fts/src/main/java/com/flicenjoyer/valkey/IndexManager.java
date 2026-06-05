package com.flicenjoyer.valkey;

import static glide.api.models.GlideString.gs;

import com.flicenjoyer.db.CatalogRepository;
import com.flicenjoyer.db.WatchHistoryRepository;
import glide.api.models.Batch;
import glide.api.models.GlideString;
import glide.api.models.commands.FT.FTCreateOptions;
import glide.api.models.commands.FT.FTCreateOptions.DataType;
import glide.api.models.commands.FT.FTCreateOptions.FieldInfo;
import glide.api.models.commands.FT.FTCreateOptions.NumericField;
import glide.api.models.commands.FT.FTCreateOptions.TagField;
import glide.api.models.commands.FT.FTCreateOptions.TextField;
import glide.api.models.exceptions.RequestException;
import java.sql.SQLException;
import java.util.Arrays;
import java.util.Set;
import java.util.concurrent.ExecutionException;
import java.util.stream.Collectors;

/** Creates ValkeySearch FTS indexes and syncs DB data into Valkey hashes on startup. */
public class IndexManager {

  private static final java.util.logging.Logger LOG =
      java.util.logging.Logger.getLogger(IndexManager.class.getName());

  private final ValkeyClient client;
  private final CatalogRepository catalogRepo;
  private final WatchHistoryRepository watchRepo;

  public IndexManager(
      ValkeyClient client, CatalogRepository catalogRepo, WatchHistoryRepository watchRepo) {
    this.client = client;
    this.catalogRepo = catalogRepo;
    this.watchRepo = watchRepo;
  }

  public void ensureIndexes() throws ExecutionException, InterruptedException {
    Set<String> existing;
    try {
      existing =
          Arrays.stream(client.ftList().get())
              .map(GlideString::toString)
              .collect(Collectors.toSet());
    } catch (ExecutionException e) {
      var cause = e.getCause();
      if (cause instanceof RequestException
          && cause.getMessage() != null
          && cause.getMessage().contains("unknown command")) {
        LOG.warning(
            "WARNING: ValkeySearch module not available — FTS indexes not created. "
                + "Search, browse, and reports will not work until ValkeySearch is loaded.");
      } else {
        throw e;
      }
      return;
    }

    if (!existing.contains(ValkeyKeys.CATALOG_INDEX)) {
      createCatalogIndex();
    }
    if (!existing.contains(ValkeyKeys.WATCH_INDEX)) {
      createWatchIndex();
    }
  }

  /** Loads all catalog and watch_history rows from DB into Valkey hashes (warms cache + FTS). */
  public void syncFromDatabase() throws ExecutionException, InterruptedException {
    try {
      var movies = catalogRepo.findAll();
      if (!movies.isEmpty()) {
        Batch batch = new Batch(false);
        for (var movie : movies) {
          batch.hset(gs(ValkeyKeys.catalogKey(movie.id())), HashParser.movieToHash(movie));
        }
        client.exec(batch, true).get();
      }
      LOG.info("Synced " + movies.size() + " catalog entries from DB to Valkey");

      var entries = watchRepo.findAll();
      if (!entries.isEmpty()) {
        Batch batch = new Batch(false);
        for (var entry : entries) {
          var key = ValkeyKeys.watchKey(entry.userId(), entry.catalogId());
          batch.hset(gs(key), HashParser.watchEntryToHash(entry));
        }
        client.exec(batch, true).get();
      }
      LOG.info("Synced " + entries.size() + " watch history entries from DB to Valkey");
    } catch (SQLException e) {
      throw new RuntimeException("Failed to sync DB data to Valkey", e);
    }
  }

  private void createCatalogIndex() throws ExecutionException, InterruptedException {
    client.ftCreate(
            ValkeyKeys.CATALOG_INDEX,
            new FieldInfo[] {
              new FieldInfo("title", new TextField(false, 1.0, true, false, true)),
              new FieldInfo("genre", new TagField(',', false, true)),
              new FieldInfo("description", new TextField()),
              new FieldInfo("tags", new TagField(',', false, false)),
              new FieldInfo("releaseYear", new NumericField(true)),
              new FieldInfo("rating", new NumericField(true)),
              new FieldInfo("durationMinutes", new NumericField(false)),
              new FieldInfo("videoPath", new TagField()),
              new FieldInfo("thumbnailPath", new TagField()),
            },
            FTCreateOptions.builder()
                .dataType(DataType.HASH)
                .prefixes(new String[] {ValkeyKeys.CATALOG_PREFIX})
                .language("english")
                .build())
        .get();
  }

  private void createWatchIndex() throws ExecutionException, InterruptedException {
    client.ftCreate(
            ValkeyKeys.WATCH_INDEX,
            new FieldInfo[] {
              new FieldInfo("userId", new TagField()),
              new FieldInfo("catalogId", new TagField()),
              new FieldInfo("title", new TextField()),
              new FieldInfo("resumeTimestamp", new NumericField()),
              new FieldInfo("completed", new TagField()),
              new FieldInfo("lastWatched", new NumericField(true)),
            },
            FTCreateOptions.builder()
                .dataType(DataType.HASH)
                .prefixes(new String[] {ValkeyKeys.WATCH_PREFIX})
                .build())
        .get();
  }
}
