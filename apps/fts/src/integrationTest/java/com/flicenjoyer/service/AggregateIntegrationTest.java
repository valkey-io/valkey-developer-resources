package com.flicenjoyer.service;

import static glide.api.models.GlideString.gs;
import static org.junit.jupiter.api.Assertions.*;

import com.flicenjoyer.valkey.ValkeyClientProvider;
import glide.api.GlideClient;
import glide.api.commands.servermodules.FT;
import glide.api.models.commands.FT.FTAggregateOptions;
import glide.api.models.commands.FT.FTAggregateOptions.GroupBy;
import glide.api.models.commands.FT.FTAggregateOptions.GroupBy.Reducer;
import glide.api.models.commands.FT.FTAggregateOptions.Limit;
import glide.api.models.commands.FT.FTAggregateOptions.SortBy;
import glide.api.models.commands.FT.FTAggregateOptions.SortBy.SortOrder;
import glide.api.models.commands.FT.FTAggregateOptions.SortBy.SortProperty;
import glide.api.models.commands.FT.FTCreateOptions;
import glide.api.models.commands.FT.FTCreateOptions.DataType;
import glide.api.models.commands.FT.FTCreateOptions.FieldInfo;
import glide.api.models.commands.FT.FTCreateOptions.NumericField;
import glide.api.models.commands.FT.FTCreateOptions.TagField;
import glide.api.models.commands.FT.FTCreateOptions.TextField;
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
 * Integration tests proving FT.AGGREGATE and benchmarking capabilities against a live Valkey
 * instance. Validates grouping, counting, averaging, and sorting for the Reports and Benchmarks
 * views.
 */
@Testcontainers
@EnabledIfEnvironmentVariable(named = "FLICENJOYER_INTEGRATION_TESTS", matches = "true")
@TestMethodOrder(MethodOrderer.OrderAnnotation.class)
class AggregateIntegrationTest {

  @Container
  @SuppressWarnings("resource") // Lifecycle managed by Testcontainers @Container
  static GenericContainer<?> valkey =
      new GenericContainer<>("valkey/valkey-bundle:unstable")
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
  void createIndexes() throws Exception {
    FT.create(
            client,
            "idx:agg_catalog",
            new FieldInfo[] {
              new FieldInfo("title", new TextField()),
              new FieldInfo("genre", new TagField(',', false, true)),
              new FieldInfo("rating", new NumericField(true)),
              new FieldInfo("releaseYear", new NumericField(true)),
            },
            FTCreateOptions.builder()
                .dataType(DataType.HASH)
                .prefixes(new String[] {"agg_cat:"})
                .build())
        .get();

    FT.create(
            client,
            "idx:agg_watch",
            new FieldInfo[] {
              new FieldInfo("userId", new TagField()),
              new FieldInfo("catalogId", new TagField()),
              new FieldInfo("completed", new TagField()),
              new FieldInfo("lastWatched", new NumericField(true)),
            },
            FTCreateOptions.builder()
                .dataType(DataType.HASH)
                .prefixes(new String[] {"agg_watch:"})
                .build())
        .get();
  }

  @Test
  @Order(2)
  void seedData() throws Exception {
    // 3 Sci-Fi, 2 Action
    client
        .hset(
            gs("agg_cat:1"),
            Map.of(
                gs("title"),
                gs("Movie A"),
                gs("genre"),
                gs("Sci-Fi"),
                gs("rating"),
                gs("8.5"),
                gs("releaseYear"),
                gs("2020")))
        .get();
    client
        .hset(
            gs("agg_cat:2"),
            Map.of(
                gs("title"),
                gs("Movie B"),
                gs("genre"),
                gs("Sci-Fi"),
                gs("rating"),
                gs("7.0"),
                gs("releaseYear"),
                gs("2021")))
        .get();
    client
        .hset(
            gs("agg_cat:3"),
            Map.of(
                gs("title"),
                gs("Movie C"),
                gs("genre"),
                gs("Sci-Fi"),
                gs("rating"),
                gs("9.0"),
                gs("releaseYear"),
                gs("2022")))
        .get();
    client
        .hset(
            gs("agg_cat:4"),
            Map.of(
                gs("title"),
                gs("Movie D"),
                gs("genre"),
                gs("Action"),
                gs("rating"),
                gs("6.0"),
                gs("releaseYear"),
                gs("2020")))
        .get();
    client
        .hset(
            gs("agg_cat:5"),
            Map.of(
                gs("title"),
                gs("Movie E"),
                gs("genre"),
                gs("Action"),
                gs("rating"),
                gs("8.0"),
                gs("releaseYear"),
                gs("2023")))
        .get();

    // Watch history: Movie A watched by 3 users, Movie B by 2, Movie D by 1
    client
        .hset(
            gs("agg_watch:u1:1"),
            Map.of(
                gs("userId"),
                gs("u1"),
                gs("catalogId"),
                gs("1"),
                gs("completed"),
                gs("true"),
                gs("lastWatched"),
                gs("1000")))
        .get();
    client
        .hset(
            gs("agg_watch:u2:1"),
            Map.of(
                gs("userId"),
                gs("u2"),
                gs("catalogId"),
                gs("1"),
                gs("completed"),
                gs("true"),
                gs("lastWatched"),
                gs("2000")))
        .get();
    client
        .hset(
            gs("agg_watch:u3:1"),
            Map.of(
                gs("userId"),
                gs("u3"),
                gs("catalogId"),
                gs("1"),
                gs("completed"),
                gs("false"),
                gs("lastWatched"),
                gs("3000")))
        .get();
    client
        .hset(
            gs("agg_watch:u1:2"),
            Map.of(
                gs("userId"),
                gs("u1"),
                gs("catalogId"),
                gs("2"),
                gs("completed"),
                gs("true"),
                gs("lastWatched"),
                gs("1500")))
        .get();
    client
        .hset(
            gs("agg_watch:u2:2"),
            Map.of(
                gs("userId"),
                gs("u2"),
                gs("catalogId"),
                gs("2"),
                gs("completed"),
                gs("true"),
                gs("lastWatched"),
                gs("2500")))
        .get();
    client
        .hset(
            gs("agg_watch:u1:4"),
            Map.of(
                gs("userId"),
                gs("u1"),
                gs("catalogId"),
                gs("4"),
                gs("completed"),
                gs("true"),
                gs("lastWatched"),
                gs("1200")))
        .get();

    Thread.sleep(2000);
  }

