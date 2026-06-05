package com.flicenjoyer.service;

import static glide.api.models.GlideString.gs;
import static org.junit.jupiter.api.Assertions.*;

import com.flicenjoyer.valkey.UserProfileManager;
import com.flicenjoyer.valkey.ValkeyClientProvider;
import com.flicenjoyer.valkey.ValkeyClient;
import glide.api.GlideClient;
import java.nio.file.Files;
import java.util.Map;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.MethodOrderer;
import org.junit.jupiter.api.Order;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.TestMethodOrder;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.junit.jupiter.api.io.TempDir;
import org.testcontainers.containers.GenericContainer;
import org.testcontainers.containers.wait.strategy.Wait;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;

/** Integration tests for WatchHistoryService against a live Valkey instance. */
@Testcontainers
@EnabledIfEnvironmentVariable(named = "FLICENJOYER_INTEGRATION_TESTS", matches = "true")
@TestMethodOrder(MethodOrderer.OrderAnnotation.class)
class WatchHistoryServiceIntegrationTest {

  @Container
  static GenericContainer<?> valkey =
      new GenericContainer<>("valkey/valkey-bundle:unstable")
          .withExposedPorts(6379)
          .waitingFor(Wait.forLogMessage(".*Ready to accept connections.*", 1));

  static ValkeyClientProvider provider;
  static ValkeyClient client;
  static GlideClient rawClient;
  static WatchHistoryService service;
  static final String TEST_USER = "test-user-123";

  @BeforeAll
  static void setUp(@TempDir java.nio.file.Path tempDir) throws Exception {
    provider = new ValkeyClientProvider(valkey.getHost(), valkey.getMappedPort(6379));
    client = provider.getValkeyClient();
    rawClient = provider.getClient();
    // Create a temp profile file so UserProfileManager loads our test user
    var profileFile = tempDir.resolve("profile.yaml");
    Files.writeString(profileFile, "userId: " + TEST_USER + "\ndisplayName: Test User\n");
    var profile = new UserProfileManager(profileFile);
    profile.load();
    service = new WatchHistoryService(client, profile, null);
  }

  @AfterAll
  static void tearDown() throws Exception {
    if (provider != null) provider.close();
  }

  @Test
  @Order(1)
  void startWatchingCreatesEntry() throws Exception {
    service.startWatching("cat-1", "Test Movie");
    var fields = client.hgetall(gs("watch:" + TEST_USER + ":cat-1")).get();
    assertFalse(fields.isEmpty());
    assertEquals("cat-1", fields.get(gs("catalogId")).toString());
    assertEquals("Test Movie", fields.get(gs("title")).toString());
    assertEquals("0", fields.get(gs("resumeTimestamp")).toString());
    assertEquals("false", fields.get(gs("completed")).toString());
  }

  @Test
  @Order(2)
  void updateResumePointSetsTimestamp() throws Exception {
    service.updateResumePoint("cat-1", 120);
    long resume = service.getResumePoint("cat-1");
    assertEquals(120, resume);
  }

  @Test
  @Order(3)
  void getResumePointReturnsZeroForUnknown() throws Exception {
    long resume = service.getResumePoint("nonexistent");
    assertEquals(0, resume);
  }

  @Test
  @Order(4)
  void markCompletedSetsFlag() throws Exception {
    service.markCompleted("cat-1");
    var fields = client.hgetall(gs("watch:" + TEST_USER + ":cat-1")).get();
    assertEquals("true", fields.get(gs("completed")).toString());
  }

  @Test
  @Order(5)
  void getUserHistoryReturnsEntries() throws Exception {
    service.startWatching("cat-2", "Another Movie");
    var history = service.getUserHistory();
    assertTrue(history.size() >= 2, "Expected at least 2 entries, got " + history.size());
  }

  @Test
  @Order(6)
  void deleteWatchHistoryForVideoRemovesAllUsers() throws Exception {
    // Add watch entry for a second user
    client
        .hset(
            gs("watch:other-user:cat-1"),
            Map.of(
                gs("userId"), gs("other-user"),
                gs("catalogId"), gs("cat-1"),
                gs("title"), gs("Test Movie"),
                gs("resumeTimestamp"), gs("0"),
                gs("completed"), gs("false"),
                gs("lastWatched"), gs("1000")))
        .get();

    service.deleteWatchHistoryForVideo("cat-1");

    var keys = rawClient.keys(gs("watch:*:cat-1")).get();
    assertEquals(0, keys.length, "All watch entries for cat-1 should be deleted");
  }
}
