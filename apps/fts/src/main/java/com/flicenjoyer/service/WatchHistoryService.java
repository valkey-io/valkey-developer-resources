package com.flicenjoyer.service;

import static glide.api.models.GlideString.gs;

import com.flicenjoyer.model.WatchHistoryEntry;
import com.flicenjoyer.valkey.HashParser;
import com.flicenjoyer.valkey.UserProfileManager;
import com.flicenjoyer.valkey.ValkeyKeys;
import glide.api.GlideClient;
import glide.api.commands.servermodules.FT;
import glide.api.models.GlideString;
import glide.api.models.commands.FT.FTSearchOptions;
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

  @SuppressWarnings("unchecked")
  public List<WatchHistoryEntry> getUserHistory() throws ExecutionException, InterruptedException {
    var query = "@userId:{" + CatalogService.escapeTag(profileManager.getUserId()) + "}";
    var opts =
        FTSearchOptions.builder()
            .limit(0, 1000)
            .sortBy("lastWatched", FTSearchOptions.SortOrder.DESC)
            .build();
    var result = FT.search(client, ValkeyKeys.WATCH_INDEX, query, opts).get();
    if (result.length < 2) return List.of();
    var docs = (Map<GlideString, Map<GlideString, GlideString>>) result[1];
    return docs.values().stream().map(HashParser::toWatchEntry).toList();
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
  @SuppressWarnings("unchecked")
  public void deleteWatchHistoryForVideo(String catalogId)
      throws ExecutionException, InterruptedException {
    var query = "@catalogId:{" + CatalogService.escapeTag(catalogId) + "}";
    var opts = FTSearchOptions.builder().limit(0, 1000).build();
    var result = FT.search(client, ValkeyKeys.WATCH_INDEX, query, opts).get();
    if (result.length < 2) return;
    var docs = (Map<GlideString, Map<GlideString, GlideString>>) result[1];
    if (docs.isEmpty()) return;
    var keys = docs.keySet().toArray(new GlideString[0]);
    client.del(keys).get();
  }
}