  @Test
  @Order(3)
  void aggregateCatalogByGenre() throws Exception {
    var results =
        FT.aggregate(
                client,
                "idx:agg_catalog",
                "@releaseYear:[0 9999]",
                FTAggregateOptions.builder()
                    .loadFields(new String[] {"@genre"})
                    .addClause(
                        new GroupBy(
                            new String[] {"@genre"},
                            new Reducer[] {
                              new Reducer("COUNT", new String[] {}, "titleCount"),
                              new Reducer("AVG", new String[] {"@rating"}, "avgRating")
                            }))
                    .addClause(
                        new SortBy(
                            new SortProperty[] {new SortProperty("@titleCount", SortOrder.DESC)}))
                    .build())
            .get();

    assertTrue(results.length >= 1, "Expected at least 1 genre group, got " + results.length);
    // Verify result structure has expected keys
    var first = results[0];
    assertNotNull(first.get(gs("genre")), "Missing 'genre' key. Keys: " + first.keySet());
    assertNotNull(first.get(gs("titleCount")), "Missing 'titleCount' key. Keys: " + first.keySet());
  }

  @Test
  @Order(4)
  void aggregateTopVideosByViewerCount() throws Exception {
    var results =
        FT.aggregate(
                client,
                "idx:agg_watch",
                "@lastWatched:[0 9999999999]",
                FTAggregateOptions.builder()
                    .loadFields(new String[] {"@catalogId"})
                    .addClause(
                        new GroupBy(
                            new String[] {"@catalogId"},
                            new Reducer[] {new Reducer("COUNT", new String[] {}, "viewerCount")}))
                    .addClause(
                        new SortBy(
                            new SortProperty[] {new SortProperty("@viewerCount", SortOrder.DESC)}))
                    .addClause(new Limit(0, 10))
                    .build())
            .get();

    assertTrue(results.length >= 1, "Expected at least 1 result, got " + results.length);
    var first = results[0];
    assertNotNull(first.get(gs("catalogId")), "Missing 'catalogId' key. Keys: " + first.keySet());
    assertNotNull(
        first.get(gs("viewerCount")), "Missing 'viewerCount' key. Keys: " + first.keySet());
    // catalogId "1" should have highest viewer count (3)
    assertEquals("1", first.get(gs("catalogId")).toString());
    assertEquals("3", first.get(gs("viewerCount")).toString());
  }

  @Test
  @Order(5)
  void benchmarkSearchLatency() throws Exception {
    var result =
        BenchmarkService.benchmark(
            () ->
                FT.search(
                        client,
                        "idx:agg_catalog",
                        "@genre:{Sci\\-Fi}",
                        glide.api.models.commands.FT.FTSearchOptions.builder().build())
                    .get(),
            100);

    assertTrue(result.medianMs() >= 0);
    assertTrue(result.p95Ms() >= result.medianMs());
    assertTrue(result.opsPerSecond() > 0);
    System.out.println(
        "Search benchmark: median="
            + result.medianMs()
            + "ms, p95="
            + result.p95Ms()
            + "ms, ops/sec="
            + result.opsPerSecond());
  }

