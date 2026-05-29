package com.flicenjoyer.valkey;

import static glide.api.models.GlideString.gs;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

import com.flicenjoyer.db.CatalogRepository;
import com.flicenjoyer.db.WatchHistoryRepository;
import glide.api.GlideClient;
import glide.api.commands.servermodules.FT;
import glide.api.models.GlideString;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ExecutionException;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.MockedStatic;
import org.mockito.junit.jupiter.MockitoExtension;

@ExtendWith(MockitoExtension.class)
class IndexManagerTest {

  @Mock GlideClient client;
  @Mock CatalogRepository catalogRepo;
  @Mock WatchHistoryRepository watchRepo;

  @Test
  void ensureIndexesCreatesWhenMissing() throws Exception {
    try (MockedStatic<FT> ft = mockStatic(FT.class)) {
      ft.when(() -> FT.list(client))
          .thenReturn(CompletableFuture.completedFuture(new GlideString[] {}));
      ft.when(() -> FT.create(eq(client), any(String.class), any(), any()))
          .thenReturn(CompletableFuture.completedFuture("OK"));

      new IndexManager(client, catalogRepo, watchRepo).ensureIndexes();

      ft.verify(() -> FT.create(eq(client), eq(ValkeyKeys.CATALOG_INDEX), any(), any()));
      ft.verify(() -> FT.create(eq(client), eq(ValkeyKeys.WATCH_INDEX), any(), any()));
    }
  }

  @Test
  void ensureIndexesSkipsWhenExist() throws Exception {
    try (MockedStatic<FT> ft = mockStatic(FT.class)) {
      ft.when(() -> FT.list(client))
          .thenReturn(
              CompletableFuture.completedFuture(
                  new GlideString[] {gs(ValkeyKeys.CATALOG_INDEX), gs(ValkeyKeys.WATCH_INDEX)}));

      new IndexManager(client, catalogRepo, watchRepo).ensureIndexes();

      ft.verify(() -> FT.create(any(), any(String.class), any(), any()), never());
    }
  }

  @Test
  void ensureIndexesHandlesValkeySearchUnavailable() throws Exception {
    try (MockedStatic<FT> ft = mockStatic(FT.class)) {
      ft.when(() -> FT.list(client))
          .thenReturn(
              CompletableFuture.failedFuture(
                  new glide.api.models.exceptions.RequestException("unknown command")));

      new IndexManager(client, catalogRepo, watchRepo).ensureIndexes();
    }
  }

  @Test
  void ensureIndexesPropagatesConnectionErrors() {
    try (MockedStatic<FT> ft = mockStatic(FT.class)) {
      ft.when(() -> FT.list(client))
          .thenReturn(CompletableFuture.failedFuture(new RuntimeException("Connection refused")));

      assertThrows(
          ExecutionException.class,
          () -> new IndexManager(client, catalogRepo, watchRepo).ensureIndexes());
    }
  }
}
