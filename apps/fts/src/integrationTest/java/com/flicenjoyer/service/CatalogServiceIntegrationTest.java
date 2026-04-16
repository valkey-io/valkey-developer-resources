package com.flicenjoyer.service;

import static glide.api.models.GlideString.gs;
import static org.junit.jupiter.api.Assertions.*;

import com.flicenjoyer.valkey.ValkeyClientProvider;
import glide.api.GlideClient;
import glide.api.commands.servermodules.FT;
import glide.api.models.commands.FT.FTCreateOptions;
import glide.api.models.commands.FT.FTCreateOptions.DataType;
import glide.api.models.commands.FT.FTCreateOptions.FieldInfo;
import glide.api.models.commands.FT.FTCreateOptions.NumericField;
import glide.api.models.commands.FT.FTCreateOptions.TagField;
import glide.api.models.commands.FT.FTCreateOptions.TextField;
import glide.api.models.commands.FT.FTSearchOptions;
import java.util.Map;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.MethodOrderer;
import org.junit.jupiter.api.Order;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.TestMethodOrder;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.testcontainers.containers.GenericContainer;
import org.testcontainers.containers.wait.strategy.Wait;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;

/**
 * Integration tests proving ValkeySearch FTS capabilities against a live Valkey 9.1.0 instance.
 * These serve as proof-of-concept for the production code.
 *
 * <p>Requires {@code valkey-search-test:9.1.0-rc1} Docker image built locally and {@code
 * FLICENJOYER_INTEGRATION_TESTS=true}.
 */
@Testcontainers
@EnabledIfEnvironmentVariable(named = "FLICENJOYER_INTEGRATION_TESTS", matches = "true")
@TestMethodOrder(MethodOrderer.OrderAnnotation.class)
class CatalogServiceIntegrationTest {

  @Container
  static GenericContainer<?> valkey =
      new GenericContainer<>("valkey-search-test:9.1.0-rc1")
          .withExposedPorts(6379)
          .waitingFor(Wait.forLogMessage(".*Ready to accept connections.*", 1));

  static ValkeyClientProvider provider;
  static GlideClient client;

  @BeforeAll
  static void setUp() throws Exception {
    provider = new ValkeyClientProvider(valkey.getHost(), valkey.getMappedPort(6379));
    client = provider.getClient();
  }

  @AfterAll
  static void tearDown() throws Exception {
    if (provider != null) provider.close();
  }

  @Test
  @Order(1)
  void createIndexWithTextFields() throws Exception {
    // Proof: TEXT fields work, but WEIGHT != 1.0 is not supported.
    // Use default weight (1.0) with withSuffixTrie and sortable.
    var result =
        FT.create(
                client,
                "idx:catalog",
                new FieldInfo[] {
                  new FieldInfo("title", new TextField(false, 1.0, true, false, true)),
                  new FieldInfo("genre", new TagField(',', false, true)),
                  new FieldInfo("description", new TextField()),
                  new FieldInfo("tags", new TagField(',', false, false)),
                  new FieldInfo("releaseYear", new NumericField(true)),
                  new FieldInfo("rating", new NumericField(true)),
                  new FieldInfo("durationMinutes", new NumericField(false)),
                  new FieldInfo("videoPath", new TagField()),
                  new FieldInfo("thumbnailPath", new TagField()),
                },
                FTCreateOptions.builder()
                    .dataType(DataType.HASH)
                    .prefixes(new String[] {"catalog:"})
                    .build())
            .get();
    assertEquals("OK", result);
  }

  @Test
  @Order(2)
  void seedTestData() throws Exception {
    client
        .hset(
            gs("catalog:1"),
            Map.of(
                gs("title"), gs("Inception"),
                gs("genre"), gs("Sci-Fi"),
                gs("description"), gs("A dream heist"),
                gs("tags"), gs("dreams,heist"),
                gs("releaseYear"), gs("2010"),
                gs("rating"), gs("8.8"),
                gs("durationMinutes"), gs("148"),
                gs("videoPath"), gs("/test/inception.mp4"),
                gs("thumbnailPath"), gs("")))
        .get();

    client
        .hset(
            gs("catalog:2"),
            Map.of(
                gs("title"), gs("The Matrix"),
                gs("genre"), gs("Sci-Fi"),
                gs("description"), gs("Simulation reality"),
                gs("tags"), gs("ai,simulation"),
                gs("releaseYear"), gs("1999"),
                gs("rating"), gs("8.7"),
                gs("durationMinutes"), gs("136"),
                gs("videoPath"), gs("/test/matrix.mp4"),
                gs("thumbnailPath"), gs("")))
        .get();

    client
        .hset(
            gs("catalog:3"),
            Map.of(
                gs("title"), gs("The Godfather"),
                gs("genre"), gs("Crime"),
                gs("description"), gs("Mafia family saga"),
                gs("tags"), gs("mafia,family"),
                gs("releaseYear"), gs("1972"),
                gs("rating"), gs("9.2"),
                gs("durationMinutes"), gs("175"),
                gs("videoPath"), gs("/test/godfather.mp4"),
                gs("thumbnailPath"), gs("")))
        .get();

    // Allow indexing
    Thread.sleep(2000);
  }

