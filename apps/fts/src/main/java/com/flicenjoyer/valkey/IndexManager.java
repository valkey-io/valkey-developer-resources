package com.flicenjoyer.valkey;

import glide.api.GlideClient;
import glide.api.commands.servermodules.FT;
import glide.api.models.GlideString;
import glide.api.models.commands.FT.FTCreateOptions;
import glide.api.models.commands.FT.FTCreateOptions.DataType;
import glide.api.models.commands.FT.FTCreateOptions.FieldInfo;
import glide.api.models.commands.FT.FTCreateOptions.NumericField;
import glide.api.models.commands.FT.FTCreateOptions.TagField;
import glide.api.models.commands.FT.FTCreateOptions.TextField;
import glide.api.models.exceptions.RequestException;
import java.util.Arrays;
import java.util.Set;
import java.util.concurrent.ExecutionException;
import java.util.stream.Collectors;

/** Creates ValkeySearch FTS indexes for catalog and watch history on startup. */
public class IndexManager {

  private static final java.util.logging.Logger LOG =
      java.util.logging.Logger.getLogger(IndexManager.class.getName());

  private final GlideClient client;

  public IndexManager(GlideClient client) {
    this.client = client;
  }

  public void ensureIndexes() throws ExecutionException, InterruptedException {
    Set<String> existing;
    try {
      existing =
          Arrays.stream(FT.list(client).get())
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
        throw e; // Connection/timeout error — propagate
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

  private void createCatalogIndex() throws ExecutionException, InterruptedException {
    FT.create(
            client,
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
    FT.create(
            client,
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
