package com.flicenjoyer.valkey;

import static glide.api.models.GlideString.gs;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

import com.flicenjoyer.db.CatalogRepository;
import glide.api.models.GlideString;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ExecutionException;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

@ExtendWith(MockitoExtension.class)
class IndexManagerTest {

  @Mock ValkeyClient client;
  @Mock CatalogRepository catalogRepo;

  @Test
  void ensureIndexesCreatesWhenMissing() throws Exception {
    when(client.ftList())
        .thenReturn(CompletableFuture.completedFuture(new GlideString[] {}));
    when(client.ftCreate(any(String.class), any(), any()))
        .thenReturn(CompletableFuture.completedFuture("OK"));

    new IndexManager(client, catalogRepo).ensureIndexes();

    verify(client).ftCreate(eq(ValkeyKeys.CATALOG_INDEX), any(), any());
    verify(client).ftCreate(eq(ValkeyKeys.WATCH_INDEX), any(), any());
  }

  @Test
  void ensureIndexesSkipsWhenExist() throws Exception {
    when(client.ftList())
        .thenReturn(
            CompletableFuture.completedFuture(
                new GlideString[] {gs(ValkeyKeys.CATALOG_INDEX), gs(ValkeyKeys.WATCH_INDEX)}));

    new IndexManager(client, catalogRepo).ensureIndexes();

    verify(client, never()).ftCreate(any(String.class), any(), any());
  }

  @Test
  void ensureIndexesHandlesValkeySearchUnavailable() throws Exception {
    when(client.ftList())
        .thenReturn(
            CompletableFuture.failedFuture(
                new glide.api.models.exceptions.RequestException("unknown command")));

    new IndexManager(client, catalogRepo).ensureIndexes();
  }

  @Test
  void ensureIndexesPropagatesConnectionErrors() {
    when(client.ftList())
        .thenReturn(CompletableFuture.failedFuture(new RuntimeException("Connection refused")));

    assertThrows(
        ExecutionException.class,
        () -> new IndexManager(client, catalogRepo).ensureIndexes());
  }
}
