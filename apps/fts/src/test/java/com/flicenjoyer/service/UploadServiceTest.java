package com.flicenjoyer.service;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

import glide.api.GlideClient;
import glide.api.models.GlideString;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Map;
import java.util.concurrent.CompletableFuture;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class UploadServiceTest {

  @Test
  void getExtensionExtractsMp4() {
    assertEquals(".mp4", UploadService.getExtension(Path.of("/videos/movie.mp4")));
  }

  @Test
  void getExtensionExtractsJpg() {
    assertEquals(".jpg", UploadService.getExtension(Path.of("thumb.jpg")));
  }

  @Test
  void getExtensionHandlesNoExtension() {
    assertEquals("", UploadService.getExtension(Path.of("noext")));
  }

  @Test
  void getExtensionHandlesMultipleDots() {
    assertEquals(".mkv", UploadService.getExtension(Path.of("my.movie.file.mkv")));
  }

  @Test
  void uploadVideoStoresHashInValkey(@TempDir Path tempDir) throws Exception {
    var client = mock(GlideClient.class);
    when(client.hset(any(GlideString.class), any(Map.class)))
        .thenReturn(CompletableFuture.completedFuture(10L));

    var videoFile = tempDir.resolve("test.mp4");
    Files.writeString(videoFile, "fake video");
    var thumbFile = tempDir.resolve("test.png");
    Files.writeString(thumbFile, "fake thumb");

    var service = new UploadService(client);
    var id =
        service.uploadVideo("Title", "Action", "Desc", "tag1", 2024, 1.5, videoFile, thumbFile);

    assertNotNull(id);
    assertFalse(id.isEmpty());
    verify(client).hset(any(GlideString.class), any(Map.class));
  }

  @Test
  void uploadVideoWithoutThumbnail(@TempDir Path tempDir) throws Exception {
    var client = mock(GlideClient.class);
    when(client.hset(any(GlideString.class), any(Map.class)))
        .thenReturn(CompletableFuture.completedFuture(10L));

    var videoFile = tempDir.resolve("test.mp4");
    Files.writeString(videoFile, "fake video");

    var service = new UploadService(client);
    var id = service.uploadVideo("Title", "Action", "Desc", "tag1", 2024, 1.5, videoFile, null);

    assertNotNull(id);
    verify(client).hset(any(GlideString.class), any(Map.class));
  }
}
