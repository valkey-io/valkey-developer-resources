package com.flicenjoyer.service;

import static glide.api.models.GlideString.gs;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

import com.flicenjoyer.valkey.UserProfileManager;
import glide.api.GlideClient;
import glide.api.models.GlideString;
import java.util.Map;
import java.util.concurrent.CompletableFuture;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

@ExtendWith(MockitoExtension.class)
class WatchHistoryServiceMockTest {

  @Mock GlideClient client;
  @Mock UserProfileManager profileManager;
  WatchHistoryService service;

  @BeforeEach
  void setUp() {
    service = new WatchHistoryService(client, profileManager);
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

    assertEquals(0L, service.getResumePoint("vid1"));
  }

  @Test
  void updateResumePointCallsHset() throws Exception {
    when(client.hset(any(GlideString.class), any()))
        .thenReturn(CompletableFuture.completedFuture(2L));

    service.updateResumePoint("vid1", 500);
    verify(client).hset(eq(gs("watch:user1:vid1")), any());
  }

  @Test
  void markCompletedCallsHset() throws Exception {
    when(client.hset(any(GlideString.class), any()))
        .thenReturn(CompletableFuture.completedFuture(1L));

    service.markCompleted("vid1");
    verify(client).hset(eq(gs("watch:user1:vid1")), any());
  }

  @Test
  void startWatchingCallsHset() throws Exception {
    when(client.hset(any(GlideString.class), any()))
        .thenReturn(CompletableFuture.completedFuture(6L));

    service.startWatching("vid1", "Test Movie");
    verify(client).hset(eq(gs("watch:user1:vid1")), any());
  }

  @Test
  void getUserHistoryReturnsEntries() throws Exception {
    when(client.keys(any(GlideString.class)))
        .thenReturn(CompletableFuture.completedFuture(new GlideString[] {gs("watch:user1:vid1")}));

    Map<GlideString, GlideString> fields =
        Map.of(
            gs("userId"), gs("user1"),
            gs("catalogId"), gs("vid1"),
            gs("title"), gs("Test"),
            gs("resumeTimestamp"), gs("100"),
            gs("completed"), gs("false"),
            gs("lastWatched"), gs("9999"));
    when(client.hgetall(any(GlideString.class)))
        .thenReturn(CompletableFuture.completedFuture(fields));

    var entries = service.getUserHistory();
    assertEquals(1, entries.size());
    assertEquals("vid1", entries.getFirst().catalogId());
  }

  @Test
  void deleteWatchHistoryForVideoDeletesKeys() throws Exception {
    when(client.keys(any(GlideString.class)))
        .thenReturn(
            CompletableFuture.completedFuture(
                new GlideString[] {gs("watch:u1:vid1"), gs("watch:u2:vid1")}));
    when(client.del(any(GlideString[].class))).thenReturn(CompletableFuture.completedFuture(1L));

    service.deleteWatchHistoryForVideo("vid1");
    verify(client, times(2)).del(any(GlideString[].class));
  }
}
