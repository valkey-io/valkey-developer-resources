package com.flicenjoyer.service;

import static glide.api.models.GlideString.gs;
import static org.junit.jupiter.api.Assertions.*;

import com.flicenjoyer.valkey.ValkeyClientProvider;
import com.flicenjoyer.valkey.ValkeyClient;
import java.nio.file.Files;
import java.nio.file.Path;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.junit.jupiter.api.io.TempDir;
import org.testcontainers.containers.GenericContainer;
import org.testcontainers.containers.wait.strategy.Wait;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;

/** Integration tests for UploadService against a live Valkey instance. */
@Testcontainers
@EnabledIfEnvironmentVariable(named = "FLICENJOYER_INTEGRATION_TESTS", matches = "true")
class UploadServiceIntegrationTest {

  @Container
  static GenericContainer<?> valkey =
      new GenericContainer<>("valkey/valkey-bundle:unstable")
          .withExposedPorts(6379)
          .waitingFor(Wait.forLogMessage(".*Ready to accept connections.*", 1));

  @Container
  static org.testcontainers.containers.PostgreSQLContainer<?> postgres =
      new org.testcontainers.containers.PostgreSQLContainer<>("postgres:17")
          .withDatabaseName("flicenjoyer")
          .withUsername("flicenjoyer")
          .withPassword("flicenjoyer")
          .withInitScript("schema.sql");

  static ValkeyClientProvider provider;
  static ValkeyClient client;
  static com.flicenjoyer.db.CatalogRepository catalogRepo;

  @BeforeAll
  static void setUp() throws Exception {
    provider = new ValkeyClientProvider(valkey.getHost(), valkey.getMappedPort(6379));
    client = provider.getValkeyClient();
    var ds = new com.zaxxer.hikari.HikariDataSource();
    ds.setJdbcUrl(postgres.getJdbcUrl());
    ds.setUsername("flicenjoyer");
    ds.setPassword("flicenjoyer");
    catalogRepo = new com.flicenjoyer.db.CatalogRepository(ds);
  }

  @AfterAll
  static void tearDown() throws Exception {
    if (provider != null) provider.close();
  }

  @Test
  void uploadVideoCreatesHashAndCopiesFiles(@TempDir Path tempDir) throws Exception {
    var videoFile = tempDir.resolve("test.mp4");
    Files.writeString(videoFile, "fake video content");
    var thumbFile = tempDir.resolve("test.png");
    Files.writeString(thumbFile, "fake thumb content");

    var service = new UploadService(client, catalogRepo);
    var id =
        service.uploadVideo(
            "Test Title", "Action", "A test video", "tag1,tag2", 2024, 2.5, videoFile, thumbFile);

    assertNotNull(id);
    var fields = client.hgetall(gs("catalog:" + id)).get();
    assertEquals("Test Title", fields.get(gs("title")).toString());
    assertEquals("Action", fields.get(gs("genre")).toString());
    assertEquals("A test video", fields.get(gs("description")).toString());
    assertEquals("2024", fields.get(gs("releaseYear")).toString());
    assertEquals("0.0", fields.get(gs("rating")).toString());
    assertFalse(fields.get(gs("videoPath")).toString().isEmpty());
    assertFalse(fields.get(gs("thumbnailPath")).toString().isEmpty());
    assertTrue(Files.exists(Path.of(fields.get(gs("videoPath")).toString())));
  }

  @Test
  void uploadVideoWithoutThumbnail(@TempDir Path tempDir) throws Exception {
    var videoFile = tempDir.resolve("test2.mp4");
    Files.writeString(videoFile, "fake video");

    var service = new UploadService(client, catalogRepo);
    var id = service.uploadVideo("No Thumb", "Drama", "Desc", "tag", 2023, 1.0, videoFile, null);

    var fields = client.hgetall(gs("catalog:" + id)).get();
    assertEquals("No Thumb", fields.get(gs("title")).toString());
    assertEquals("", fields.get(gs("thumbnailPath")).toString());
  }
}
