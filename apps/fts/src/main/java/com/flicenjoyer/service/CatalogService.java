package com.flicenjoyer.service;

import static glide.api.models.GlideString.gs;

import com.flicenjoyer.db.CatalogRepository;
import com.flicenjoyer.model.Genre;
import com.flicenjoyer.model.Movie;
import com.flicenjoyer.valkey.AppPaths;
import com.flicenjoyer.valkey.HashParser;
import com.flicenjoyer.valkey.QueryEscaper;
import com.flicenjoyer.valkey.ValkeyClient;
import com.flicenjoyer.valkey.ValkeyKeys;
import glide.api.models.GlideString;
import glide.api.models.commands.FT.FTSearchOptions;
import glide.api.models.commands.FT.FTSearchOptions.SortOrder;
import java.sql.SQLException;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ExecutionException;

/**
 * Catalog search, browse, and CRUD operations. Uses ValkeySearch FTS for search, Valkey hashes as
 * cache, and PostgreSQL as source of truth.
 */
public class CatalogService {

  private static final java.util.logging.Logger LOG =
      java.util.logging.Logger.getLogger(CatalogService.class.getName());

  private final ValkeyClient client;
  private final CatalogRepository catalogRepo;

  public CatalogService(ValkeyClient client, CatalogRepository catalogRepo) {
    this.client = client;
    this.catalogRepo = catalogRepo;
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
    LOG.fine(() -> "[catalog] FT.SEARCH query: " + query);
    var result = client.ftSearch(ValkeyKeys.CATALOG_INDEX, query, opts.build()).get();
    LOG.fine(() -> "[catalog] FT.SEARCH result length: " + result.length + ", count: " + result[0]);
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
    return QueryEscaper.escapeQuery(input);
  }

  static String escapeTag(String input) {
    return QueryEscaper.escapeTag(input);
  }

  /** Browse catalog using FT.SEARCH on idx:catalog. */
  public List<Movie> browseAll(String genreFilter, String sortField, boolean descending)
      throws ExecutionException, InterruptedException {
    boolean isOther = genreFilter != null && genreFilter.equals("Other");
    boolean hasGenre =
        genreFilter != null && !genreFilter.isEmpty() && !genreFilter.equals("All") && !isOther;

    var query = hasGenre ? "@genre:{" + escapeTag(genreFilter) + "}" : "@releaseYear:[0 inf]";
    var sortOrder = descending ? SortOrder.DESC : SortOrder.ASC;
    String resolvedSort = sortField != null ? sortField : "title";

    var opts = FTSearchOptions.builder().limit(0, 1000);
    if (!isOther) {
      opts.sortBy(resolvedSort, sortOrder);
    }
    var result = client.ftSearch(ValkeyKeys.CATALOG_INDEX, query, opts.build()).get();
    var movies = new ArrayList<>(parseSearchResults(result));

    if (isOther) {
      movies.removeIf(m -> Genre.isKnown(m.genre()));
      Comparator<Movie> cmp =
          switch (resolvedSort) {
            case "rating" -> Comparator.comparingDouble(Movie::rating);
            case "releaseYear" -> Comparator.comparingInt(Movie::releaseYear);
            default -> Comparator.comparing(Movie::title, String.CASE_INSENSITIVE_ORDER);
          };
      if (descending) cmp = cmp.reversed();
      movies.sort(cmp);
    }
    return movies;
  }

  /** Cache-aside: check Valkey cache first, fall back to DB on miss. */
  public Movie getById(String catalogId) throws ExecutionException, InterruptedException {
    var fields = client.hgetall(gs(ValkeyKeys.catalogKey(catalogId))).get();
    if (!fields.isEmpty()) {
      return HashParser.toMovie(ValkeyKeys.catalogKey(catalogId), fields);
    }
    // Cache miss — query DB
    try {
      var movie = catalogRepo.findById(catalogId).orElse(null);
      if (movie != null) {
        // Populate cache
        client.hset(gs(ValkeyKeys.catalogKey(catalogId)), HashParser.movieToHash(movie)).get();
      }
      return movie;
    } catch (SQLException e) {
      throw new RuntimeException("DB lookup failed for catalog " + catalogId, e);
    }
  }

