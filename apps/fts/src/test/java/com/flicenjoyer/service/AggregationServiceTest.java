package com.flicenjoyer.service;

import static glide.api.models.GlideString.gs;
import static org.junit.jupiter.api.Assertions.*;

import com.flicenjoyer.model.AggregationResult;
import glide.api.models.GlideString;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;

class AggregationServiceTest {

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
}
