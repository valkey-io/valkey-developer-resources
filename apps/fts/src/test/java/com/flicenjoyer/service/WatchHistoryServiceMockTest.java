package com.flicenjoyer.service;

import static glide.api.models.GlideString.gs;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

import com.flicenjoyer.db.WatchHistoryRepository;
import com.flicenjoyer.valkey.UserProfileManager;
import glide.api.BaseClient;
import glide.api.GlideClient;
import glide.api.commands.servermodules.FT;
import glide.api.models.GlideString;
import glide.api.models.commands.FT.FTSearchOptions;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.concurrent.CompletableFuture;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.MockedStatic;
import org.mockito.junit.jupiter.MockitoExtension;

@ExtendWith(MockitoExtension.class)
class WatchHistoryServiceMockTest {

  @Mock GlideClient client;
  @Mock UserProfileManager profileManager;
  @Mock WatchHistoryRepository watchRepo;
  WatchHistoryService service;

  @BeforeEach
  void setUp() {
    service = new WatchHistoryService(client, profileManager, watchRepo);
    lenient().when(profileManager.getUserId()).thenReturn("user1");
  }

  @Test
  void getResumePointReturnsValue() throws Exception {
    when(client.hget(any(GlideString.class), any(GlideString.class)))
        .thenReturn(CompletableFuture.completedFuture(gs("1234")));

    var result = service.getResumePoint("vid1");
    assertEquals(1234L, result);
  }

  @Test
  void getResumePointReturnsZeroWhenNull() throws Exception {
    when(client.hget(any(GlideString.class), any(GlideString.class)))
        .thenReturn(CompletableFuture.completedFuture(null));
    when(watchRepo.findByUserAndCatalog("user1", "vid1"))
        .thenReturn(java.util.Optional.empty());

    assertEquals(0L, service.getResumePoint("vid1"));
  }

  @Test
  void updateResumePointCallsHset() throws Exception {
    when(watchRepo.findByUserAndCatalog("user1", "vid1"))
        .thenReturn(java.util.Optional.empty());
    when(client.hset(any(GlideString.class), any()))
        .thenReturn(CompletableFuture.completedFuture(2L));

    service.updateResumePoint("vid1", 500);
    verify(watchRepo).upsert(any());
    verify(client).hset(eq(gs("watch:user1:vid1")), any());
  }

  @Test
  void markCompletedCallsHset() throws Exception {
    when(watchRepo.findByUserAndCatalog("user1", "vid1"))
        .thenReturn(java.util.Optional.empty());
    when(client.hset(any(GlideString.class), any()))
        .thenReturn(CompletableFuture.completedFuture(1L));

    service.markCompleted("vid1");
    verify(watchRepo).upsert(any());
    verify(client).hset(eq(gs("watch:user1:vid1")), any());
  }

  @Test
  void startWatchingCallsHset() throws Exception {
    when(client.hset(any(GlideString.class), any()))
        .thenReturn(CompletableFuture.completedFuture(6L));

    service.startWatching("vid1", "Test Movie");
    verify(watchRepo).upsert(any());
    verify(client).hset(eq(gs("watch:user1:vid1")), any());
  }

  @Test
  void getUserHistoryReturnsEntries() throws Exception {
    Map<GlideString, GlideString> fields = new LinkedHashMap<>();
    fields.put(gs("userId"), gs("user1"));
    fields.put(gs("catalogId"), gs("vid1"));
    fields.put(gs("title"), gs("Test"));
    fields.put(gs("resumeTimestamp"), gs("100"));
    fields.put(gs("completed"), gs("false"));
    fields.put(gs("lastWatched"), gs("9999"));

    Map<GlideString, Map<GlideString, GlideString>> docs = new LinkedHashMap<>();
    docs.put(gs("watch:user1:vid1"), fields);
    Object[] searchResult = new Object[] {1L, docs};

    try (MockedStatic<FT> ft = mockStatic(FT.class)) {
      ft.when(
              () ->
                  FT.search(
                      any(BaseClient.class),
                      any(String.class),
                      any(String.class),
                      any(FTSearchOptions.class)))
          .thenReturn(CompletableFuture.completedFuture(searchResult));

      var entries = service.getUserHistory();
      assertEquals(1, entries.size());
      assertEquals("vid1", entries.getFirst().catalogId());
    }
  }

  @Test
  void deleteWatchHistoryForVideoDeletesKeys() throws Exception {
    Map<GlideString, Map<GlideString, GlideString>> docs = new LinkedHashMap<>();
    docs.put(gs("watch:u1:vid1"), new LinkedHashMap<>());
    docs.put(gs("watch:u2:vid1"), new LinkedHashMap<>());
    Object[] searchResult = new Object[] {2L, docs};

    when(client.del(any(GlideString[].class))).thenReturn(CompletableFuture.completedFuture(2L));

    try (MockedStatic<FT> ft = mockStatic(FT.class)) {
      ft.when(
              () ->
                  FT.search(
                      any(BaseClient.class),
                      any(String.class),
                      any(String.class),
                      any(FTSearchOptions.class)))
          .thenReturn(CompletableFuture.completedFuture(searchResult));

      service.deleteWatchHistoryForVideo("vid1");
      verify(client, times(1)).del(any(GlideString[].class)); // single batched call
    }
  }
}
