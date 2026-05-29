package com.flicenjoyer.service;

import static glide.api.models.GlideString.gs;

import com.flicenjoyer.db.WatchHistoryRepository;
import com.flicenjoyer.model.WatchHistoryEntry;
import com.flicenjoyer.valkey.HashParser;
import com.flicenjoyer.valkey.UserProfileManager;
import com.flicenjoyer.valkey.ValkeyKeys;
import glide.api.GlideClient;
import glide.api.commands.servermodules.FT;
import glide.api.models.GlideString;
import glide.api.models.commands.FT.FTSearchOptions;
import java.sql.SQLException;
import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ExecutionException;

/** Per-user watch history: resume points, completion tracking, and session management. */
public class WatchHistoryService {

  private final GlideClient client;
  private final UserProfileManager profileManager;
  private final WatchHistoryRepository watchRepo;

  public WatchHistoryService(
      GlideClient client, UserProfileManager profileManager, WatchHistoryRepository watchRepo) {
    this.client = client;
    this.profileManager = profileManager;
    this.watchRepo = watchRepo;
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
    if (result.length >= 2) {
      var docs = (Map<GlideString, Map<GlideString, GlideString>>) result[1];
      if (!docs.isEmpty()) {
        return docs.values().stream().map(HashParser::toWatchEntry).toList();
      }
    }
    // Cache miss — fall back to DB, populate cache
    try {
      var entries = watchRepo.findByUserId(profileManager.getUserId());
      for (var entry : entries) {
        var key = ValkeyKeys.watchKey(entry.userId(), entry.catalogId());
        client.hset(gs(key), HashParser.watchEntryToHash(entry)).get();
      }
      return entries;
    } catch (SQLException e) {
      throw new RuntimeException("DB lookup failed for user history", e);
    }
  }

  /** Cache-aside: check Valkey first, fall back to DB. */
  public long getResumePoint(String catalogId) throws ExecutionException, InterruptedException {
    String key = ValkeyKeys.watchKey(profileManager.getUserId(), catalogId);
    GlideString val = client.hget(gs(key), gs("resumeTimestamp")).get();
    if (val != null) return HashParser.toLong(val);
    // Cache miss — query DB
    try {
      var entry = watchRepo.findByUserAndCatalog(profileManager.getUserId(), catalogId);
      if (entry.isPresent()) {
        // Populate cache
        client.hset(gs(key), HashParser.watchEntryToHash(entry.get())).get();
        return entry.get().resumeTimestamp();
      }
      return 0;
    } catch (SQLException e) {
      throw new RuntimeException("DB lookup failed for watch history", e);
    }
  }

  /** Direct DB lookup — bypasses cache. Used for benchmark comparison. */
  public long getResumePointFromDb(String catalogId) {
    try {
      return watchRepo
          .findByUserAndCatalog(profileManager.getUserId(), catalogId)
          .map(WatchHistoryEntry::resumeTimestamp)
          .orElse(0L);
    } catch (SQLException e) {
      throw new RuntimeException("DB lookup failed", e);
    }
  }

  /** Direct DB write — matches DB work of updateResumePoint (read + upsert). */
  public void updateResumePointInDbOnly(String catalogId, long seconds) {
    try {
      long now = Instant.now().getEpochSecond();
      // Same DB work as the Valkey path: read existing, then upsert
      var existing = watchRepo.findByUserAndCatalog(profileManager.getUserId(), catalogId);
      var entry =
          new WatchHistoryEntry(
              profileManager.getUserId(),
              catalogId,
              existing.map(WatchHistoryEntry::title).orElse(""),
              seconds,
              existing.map(WatchHistoryEntry::completed).orElse(false),
              now);
      watchRepo.upsert(entry);
    } catch (SQLException e) {
      throw new RuntimeException("DB write failed", e);
    }
  }

  public void updateResumePoint(String catalogId, long seconds)
      throws ExecutionException, InterruptedException {
    long now = Instant.now().getEpochSecond();
    String userId = profileManager.getUserId();
    // Write to DB first
    try {
      var existing = watchRepo.findByUserAndCatalog(userId, catalogId);
      var entry =
          new WatchHistoryEntry(
              userId,
              catalogId,
              existing.map(WatchHistoryEntry::title).orElse(""),
              seconds,
              existing.map(WatchHistoryEntry::completed).orElse(false),
              now);
      watchRepo.upsert(entry);
    } catch (SQLException e) {
      throw new RuntimeException("DB write failed", e);
    }
    // Update cache
    String key = ValkeyKeys.watchKey(userId, catalogId);
    client
        .hset(
            gs(key),
            Map.of(
                gs("resumeTimestamp"), gs(String.valueOf(seconds)),
                gs("lastWatched"), gs(String.valueOf(now))))
        .get();
  }

  public void markCompleted(String catalogId) throws ExecutionException, InterruptedException {
    String userId = profileManager.getUserId();
    long now = Instant.now().getEpochSecond();
    // Write to DB
    try {
      var existing = watchRepo.findByUserAndCatalog(userId, catalogId);
      var entry =
          new WatchHistoryEntry(
              userId,
              catalogId,
              existing.map(WatchHistoryEntry::title).orElse(""),
              existing.map(WatchHistoryEntry::resumeTimestamp).orElse(0L),
              true,
              now);
      watchRepo.upsert(entry);
    } catch (SQLException e) {
      throw new RuntimeException("DB write failed", e);
    }
    // Update cache
    String key = ValkeyKeys.watchKey(userId, catalogId);
    client
        .hset(
            gs(key),
            Map.of(gs("completed"), gs("true"), gs("lastWatched"), gs(String.valueOf(now))))
        .get();
  }

  public void startWatching(String catalogId, String title)
      throws ExecutionException, InterruptedException {
    String userId = profileManager.getUserId();
    long now = Instant.now().getEpochSecond();
    var entry = new WatchHistoryEntry(userId, catalogId, title, 0, false, now);
    // Write to DB
    try {
      watchRepo.upsert(entry);
    } catch (SQLException e) {
      throw new RuntimeException("DB write failed", e);
    }
    // Populate cache
    String key = ValkeyKeys.watchKey(userId, catalogId);
    client.hset(gs(key), HashParser.watchEntryToHash(entry)).get();
  }

  /** Deletes watch history for a video across ALL users. */
  @SuppressWarnings("unchecked")
  public void deleteWatchHistoryForVideo(String catalogId)
      throws ExecutionException, InterruptedException {
    // Delete from DB first
    try {
      watchRepo.deleteByCatalogId(catalogId);
    } catch (SQLException e) {
      throw new RuntimeException("DB delete failed", e);
    }
    // Delete from cache
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
