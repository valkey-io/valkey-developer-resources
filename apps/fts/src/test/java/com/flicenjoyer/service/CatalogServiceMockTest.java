package com.flicenjoyer.service;

import static glide.api.models.GlideString.gs;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.*;

import com.flicenjoyer.db.CatalogRepository;
import glide.api.BaseClient;
import glide.api.GlideClient;
import glide.api.commands.servermodules.FT;
import glide.api.models.GlideString;
import glide.api.models.commands.FT.FTSearchOptions;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.concurrent.CompletableFuture;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.MockedStatic;
import org.mockito.junit.jupiter.MockitoExtension;

@ExtendWith(MockitoExtension.class)
class CatalogServiceMockTest {

  @Mock GlideClient client;
  @Mock CatalogRepository catalogRepo;
  CatalogService service;

  @BeforeEach
  void setUp() {
    service = new CatalogService(client, catalogRepo);
  }

  @Test
  void getByIdReturnsMovie() throws Exception {
    Map<GlideString, GlideString> fields = new LinkedHashMap<>();
    fields.put(gs("title"), gs("Test Movie"));
    fields.put(gs("genre"), gs("Action"));
    fields.put(gs("description"), gs("Desc"));
    fields.put(gs("tags"), gs("tag1"));
    fields.put(gs("releaseYear"), gs("2025"));
    fields.put(gs("rating"), gs("8.5"));
    fields.put(gs("durationMinutes"), gs("120"));
    fields.put(gs("videoPath"), gs("/v.mp4"));
    fields.put(gs("thumbnailPath"), gs("/t.jpg"));

    when(client.hgetall(any(GlideString.class)))
        .thenReturn(CompletableFuture.completedFuture(fields));

    var movie = service.getById("abc");
    assertNotNull(movie);
    assertEquals("Test Movie", movie.title());
    assertEquals("Action", movie.genre());
    assertEquals(8.5, movie.rating(), 0.01);
  }

  @Test
  void getByIdReturnsNullWhenEmpty() throws Exception {
    when(client.hgetall(any(GlideString.class)))
        .thenReturn(CompletableFuture.completedFuture(Map.of()));
    when(catalogRepo.findById("missing")).thenReturn(java.util.Optional.empty());

    assertNull(service.getById("missing"));
  }

  @Test
  void updateDurationCallsHset() throws Exception {
    when(client.hset(any(GlideString.class), any()))
        .thenReturn(CompletableFuture.completedFuture(1L));

    service.updateDuration("abc", 90.5);
    verify(client).hset(any(GlideString.class), any());
    verify(catalogRepo).updateDuration("abc", 90.5);
  }

  @Test
  void updateRatingCallsHset() throws Exception {
    when(client.hset(any(GlideString.class), any()))
        .thenReturn(CompletableFuture.completedFuture(1L));

    service.updateRating("abc", 4.0);
    verify(client).hset(any(GlideString.class), any());
  }

  @Test
  void updateMetadataCallsHset() throws Exception {
    when(client.hset(any(GlideString.class), any()))
        .thenReturn(CompletableFuture.completedFuture(5L));

    service.updateMetadata("abc", "New Title", "Drama", "New desc", "t1,t2", 2024);
    verify(client).hset(any(GlideString.class), any());
  }

  @Test
  void updateThumbnailCallsHset() throws Exception {
    when(client.hset(any(GlideString.class), any()))
        .thenReturn(CompletableFuture.completedFuture(1L));

    service.updateThumbnail("abc", "/new/thumb.jpg");
    verify(client).hset(any(GlideString.class), any());
  }

  private Object[] emptySearchResult() {
    return new Object[] {0L};
  }

  private Object[] singleMovieResult(String title) {
    Map<GlideString, GlideString> fields = new LinkedHashMap<>();
    fields.put(gs("title"), gs(title));
    fields.put(gs("genre"), gs("Action"));
    fields.put(gs("description"), gs(""));
    fields.put(gs("tags"), gs(""));
    fields.put(gs("releaseYear"), gs("2020"));
    fields.put(gs("rating"), gs("7"));
    fields.put(gs("durationMinutes"), gs("90"));
    fields.put(gs("videoPath"), gs(""));
    fields.put(gs("thumbnailPath"), gs(""));
    Map<GlideString, Map<GlideString, GlideString>> docs = new LinkedHashMap<>();
    docs.put(gs("catalog:1"), fields);
    return new Object[] {1L, docs};
  }

