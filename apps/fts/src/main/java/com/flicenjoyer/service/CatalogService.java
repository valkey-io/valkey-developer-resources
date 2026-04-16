package com.flicenjoyer.service;

import static glide.api.models.GlideString.gs;

import com.flicenjoyer.model.Genre;
import com.flicenjoyer.model.Movie;
import com.flicenjoyer.valkey.AppPaths;
import com.flicenjoyer.valkey.HashParser;
import com.flicenjoyer.valkey.ValkeyKeys;
import glide.api.GlideClient;
import glide.api.commands.servermodules.FT;
import glide.api.models.GlideString;
import glide.api.models.commands.FT.FTSearchOptions;
import glide.api.models.commands.FT.FTSearchOptions.SortOrder;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ExecutionException;

/** Catalog search, browse, and CRUD operations backed by ValkeySearch FTS and Valkey hashes. */
public class CatalogService {

  private static final java.util.logging.Logger LOG =
      java.util.logging.Logger.getLogger(CatalogService.class.getName());

  private final GlideClient client;

  public CatalogService(GlideClient client) {
    this.client = client;
  }

  public List<Movie> searchPrefix(String prefix, int limit)
      throws ExecutionException, InterruptedException {
    var escaped = escapeQuery(prefix).trim();
    var words = escaped.split("\\s+");
    var sb = new StringBuilder();
    for (int i = 0; i < words.length; i++) {
      if (words[i].isBlank()) continue;
      if (i > 0) sb.append(" ");
      sb.append(words[i]);
      if (i == words.length - 1) sb.append("*");
    }
    var terms = sb.toString();
    // Match title OR description (TEXT) OR genre (TAG)
    var query =
        "(@title:" + terms + ")|(@description:" + terms + ")|(@genre:{" + escapeTag(prefix) + "})";
    return executeSearch(query, limit, null, null);
  }

  public List<Movie> searchFuzzy(String term, int limit)
      throws ExecutionException, InterruptedException {
    var escaped = escapeQuery(term).trim();
    var words = escaped.split("\\s+");
    var fuzzyTerms =
        java.util.Arrays.stream(words)
            .filter(w -> !w.isBlank())
            .map(w -> "%%" + w + "%%")
            .collect(java.util.stream.Collectors.joining(" "));
    // Match title OR description (TEXT fuzzy) OR genre (TAG exact)
    var query =
        "(@title:"
            + fuzzyTerms
            + ")|(@description:"
            + fuzzyTerms
            + ")|(@genre:{"
            + escapeTag(term)
            + "})";
    return executeSearch(query, limit, null, null);
  }

  public List<Movie> search(String prefix, int limit)
      throws ExecutionException, InterruptedException {
    var prefixResults = searchPrefix(prefix, limit);
    var fuzzyResults = searchFuzzy(prefix, limit);
    // Merge, prefix results first, deduplicate by ID
    var seen = new java.util.LinkedHashMap<String, Movie>();
    for (var m : prefixResults) seen.putIfAbsent(m.id(), m);
    for (var m : fuzzyResults) seen.putIfAbsent(m.id(), m);
    return seen.values().stream().limit(limit).toList();
  }

  public List<Movie> browseByGenre(String genre, String sortField, SortOrder order, int limit)
      throws ExecutionException, InterruptedException {
    var query = "@genre:{" + escapeTag(genre) + "}";
    return executeSearch(query, limit, sortField, order);
  }

  private List<Movie> executeSearch(String query, int limit, String sortField, SortOrder sortOrder)
      throws ExecutionException, InterruptedException {
    var opts = FTSearchOptions.builder().limit(0, limit);
    if (sortField != null) {
      opts.sortBy(sortField, sortOrder != null ? sortOrder : SortOrder.ASC);
    }
    LOG.info("[catalog] FT.SEARCH query: " + query);
    var result = FT.search(client, ValkeyKeys.CATALOG_INDEX, query, opts.build()).get();
    LOG.info("[catalog] FT.SEARCH result length: " + result.length + ", count: " + result[0]);
    return parseSearchResults(result);
  }

  @SuppressWarnings("unchecked")
  static List<Movie> parseSearchResults(Object[] result) {
    if (result.length < 2) return List.of();
    var docs = (Map<GlideString, Map<GlideString, GlideString>>) result[1];
    return docs.entrySet().stream()
        .map(e -> HashParser.toMovie(e.getKey().toString(), e.getValue()))
        .toList();
  }

