package com.flicenjoyer.valkey;

import static com.flicenjoyer.valkey.ValkeyKeys.*;
import static glide.api.models.GlideString.gs;

import com.flicenjoyer.model.Movie;
import com.flicenjoyer.model.WatchHistoryEntry;
import glide.api.models.GlideString;
import java.util.Map;

/** Shared utilities for parsing Valkey hash fields into model objects. */
public final class HashParser {

  private HashParser() {}

  public static String str(Map<GlideString, GlideString> f, String name) {
    return f.getOrDefault(gs(name), gs("")).toString();
  }

  public static int toInt(Map<GlideString, GlideString> f, String name) {
    var val = str(f, name);
    return val.isEmpty() ? 0 : (int) Double.parseDouble(val);
  }

  public static double toDouble(Map<GlideString, GlideString> f, String name) {
    var val = str(f, name);
    return val.isEmpty() ? 0.0 : Double.parseDouble(val);
  }

  public static long toLong(Map<GlideString, GlideString> f, String name) {
    var val = str(f, name);
    return val.isEmpty() ? 0L : (long) Double.parseDouble(val);
  }

  public static long toLong(GlideString val) {
    return val == null ? 0L : (long) Double.parseDouble(val.toString());
  }

  public static Movie toMovie(String key, Map<GlideString, GlideString> f) {
    var id =
        key.startsWith(ValkeyKeys.CATALOG_PREFIX)
            ? key.substring(ValkeyKeys.CATALOG_PREFIX.length())
            : key;
    return new Movie(
        id,
        str(f, "title"),
        str(f, "genre"),
        str(f, "description"),
        str(f, "tags"),
        toInt(f, "releaseYear"),
        toDouble(f, "rating"),
        toDouble(f, "durationMinutes"),
        str(f, "videoPath"),
        str(f, "thumbnailPath"));
  }

  public static WatchHistoryEntry toWatchEntry(Map<GlideString, GlideString> f) {
    return new WatchHistoryEntry(
        str(f, "userId"),
        str(f, "catalogId"),
        str(f, "title"),
        toLong(f, "resumeTimestamp"),
        "true".equals(str(f, "completed")),
        toLong(f, "lastWatched"));
  }
}