  @Test
  void searchPrefixBuildsCorrectQuery() throws Exception {
    var queryCaptor = ArgumentCaptor.forClass(String.class);

    try (MockedStatic<FT> ft = mockStatic(FT.class)) {
      ft.when(
              () ->
                  FT.search(
                      any(BaseClient.class),
                      any(String.class),
                      any(String.class),
                      any(FTSearchOptions.class)))
          .thenReturn(CompletableFuture.completedFuture(singleMovieResult("Alien")));

      service.searchPrefix("ali", 10);

      ft.verify(
          () ->
              FT.search(
                  any(BaseClient.class),
                  eq("idx:catalog"),
                  queryCaptor.capture(),
                  any(FTSearchOptions.class)));
      var query = queryCaptor.getValue();
      assertTrue(query.contains("ali*"), "Should have prefix wildcard: " + query);
      assertTrue(query.contains("@title:"), "Should search title field: " + query);
    }
  }

  @Test
  void searchFuzzyBuildsCorrectQuery() throws Exception {
    var queryCaptor = ArgumentCaptor.forClass(String.class);

    try (MockedStatic<FT> ft = mockStatic(FT.class)) {
      ft.when(
              () ->
                  FT.search(
                      any(BaseClient.class),
                      any(String.class),
                      any(String.class),
                      any(FTSearchOptions.class)))
          .thenReturn(CompletableFuture.completedFuture(singleMovieResult("Alien")));

      service.searchFuzzy("alien", 10);

      ft.verify(
          () ->
              FT.search(
                  any(BaseClient.class),
                  eq("idx:catalog"),
                  queryCaptor.capture(),
                  any(FTSearchOptions.class)));
      var query = queryCaptor.getValue();
      assertTrue(query.contains("%%alien%%"), "Should have fuzzy markers: " + query);
    }
  }

  @Test
  void browseByGenreBuildsTagQuery() throws Exception {
    try (MockedStatic<FT> ft = mockStatic(FT.class)) {
      ft.when(
              () ->
                  FT.search(
                      any(BaseClient.class),
                      any(String.class),
                      any(String.class),
                      any(FTSearchOptions.class)))
          .thenReturn(CompletableFuture.completedFuture(emptySearchResult()));

      service.browseByGenre("Sci-Fi", "title", FTSearchOptions.SortOrder.ASC, 20);

      ft.verify(
          () ->
              FT.search(
                  any(BaseClient.class),
                  eq("idx:catalog"),
                  eq("@genre:{Sci\\-Fi}"),
                  any(FTSearchOptions.class)));
    }
  }

  @Test
  void searchPrefixReturnsMovies() throws Exception {
    try (MockedStatic<FT> ft = mockStatic(FT.class)) {
      ft.when(
              () ->
                  FT.search(
                      any(BaseClient.class),
                      any(String.class),
                      any(String.class),
                      any(FTSearchOptions.class)))
          .thenReturn(CompletableFuture.completedFuture(singleMovieResult("Inception")));

      var movies = service.searchPrefix("incep", 10);
      assertEquals(1, movies.size());
      assertEquals("Inception", movies.getFirst().title());
    }
  }

  @Test
  void browseAllReturnsMovies() throws Exception {
    Map<GlideString, GlideString> fields = new LinkedHashMap<>();
    fields.put(gs("title"), gs("Movie A"));
    fields.put(gs("genre"), gs("Action"));
    fields.put(gs("description"), gs(""));
    fields.put(gs("tags"), gs(""));
    fields.put(gs("releaseYear"), gs("2020"));
    fields.put(gs("rating"), gs("7"));
    fields.put(gs("durationMinutes"), gs("90"));
    fields.put(gs("videoPath"), gs(""));
    fields.put(gs("thumbnailPath"), gs(""));

    Map<GlideString, Map<GlideString, GlideString>> docs = new LinkedHashMap<>();
    docs.put(gs("catalog:1"), fields);
    Object[] searchResult = new Object[] {1L, docs};

    try (MockedStatic<FT> ft = mockStatic(FT.class)) {
      ft.when(
              () ->
                  FT.search(
                      any(BaseClient.class),
                      any(String.class),
                      any(String.class),
                      any(FTSearchOptions.class)))
          .thenReturn(CompletableFuture.completedFuture(searchResult));

      var movies = service.browseAll(null, "title", false);
      assertEquals(1, movies.size());
      assertEquals("Movie A", movies.getFirst().title());
    }
  }

  @Test
  void browseAllNullFilterUsesRangeQuery() throws Exception {
    Object[] searchResult = new Object[] {0L};

    try (MockedStatic<FT> ft = mockStatic(FT.class)) {
      ft.when(
              () ->
                  FT.search(
                      any(BaseClient.class),
                      any(String.class),
                      any(String.class),
                      any(FTSearchOptions.class)))
          .thenReturn(CompletableFuture.completedFuture(searchResult));

      service.browseAll(null, "title", false);

      ft.verify(
          () ->
              FT.search(
                  any(BaseClient.class),
                  eq("idx:catalog"),
                  eq("@releaseYear:[0 inf]"),
                  any(FTSearchOptions.class)));
    }
  }