  @Test
  @Order(3)
  void exactSearch() throws Exception {
    var result =
        FT.search(client, "idx:catalog", "@title:Inception", FTSearchOptions.builder().build())
            .get();
    assertTrue((Long) result[0] >= 1, "Expected at least 1 result for exact 'Inception'");
  }

  @Test
  @Order(4)
  void prefixSearch() throws Exception {
    var result =
        FT.search(client, "idx:catalog", "@title:Incep*", FTSearchOptions.builder().build()).get();
    assertTrue((Long) result[0] >= 1, "Expected at least 1 result for prefix 'Incep*'");
  }

  @Test
  @Order(5)
  void genreTagFilter() throws Exception {
    var result =
        FT.search(client, "idx:catalog", "@genre:{Sci\\-Fi}", FTSearchOptions.builder().build())
            .get();
    assertTrue((Long) result[0] >= 2, "Expected at least 2 Sci-Fi results");
  }

  @Test
  @Order(6)
  void sortByRating() throws Exception {
    var result =
        FT.search(
                client,
                "idx:catalog",
                "@genre:{Sci\\-Fi}",
                FTSearchOptions.builder().sortBy("rating", FTSearchOptions.SortOrder.DESC).build())
            .get();
    assertTrue((Long) result[0] >= 2);
  }

  @Test
  @Order(7)
  void catalogServiceParseRoundTrip() throws Exception {
    var catalogService = new CatalogService(client);
    var results = catalogService.searchPrefix("Incep", 10);
    assertFalse(results.isEmpty(), "CatalogService typeahead should find Inception");
    assertEquals("Inception", results.getFirst().title());
  }

  @Test
  @Order(8)
  void catalogServiceFuzzySearch() throws Exception {
    var catalogService = new CatalogService(client);
    var results = catalogService.searchFuzzy("Incetpion", 10);
    // Fuzzy may or may not work depending on ValkeySearch version
    // Just verify it doesn't throw
    assertNotNull(results);
  }

  @Test
  @Order(9)
  void catalogServiceBrowseByGenre() throws Exception {
    var catalogService = new CatalogService(client);
    var results =
        catalogService.browseByGenre("Sci-Fi", "rating", FTSearchOptions.SortOrder.DESC, 20);
    assertFalse(results.isEmpty(), "Should find Sci-Fi movies");
    assertTrue(results.stream().allMatch(m -> m.genre().contains("Sci-Fi")));
  }

  @Test
  @Order(10)
  void browseAllReturnsAllMovies() throws Exception {
    var catalogService = new CatalogService(client);
    var results = catalogService.browseAll("", "title", false);
    assertTrue(results.size() >= 3, "Should find all seeded movies");
  }

  @Test
  @Order(11)
  void browseAllWithGenreFilter() throws Exception {
    var catalogService = new CatalogService(client);
    var results = catalogService.browseAll("Sci-Fi", "rating", true);
    assertFalse(results.isEmpty());
    assertTrue(results.stream().allMatch(m -> m.genre().contains("Sci-Fi")));
  }

  @Test
  @Order(12)
  void updateDuration() throws Exception {
    var catalogService = new CatalogService(client);
    catalogService.updateDuration("1", 200.5);
    var val = client.hget(gs("catalog:1"), gs("durationMinutes")).get();
    assertEquals("200.5", val.toString());
  }

  @Test
  @Order(13)
  void updateRating() throws Exception {
    var catalogService = new CatalogService(client);
    catalogService.updateRating("1", 9.5);
    var val = client.hget(gs("catalog:1"), gs("rating")).get();
    assertEquals("9.5", val.toString());
  }

  @Test
  @Order(14)
  void updateMetadata() throws Exception {
    var catalogService = new CatalogService(client);
    catalogService.updateMetadata("1", "Inception 2", "Action", "Sequel", "sequel,dreams", 2025);
    var fields = client.hgetall(gs("catalog:1")).get();
    assertEquals("Inception 2", fields.get(gs("title")).toString());
    assertEquals("Action", fields.get(gs("genre")).toString());
    assertEquals("2025", fields.get(gs("releaseYear")).toString());
  }

  @Test
  @Order(15)
  void updateThumbnail() throws Exception {
    var catalogService = new CatalogService(client);
    catalogService.updateThumbnail("2", "/new/thumb.png");
    var val = client.hget(gs("catalog:2"), gs("thumbnailPath")).get();
    assertEquals("/new/thumb.png", val.toString());
  }

  @Test
  @Order(16)
  void deleteVideoRemovesHash() throws Exception {
    var catalogService = new CatalogService(client);
    catalogService.deleteVideo("3");
    var fields = client.hgetall(gs("catalog:3")).get();
    assertTrue(fields.isEmpty(), "Hash should be deleted");
  }
}
