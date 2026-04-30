package com.flicenjoyer.service;

import static glide.api.models.GlideString.gs;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

import com.flicenjoyer.model.AggregationResult;
import glide.api.BaseClient;
import glide.api.GlideClient;
import glide.api.commands.servermodules.FT;
import glide.api.models.Batch;
import glide.api.models.GlideString;
import glide.api.models.commands.FT.FTAggregateOptions;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.CompletableFuture;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.MockedStatic;
import org.mockito.junit.jupiter.MockitoExtension;

@ExtendWith(MockitoExtension.class)
class AggregationServiceTest {

  @Mock GlideClient client;
  AggregationService service;

  @BeforeEach
  void setUp() {
    service = new AggregationService(client);
  }

  @Test
  void parseAggregateResultsExtractsLabelAndMetrics() {
    @SuppressWarnings("unchecked")
    Map<GlideString, Object>[] raw = new Map[2];

    Map<GlideString, Object> row1 = new LinkedHashMap<>();
    row1.put(gs("title"), gs("Inception"));
    row1.put(gs("viewerCount"), gs("42"));
    raw[0] = row1;

    Map<GlideString, Object> row2 = new LinkedHashMap<>();
    row2.put(gs("title"), gs("The Matrix"));
    row2.put(gs("viewerCount"), gs("37"));
    raw[1] = row2;

    List<AggregationResult> results = AggregationService.parseAggregateResults(raw, "title");

    assertEquals(2, results.size());
    assertEquals("Inception", results.get(0).label());
    assertEquals("42", results.get(0).metrics().get("viewerCount"));
    assertEquals("The Matrix", results.get(1).label());
    assertEquals("37", results.get(1).metrics().get("viewerCount"));
  }

  @Test
  void parseAggregateResultsHandlesGenreSummary() {
    @SuppressWarnings("unchecked")
    Map<GlideString, Object>[] raw = new Map[1];

    Map<GlideString, Object> row = new LinkedHashMap<>();
    row.put(gs("genre"), gs("Sci-Fi"));
    row.put(gs("titleCount"), gs("15"));
    row.put(gs("avgRating"), gs("8.2"));
    raw[0] = row;

    List<AggregationResult> results = AggregationService.parseAggregateResults(raw, "genre");

    assertEquals(1, results.size());
    assertEquals("Sci-Fi", results.getFirst().label());
    assertEquals("15", results.getFirst().metrics().get("titleCount"));
    assertEquals("8.2", results.getFirst().metrics().get("avgRating"));
  }

  @Test
  void parseAggregateResultsHandlesEmptyArray() {
    @SuppressWarnings("unchecked")
    Map<GlideString, Object>[] raw = new Map[0];

    List<AggregationResult> results = AggregationService.parseAggregateResults(raw, "title");
    assertTrue(results.isEmpty());
  }

  @SuppressWarnings("unchecked")
  @Test
  void topTitlesByViewersBatchFetchesTitles() throws Exception {
    Map<GlideString, Object>[] aggResult = new Map[1];
    Map<GlideString, Object> row = new LinkedHashMap<>();
    row.put(gs("catalogId"), gs("vid1"));
    row.put(gs("viewerCount"), gs("5"));
    aggResult[0] = row;

    Map<GlideString, GlideString> catalogFields = new LinkedHashMap<>();
    catalogFields.put(gs("title"), gs("Inception"));

    when(client.exec(any(Batch.class), eq(false)))
        .thenReturn(CompletableFuture.completedFuture(new Object[] {catalogFields}));

    try (MockedStatic<FT> ft = mockStatic(FT.class)) {
      ft.when(
              () ->
                  FT.aggregate(
                      any(BaseClient.class),
                      any(String.class),
                      any(String.class),
                      any(FTAggregateOptions.class)))
          .thenReturn(CompletableFuture.completedFuture(aggResult));

      var results = service.topTitlesByViewers(10);
      assertEquals(1, results.size());
      assertEquals("Inception", results.getFirst().label());
      assertEquals("5", results.getFirst().metrics().get("viewerCount"));
      verify(client).exec(any(Batch.class), eq(false)); // batched, not N+1
    }
  }

  @SuppressWarnings("unchecked")
  @Test
  void catalogSummaryByGenreReturnsResults() throws Exception {
    Map<GlideString, Object>[] aggResult = new Map[1];
    Map<GlideString, Object> row = new LinkedHashMap<>();
    row.put(gs("genre"), gs("Action"));
    row.put(gs("titleCount"), gs("10"));
    row.put(gs("avgRating"), gs("7.5"));
    aggResult[0] = row;

    try (MockedStatic<FT> ft = mockStatic(FT.class)) {
      ft.when(
              () ->
                  FT.aggregate(
                      any(BaseClient.class),
                      any(String.class),
                      any(String.class),
                      any(FTAggregateOptions.class)))
          .thenReturn(CompletableFuture.completedFuture(aggResult));

      var results = service.catalogSummaryByGenre();
      assertEquals(1, results.size());
      assertEquals("Action", results.getFirst().label());
      assertEquals("10", results.getFirst().metrics().get("titleCount"));
    }
  }
}