  @Test
  void browseAllAllFilterUsesRangeQuery() throws Exception {
    Object[] searchResult = new Object[] {0L};

    try (MockedStatic<FT> ft = mockStatic(FT.class)) {
      ft.when(
              () ->
                  FT.search(
                      any(BaseClient.class),
                      any(String.class),
                      any(String.class),
                      any(FTSearchOptions.class)))
          .thenReturn(CompletableFuture.completedFuture(searchResult));

      service.browseAll("All", "title", false);

      ft.verify(
          () ->
              FT.search(
                  any(BaseClient.class),
                  eq("idx:catalog"),
                  eq("@releaseYear:[0 inf]"),
                  any(FTSearchOptions.class)));
    }
  }

  @Test
  void browseAllGenreFilterUsesTagQuery() throws Exception {
    Object[] searchResult = new Object[] {0L};

    try (MockedStatic<FT> ft = mockStatic(FT.class)) {
      ft.when(
              () ->
                  FT.search(
                      any(BaseClient.class),
                      any(String.class),
                      any(String.class),
                      any(FTSearchOptions.class)))
          .thenReturn(CompletableFuture.completedFuture(searchResult));

      service.browseAll("Action", "title", false);

      ft.verify(
          () ->
              FT.search(
                  any(BaseClient.class),
                  eq("idx:catalog"),
                  eq("@genre:{Action}"),
                  any(FTSearchOptions.class)));
    }
  }

  @Test
  void browseAllFiltersGenre() throws Exception {
    Map<GlideString, GlideString> action = new LinkedHashMap<>();
    action.put(gs("title"), gs("Action Movie"));
    action.put(gs("genre"), gs("Action"));
    action.put(gs("description"), gs(""));
    action.put(gs("tags"), gs(""));
    action.put(gs("releaseYear"), gs("2020"));
    action.put(gs("rating"), gs("7"));
    action.put(gs("durationMinutes"), gs("90"));
    action.put(gs("videoPath"), gs(""));
    action.put(gs("thumbnailPath"), gs(""));

    Map<GlideString, Map<GlideString, GlideString>> docs = new LinkedHashMap<>();
    docs.put(gs("catalog:1"), action);
    Object[] searchResult = new Object[] {1L, docs};

    try (MockedStatic<FT> ft = mockStatic(FT.class)) {
      ft.when(
              () ->
                  FT.search(
                      any(BaseClient.class),
                      any(String.class),
                      any(String.class),
                      any(FTSearchOptions.class)))
          .thenReturn(CompletableFuture.completedFuture(searchResult));

      var movies = service.browseAll("Action", "title", false);
      assertEquals(1, movies.size());
      assertEquals("Action Movie", movies.getFirst().title());
    }
  }

  @Test
  void browseAllOtherFilterUsesRangeQuery() throws Exception {
    Object[] searchResult = new Object[] {0L};

    try (MockedStatic<FT> ft = mockStatic(FT.class)) {
      ft.when(
              () ->
                  FT.search(
                      any(BaseClient.class),
                      any(String.class),
                      any(String.class),
                      any(FTSearchOptions.class)))
          .thenReturn(CompletableFuture.completedFuture(searchResult));

      service.browseAll("Other", "title", false);

      ft.verify(
          () ->
              FT.search(
                  any(BaseClient.class),
                  eq("idx:catalog"),
                  eq("@releaseYear:[0 inf]"),
                  any(FTSearchOptions.class)));
    }
  }

  @Test
  void browseAllOtherFilterExcludesKnownGenres() throws Exception {
    Map<GlideString, GlideString> fields = new LinkedHashMap<>();
    fields.put(gs("title"), gs("Weird Movie"));
    fields.put(gs("genre"), gs("Action"));
    fields.put(gs("description"), gs(""));
    fields.put(gs("tags"), gs(""));
    fields.put(gs("releaseYear"), gs("2020"));
    fields.put(gs("rating"), gs("5"));
    fields.put(gs("durationMinutes"), gs("80"));
    fields.put(gs("videoPath"), gs(""));
    fields.put(gs("thumbnailPath"), gs(""));

    Map<GlideString, Map<GlideString, GlideString>> docs = new LinkedHashMap<>();
    docs.put(gs("catalog:1"), fields);
    Object[] searchResult = new Object[] {1L, docs};

    try (MockedStatic<FT> ft = mockStatic(FT.class)) {
      ft.when(
              () ->
                  FT.search(
                      any(BaseClient.class),
                      any(String.class),
                      any(String.class),
                      any(FTSearchOptions.class)))
          .thenReturn(CompletableFuture.completedFuture(searchResult));

      var movies = service.browseAll("Other", "title", false);
      assertEquals(0, movies.size()); // Action is a known genre, excluded by "Other"
    }
  }
}
