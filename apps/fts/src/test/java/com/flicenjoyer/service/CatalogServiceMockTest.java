package com.flicenjoyer.service;

import static glide.api.models.GlideString.gs;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

import glide.api.GlideClient;
import glide.api.models.GlideString;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.concurrent.CompletableFuture;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

@ExtendWith(MockitoExtension.class)
class CatalogServiceMockTest {

  @Mock GlideClient client;
  CatalogService service;

  @BeforeEach
  void setUp() {
    service = new CatalogService(client);
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

    assertNull(service.getById("missing"));
  }

  @Test
  void updateDurationCallsHset() throws Exception {
    when(client.hset(any(GlideString.class), any()))
        .thenReturn(CompletableFuture.completedFuture(1L));

    service.updateDuration("abc", 90.5);
    verify(client).hset(any(GlideString.class), any());
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

  @Test
  void browseAllReturnsMovies() throws Exception {
    when(client.keys(any(GlideString.class)))
        .thenReturn(CompletableFuture.completedFuture(new GlideString[] {gs("catalog:1")}));

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

    when(client.hgetall(any(GlideString.class)))
        .thenReturn(CompletableFuture.completedFuture(fields));

    var movies = service.browseAll(null, "title", false);
    assertEquals(1, movies.size());
    assertEquals("Movie A", movies.getFirst().title());
  }

  @Test
  void browseAllFiltersGenre() throws Exception {
    when(client.keys(any(GlideString.class)))
        .thenReturn(
            CompletableFuture.completedFuture(
                new GlideString[] {gs("catalog:1"), gs("catalog:2")}));

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

    Map<GlideString, GlideString> scifi = new LinkedHashMap<>();
    scifi.put(gs("title"), gs("Sci-Fi Movie"));
    scifi.put(gs("genre"), gs("Sci-Fi"));
    scifi.put(gs("description"), gs(""));
    scifi.put(gs("tags"), gs(""));
    scifi.put(gs("releaseYear"), gs("2021"));
    scifi.put(gs("rating"), gs("8"));
    scifi.put(gs("durationMinutes"), gs("120"));
    scifi.put(gs("videoPath"), gs(""));
    scifi.put(gs("thumbnailPath"), gs(""));

    when(client.hgetall(gs("catalog:1"))).thenReturn(CompletableFuture.completedFuture(action));
    when(client.hgetall(gs("catalog:2"))).thenReturn(CompletableFuture.completedFuture(scifi));

    var movies = service.browseAll("Action", "title", false);
    assertEquals(1, movies.size());
    assertEquals("Action Movie", movies.getFirst().title());
  }

  @Test
  void browseAllOtherFilterExcludesKnownGenres() throws Exception {
    when(client.keys(any(GlideString.class)))
        .thenReturn(CompletableFuture.completedFuture(new GlideString[] {gs("catalog:1")}));

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

    when(client.hgetall(any(GlideString.class)))
        .thenReturn(CompletableFuture.completedFuture(fields));

    var movies = service.browseAll("Other", "title", false);
    assertEquals(0, movies.size()); // Action is a known genre, excluded by "Other"
  }
}