  static String escapeQuery(String input) {
    // Replace hyphens with spaces (tokenizer treats them as word separators)
    // then escape remaining special characters
    return input.replace('-', ' ').replaceAll("[^a-zA-Z0-9 ]", "\\\\$0");
  }

  static String escapeTag(String input) {
    return input.replaceAll("[^a-zA-Z0-9 ]", "\\\\$0");
  }

  /**
   * Fallback browse using KEYS + HGETALL — works without ValkeySearch. Filters and sorts
   * client-side. Will be replaced by FT.SEARCH once ValkeySearch 1.2 is available.
   */
  public List<Movie> browseAll(String genreFilter, String sortField, boolean descending)
      throws ExecutionException, InterruptedException {
    var keys = client.keys(gs(ValkeyKeys.CATALOG_PREFIX + "*")).get();
    var movies = new ArrayList<Movie>();
    for (var key : keys) {
      var fields = client.hgetall(key).get();
      if (fields.isEmpty()) continue;
      var movie = HashParser.toMovie(key.toString(), fields);
      if (genreFilter != null && !genreFilter.isEmpty() && !genreFilter.equals("All")) {
        if (genreFilter.equals("Other")) {
          if (Genre.isKnown(movie.genre())) continue;
        } else if (!movie.genre().equalsIgnoreCase(genreFilter)) {
          continue;
        }
      }
      movies.add(movie);
    }
    Comparator<Movie> cmp =
        switch (sortField != null ? sortField : "title") {
          case "rating" -> Comparator.comparingDouble(Movie::rating);
          case "releaseYear" -> Comparator.comparingInt(Movie::releaseYear);
          default -> Comparator.comparing(Movie::title, String.CASE_INSENSITIVE_ORDER);
        };
    if (descending) cmp = cmp.reversed();
    movies.sort(cmp);
    return movies;
  }

  public Movie getById(String catalogId) throws ExecutionException, InterruptedException {
    var fields = client.hgetall(gs(ValkeyKeys.catalogKey(catalogId))).get();
    if (fields.isEmpty()) return null;
    return HashParser.toMovie(ValkeyKeys.catalogKey(catalogId), fields);
  }

  public void updateDuration(String catalogId, double durationMinutes)
      throws ExecutionException, InterruptedException {
    setField(catalogId, "durationMinutes", String.valueOf(durationMinutes));
  }

  public void updateRating(String catalogId, double rating)
      throws ExecutionException, InterruptedException {
    setField(catalogId, "rating", String.valueOf(rating));
  }

  public void updateMetadata(
      String catalogId,
      String title,
      String genre,
      String description,
      String tags,
      int releaseYear)
      throws ExecutionException, InterruptedException {
    client
        .hset(
            gs(ValkeyKeys.catalogKey(catalogId)),
            Map.of(
                gs("title"), gs(title),
                gs("genre"), gs(genre),
                gs("description"), gs(description),
                gs("tags"), gs(tags),
                gs("releaseYear"), gs(String.valueOf(releaseYear))))
        .get();
  }

  public void updateThumbnail(String catalogId, String thumbnailPath)
      throws ExecutionException, InterruptedException {
    setField(catalogId, "thumbnailPath", thumbnailPath);
  }

  private void setField(String catalogId, String field, String value)
      throws ExecutionException, InterruptedException {
    client.hset(gs(ValkeyKeys.catalogKey(catalogId)), Map.of(gs(field), gs(value))).get();
  }

  public void deleteVideo(String catalogId) throws ExecutionException, InterruptedException {
    // Get file paths before deleting hash
    var fields = client.hgetall(gs(ValkeyKeys.catalogKey(catalogId))).get();
    client.del(new GlideString[] {gs(ValkeyKeys.catalogKey(catalogId))}).get();
    // Delete local files (only under media directory)
    var videoPath = fields.getOrDefault(gs("videoPath"), gs("")).toString();
    var thumbPath = fields.getOrDefault(gs("thumbnailPath"), gs("")).toString();
    try {
      deleteIfUnderMedia(videoPath);
      deleteIfUnderMedia(thumbPath);
    } catch (java.io.IOException e) {
      LOG.warning("[catalog] Failed to delete files for " + catalogId + ": " + e.getMessage());
    }
  }

  private static void deleteIfUnderMedia(String path) throws java.io.IOException {
    if (path.isEmpty()) return;
    var resolved = java.nio.file.Path.of(path).toAbsolutePath().normalize();
    if (!resolved.startsWith(AppPaths.MEDIA)) {
      LOG.warning("[catalog] Refusing to delete path outside media dir: " + path);
      return;
    }
    java.nio.file.Files.deleteIfExists(resolved);
  }
}
