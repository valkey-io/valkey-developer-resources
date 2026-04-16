package com.flicenjoyer.service;

import static glide.api.models.GlideString.gs;

import com.flicenjoyer.model.AggregationResult;
import com.flicenjoyer.valkey.ValkeyKeys;
import glide.api.GlideClient;
import glide.api.commands.servermodules.FT;
import glide.api.models.GlideString;
import glide.api.models.commands.FT.FTAggregateOptions;
import glide.api.models.commands.FT.FTAggregateOptions.GroupBy;
import glide.api.models.commands.FT.FTAggregateOptions.GroupBy.Reducer;
import glide.api.models.commands.FT.FTAggregateOptions.Limit;
import glide.api.models.commands.FT.FTAggregateOptions.SortBy;
import glide.api.models.commands.FT.FTAggregateOptions.SortBy.SortOrder;
import glide.api.models.commands.FT.FTAggregateOptions.SortBy.SortProperty;
import java.util.Arrays;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ExecutionException;

/** FT.AGGREGATE report generation for catalog and watch history analytics. */
public class AggregationService {

  private static final java.util.logging.Logger LOG =
      java.util.logging.Logger.getLogger(AggregationService.class.getName());
  private static final String ALL_TIMESTAMPS = "@lastWatched:[0 9999999999]";
  private static final String ALL_YEARS = "@releaseYear:[0 9999]";

  private final GlideClient client;
  private final CatalogService catalogService;

  public AggregationService(GlideClient client, CatalogService catalogService) {
    this.client = client;
    this.catalogService = catalogService;
  }

  /**
   * Top videos by viewer count. Groups watch entries by catalogId (TAG field), counts viewers, then
   * resolves titles via CatalogService.
   */
  public List<AggregationResult> topTitlesByViewers(int limit)
      throws ExecutionException, InterruptedException {
    var raw =
        FT.aggregate(
                client,
                ValkeyKeys.WATCH_INDEX,
                ALL_TIMESTAMPS,
                FTAggregateOptions.builder()
                    .loadFields(new String[] {"@catalogId"})
                    .addClause(
                        new GroupBy(
                            new String[] {"@catalogId"},
                            new Reducer[] {new Reducer("COUNT", new String[] {}, "viewerCount")}))
                    .addClause(
                        new SortBy(
                            new SortProperty[] {new SortProperty("@viewerCount", SortOrder.DESC)}))
                    .addClause(new Limit(0, limit))
                    .build())
            .get();

    // Resolve catalogId → title
    return Arrays.stream(raw)
        .map(
            row -> {
              var catalogId = row.getOrDefault(gs("catalogId"), gs("")).toString();
              var viewerCount = row.getOrDefault(gs("viewerCount"), gs("0")).toString();
              String title = catalogId;
              try {
                var movie = catalogService.getById(catalogId);
                if (movie != null) title = movie.title();
              } catch (Exception ex) {
                LOG.warning(
                    "[aggregate] Failed to resolve title for "
                        + catalogId
                        + ": "
                        + ex.getMessage());
              }
              return new AggregationResult(
                  title, Map.of("viewerCount", viewerCount, "catalogId", catalogId));
            })
        .toList();
  }

  /** Catalog summary grouped by genre — title count and average rating per genre. */
  public List<AggregationResult> catalogSummaryByGenre()
      throws ExecutionException, InterruptedException {
    var raw =
        FT.aggregate(
                client,
                ValkeyKeys.CATALOG_INDEX,
                ALL_YEARS,
                FTAggregateOptions.builder()
                    .loadFields(new String[] {"@genre", "@rating"})
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

    return parseAggregateResults(raw, "genre");
  }

  static List<AggregationResult> parseAggregateResults(
      Map<GlideString, Object>[] raw, String labelField) {
    return Arrays.stream(raw)
        .map(
            row -> {
              String label = "";
              Map<String, Object> metrics = new HashMap<>();
              for (var entry : row.entrySet()) {
                var key = entry.getKey().toString();
                var strVal =
                    entry.getValue() instanceof GlideString gStr
                        ? gStr.toString()
                        : String.valueOf(entry.getValue());
                if (key.equals(labelField)) label = strVal;
                else metrics.put(key, strVal);
              }
              return new AggregationResult(label, metrics);
            })
        .toList();
  }
}