  /** Direct DB lookup — bypasses cache. Used for benchmark comparison. */
  public Movie getByIdFromDb(String catalogId) {
    try {
      return catalogRepo.findById(catalogId).orElse(null);
    } catch (SQLException e) {
      throw new RuntimeException("DB lookup failed for catalog " + catalogId, e);
    }
  }

  /** Direct DB text search — bypasses Valkey. Used for benchmark comparison against FT.SEARCH. */
  public List<Movie> searchFromDb(String prefix, int limit) {
    try {
      return catalogRepo.searchByTitle(prefix, limit);
    } catch (SQLException e) {
      throw new RuntimeException("DB search failed", e);
    }
  }

  /** FT.SEARCH title-only prefix — equivalent scope to DB ILIKE for fair benchmarking. */
  public List<Movie> searchViaFts(String prefix, int limit)
      throws ExecutionException, InterruptedException {
    var query = "@title:" + escapeQuery(prefix).trim() + "*";
    return executeSearch(query, limit, null, null);
  }

  /** Direct DB write — bypasses cache. Matches DB work of updateRating (1 DB write). */
  public void updateRatingInDbOnly(String catalogId, double rating) {
    try {
      catalogRepo.updateRating(catalogId, rating);
    } catch (SQLException e) {
      throw new RuntimeException("DB update failed", e);
    }
  }

  public void updateDuration(String catalogId, double durationMinutes)
      throws ExecutionException, InterruptedException {
    dbWriteThenCache(
        () -> catalogRepo.updateDuration(catalogId, durationMinutes),
        catalogId,
        "durationMinutes",
        String.valueOf(durationMinutes));
  }

  public void updateRating(String catalogId, double rating)
      throws ExecutionException, InterruptedException {
    dbWriteThenCache(
        () -> catalogRepo.updateRating(catalogId, rating),
        catalogId,
        "rating",
        String.valueOf(rating));
  }

  public void updateMetadata(
      String catalogId,
      String title,
      String genre,
      String description,
      String tags,
      int releaseYear)
      throws ExecutionException, InterruptedException {
    try {
      catalogRepo.updateMetadata(catalogId, title, genre, description, tags, releaseYear);
    } catch (SQLException e) {
      throw new RuntimeException("DB update failed", e);
    }
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
    dbWriteThenCache(
        () -> catalogRepo.updateThumbnail(catalogId, thumbnailPath),
        catalogId,
        "thumbnailPath",
        thumbnailPath);
  }

  private void setField(String catalogId, String field, String value)
      throws ExecutionException, InterruptedException {
    client.hset(gs(ValkeyKeys.catalogKey(catalogId)), Map.of(gs(field), gs(value))).get();
  }

  /** Writes to DB (source of truth) then updates the single cache field. */
  private void dbWriteThenCache(SqlAction dbWrite, String catalogId, String field, String value)
      throws ExecutionException, InterruptedException {
    try {
      dbWrite.execute();
    } catch (SQLException e) {
      throw new RuntimeException("DB update failed", e);
    }
    setField(catalogId, field, value);
  }

  @FunctionalInterface
  private interface SqlAction {
    void execute() throws SQLException;
  }

  public void deleteVideo(String catalogId) throws ExecutionException, InterruptedException {
    // Read file paths from cache BEFORE deleting anything
    var fields = client.hgetall(gs(ValkeyKeys.catalogKey(catalogId))).get();
    // Delete from DB (source of truth)
    try {
      catalogRepo.delete(catalogId);
    } catch (SQLException e) {
      throw new RuntimeException("DB delete failed", e);
    }
    // Delete from cache
    client.del(new GlideString[] {gs(ValkeyKeys.catalogKey(catalogId))}).get();
    // Delete local files
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