  @Test
  @Order(6)
  void benchmarkAggregateLatency() throws Exception {
    var result =
        BenchmarkService.benchmark(
            () ->
                FT.aggregate(
                        client,
                        "idx:agg_catalog",
                        "@releaseYear:[0 9999]",
                        FTAggregateOptions.builder()
                            .addClause(
                                new GroupBy(
                                    new String[] {"@genre"},
                                    new Reducer[] {new Reducer("COUNT", new String[] {}, "cnt")}))
                            .build())
                    .get(),
            100);

    assertTrue(result.medianMs() >= 0);
    assertTrue(result.opsPerSecond() > 0);
    System.out.println(
        "Aggregate benchmark: median="
            + result.medianMs()
            + "ms, p95="
            + result.p95Ms()
            + "ms, ops/sec="
            + result.opsPerSecond());
  }

  @Test
  @Order(7)
  void createProductionIndexes() throws Exception {
    // Create indexes matching ValkeyKeys constants for service-layer tests
    FT.create(
            client,
            "idx:catalog",
            new FieldInfo[] {
              new FieldInfo("title", new TextField()),
              new FieldInfo("genre", new TagField(',', false, true)),
              new FieldInfo("rating", new NumericField(true)),
              new FieldInfo("releaseYear", new NumericField(true)),
            },
            FTCreateOptions.builder()
                .dataType(DataType.HASH)
                .prefixes(new String[] {"catalog:"})
                .build())
        .get();

    FT.create(
            client,
            "idx:watch",
            new FieldInfo[] {
              new FieldInfo("userId", new TagField()),
              new FieldInfo("catalogId", new TagField()),
              new FieldInfo("completed", new TagField()),
              new FieldInfo("lastWatched", new NumericField(true)),
            },
            FTCreateOptions.builder()
                .dataType(DataType.HASH)
                .prefixes(new String[] {"watch:"})
                .build())
        .get();

    // Seed catalog data
    client
        .hset(
            gs("catalog:t1"),
            Map.of(
                gs("title"),
                gs("Film A"),
                gs("genre"),
                gs("Sci-Fi"),
                gs("rating"),
                gs("8.0"),
                gs("releaseYear"),
                gs("2020"),
                gs("videoPath"),
                gs(""),
                gs("thumbnailPath"),
                gs(""),
                gs("description"),
                gs(""),
                gs("tags"),
                gs(""),
                gs("durationMinutes"),
                gs("90")))
        .get();
    client
        .hset(
            gs("catalog:t2"),
            Map.of(
                gs("title"),
                gs("Film B"),
                gs("genre"),
                gs("Action"),
                gs("rating"),
                gs("7.0"),
                gs("releaseYear"),
                gs("2021"),
                gs("videoPath"),
                gs(""),
                gs("thumbnailPath"),
                gs(""),
                gs("description"),
                gs(""),
                gs("tags"),
                gs(""),
                gs("durationMinutes"),
                gs("120")))
        .get();

    // Seed watch data
    client
        .hset(
            gs("watch:u1:t1"),
            Map.of(
                gs("userId"),
                gs("u1"),
                gs("catalogId"),
                gs("t1"),
                gs("completed"),
                gs("true"),
                gs("lastWatched"),
                gs("1000"),
                gs("title"),
                gs("Film A"),
                gs("resumeTimestamp"),
                gs("0")))
        .get();
    client
        .hset(
            gs("watch:u2:t1"),
            Map.of(
                gs("userId"),
                gs("u2"),
                gs("catalogId"),
                gs("t1"),
                gs("completed"),
                gs("false"),
                gs("lastWatched"),
                gs("2000"),
                gs("title"),
                gs("Film A"),
                gs("resumeTimestamp"),
                gs("50")))
        .get();
    client
        .hset(
            gs("watch:u1:t2"),
            Map.of(
                gs("userId"),
                gs("u1"),
                gs("catalogId"),
                gs("t2"),
                gs("completed"),
                gs("true"),
                gs("lastWatched"),
                gs("1500"),
                gs("title"),
                gs("Film B"),
                gs("resumeTimestamp"),
                gs("0")))
        .get();

    Thread.sleep(2000);
  }

  @Test
  @Order(8)
  void serviceTopTitlesByViewers() throws Exception {
    var aggService = new AggregationService(client);
    var results = aggService.topTitlesByViewers(10);

    assertFalse(results.isEmpty(), "Should return at least 1 result");
    // Film A (t1) has 2 viewers, Film B (t2) has 1
    assertEquals("Film A", results.getFirst().label());
    assertEquals("2", results.getFirst().metrics().get("viewerCount"));
  }

  @Test
  @Order(9)
  void serviceCatalogSummaryByGenre() throws Exception {
    var aggService = new AggregationService(client);
    var results = aggService.catalogSummaryByGenre();

    assertFalse(results.isEmpty(), "Should return at least 1 genre group");
    // Verify structure
    var first = results.getFirst();
    assertNotNull(first.label());
    assertNotNull(first.metrics().get("titleCount"));
    assertNotNull(first.metrics().get("avgRating"));
  }
}
