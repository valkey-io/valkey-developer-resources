package com.flicenjoyer.service;

import static glide.api.models.GlideString.gs;

import com.flicenjoyer.model.WatchHistoryEntry;
import com.flicenjoyer.valkey.HashParser;
import com.flicenjoyer.valkey.UserProfileManager;
import com.flicenjoyer.valkey.ValkeyKeys;
import glide.api.GlideClient;
import glide.api.models.GlideString;
import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ExecutionException;

/** Per-user watch history: resume points, completion tracking, and session management. */
public class WatchHistoryService {

  private final GlideClient client;
  private final UserProfileManager profileManager;

  public WatchHistoryService(GlideClient client, UserProfileManager profileManager) {
    this.client = client;
    this.profileManager = profileManager;
  }

  public List<WatchHistoryEntry> getUserHistory() throws ExecutionException, InterruptedException {
    // Fallback: scan watch keys directly (works without ValkeySearch)
    var keys = client.keys(gs(ValkeyKeys.WATCH_PREFIX + profileManager.getUserId() + ":*")).get();
    var entries = new java.util.ArrayList<WatchHistoryEntry>();
    for (var key : keys) {
      var fields = client.hgetall(key).get();
      if (fields.isEmpty()) continue;
      entries.add(HashParser.toWatchEntry(fields));
    }
    entries.sort(java.util.Comparator.comparingLong(WatchHistoryEntry::lastWatched).reversed());
    return entries;
  }

  public long getResumePoint(String catalogId) throws ExecutionException, InterruptedException {
    String key = ValkeyKeys.watchKey(profileManager.getUserId(), catalogId);
    GlideString val = client.hget(gs(key), gs("resumeTimestamp")).get();
    if (val == null) return 0;
    return HashParser.toLong(val);
  }

  public void updateResumePoint(String catalogId, long seconds)
      throws ExecutionException, InterruptedException {
    String key = ValkeyKeys.watchKey(profileManager.getUserId(), catalogId);
    client
        .hset(
            gs(key),
            Map.of(
                gs("resumeTimestamp"), gs(String.valueOf(seconds)),
                gs("lastWatched"), gs(String.valueOf(Instant.now().getEpochSecond()))))
        .get();
  }

  public void markCompleted(String catalogId) throws ExecutionException, InterruptedException {
    String key = ValkeyKeys.watchKey(profileManager.getUserId(), catalogId);
    client.hset(gs(key), Map.of(gs("completed"), gs("true"))).get();
  }

  public void startWatching(String catalogId, String title)
      throws ExecutionException, InterruptedException {
    String key = ValkeyKeys.watchKey(profileManager.getUserId(), catalogId);
    long now = Instant.now().getEpochSecond();
    client
        .hset(
            gs(key),
            Map.of(
                gs("userId"), gs(profileManager.getUserId()),
                gs("catalogId"), gs(catalogId),
                gs("title"), gs(title),
                gs("resumeTimestamp"), gs("0"),
                gs("completed"), gs("false"),
                gs("lastWatched"), gs(String.valueOf(now))))
        .get();
  }

  /** Deletes watch history for a video across ALL users. */
  public void deleteWatchHistoryForVideo(String catalogId)
      throws ExecutionException, InterruptedException {
    var keys = client.keys(gs(ValkeyKeys.WATCH_PREFIX + "*:" + catalogId)).get();
    for (var key : keys) {
      client.del(new GlideString[] {key}).get();
    }
  }
}
