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

  /** Convert a Movie to a Valkey hash field map for HSET. */
  public static Map<GlideString, GlideString> movieToHash(Movie m) {
    return Map.of(
        gs("title"), gs(m.title()),
        gs("genre"), gs(m.genre()),
        gs("description"), gs(m.description() != null ? m.description() : ""),
        gs("tags"), gs(m.tags() != null ? m.tags() : ""),
        gs("releaseYear"), gs(String.valueOf(m.releaseYear())),
        gs("rating"), gs(String.valueOf(m.rating())),
        gs("durationMinutes"), gs(String.valueOf(m.durationMinutes())),
        gs("videoPath"), gs(m.videoPath() != null ? m.videoPath() : ""),
        gs("thumbnailPath"), gs(m.thumbnailPath() != null ? m.thumbnailPath() : ""));
  }

  /** Convert a WatchHistoryEntry to a Valkey hash field map for HSET. */
  public static Map<GlideString, GlideString> watchEntryToHash(WatchHistoryEntry e) {
    return Map.of(
        gs("userId"), gs(e.userId()),
        gs("catalogId"), gs(e.catalogId()),
        gs("title"), gs(e.title() != null ? e.title() : ""),
        gs("resumeTimestamp"), gs(String.valueOf(e.resumeTimestamp())),
        gs("completed"), gs(String.valueOf(e.completed())),
        gs("lastWatched"), gs(String.valueOf(e.lastWatched())));
  }
}
