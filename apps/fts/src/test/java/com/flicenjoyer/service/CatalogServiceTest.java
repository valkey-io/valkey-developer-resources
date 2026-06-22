package com.flicenjoyer.service;

import static glide.api.models.GlideString.gs;
import static org.junit.jupiter.api.Assertions.*;

import com.flicenjoyer.model.Movie;
import glide.api.models.GlideString;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;

class CatalogServiceTest {

  @Test
  void parseSearchResultsExtractsMovies() {
    Map<GlideString, GlideString> fields = new LinkedHashMap<>();
    fields.put(gs("title"), gs("Inception"));
    fields.put(gs("genre"), gs("Sci-Fi"));
    fields.put(gs("description"), gs("A dream heist"));
    fields.put(gs("tags"), gs("dreams,heist"));
    fields.put(gs("releaseYear"), gs("2010"));
    fields.put(gs("rating"), gs("8.8"));
    fields.put(gs("durationMinutes"), gs("148"));
    fields.put(gs("videoPath"), gs("/media/videos/1.mp4"));
    fields.put(gs("thumbnailPath"), gs("/media/thumbnails/1.jpg"));

    Map<GlideString, Map<GlideString, GlideString>> docs = new LinkedHashMap<>();
    docs.put(gs("catalog:1"), fields);

    Object[] result = new Object[] {1L, docs};
    List<Movie> movies = CatalogService.parseSearchResults(result);

    assertEquals(1, movies.size());
    Movie m = movies.getFirst();
    assertEquals("1", m.id());
    assertEquals("Inception", m.title());
    assertEquals("Sci-Fi", m.genre());
    assertEquals(2010, m.releaseYear());
    assertEquals(8.8, m.rating(), 0.01);
    assertEquals(148.0, m.durationMinutes(), 0.01);
    assertEquals("/media/videos/1.mp4", m.videoPath());
    assertEquals("/media/thumbnails/1.jpg", m.thumbnailPath());
  }

  @Test
  void parseSearchResultsHandlesEmptyResult() {
    Object[] result = new Object[] {0L};
    List<Movie> movies = CatalogService.parseSearchResults(result);
    assertTrue(movies.isEmpty());
  }

  @Test
  void parseSearchResultsHandlesMultipleDocuments() {
    Map<GlideString, Map<GlideString, GlideString>> docs = new LinkedHashMap<>();

    Map<GlideString, GlideString> f1 = new LinkedHashMap<>();
    f1.put(gs("title"), gs("Movie A"));
    f1.put(gs("genre"), gs("Action"));
    f1.put(gs("description"), gs("Desc A"));
    f1.put(gs("tags"), gs("tag1"));
    f1.put(gs("releaseYear"), gs("2020"));
    f1.put(gs("rating"), gs("7.5"));
    f1.put(gs("durationMinutes"), gs("120"));
    f1.put(gs("videoPath"), gs("/a.mp4"));
    f1.put(gs("thumbnailPath"), gs(""));
    docs.put(gs("catalog:10"), f1);

    Map<GlideString, GlideString> f2 = new LinkedHashMap<>();
    f2.put(gs("title"), gs("Movie B"));
    f2.put(gs("genre"), gs("Comedy"));
    f2.put(gs("description"), gs("Desc B"));
    f2.put(gs("tags"), gs("tag2"));
    f2.put(gs("releaseYear"), gs("2021"));
    f2.put(gs("rating"), gs("6.0"));
    f2.put(gs("durationMinutes"), gs("90"));
    f2.put(gs("videoPath"), gs("/b.mp4"));
    f2.put(gs("thumbnailPath"), gs("/b.jpg"));
    docs.put(gs("catalog:11"), f2);

    Object[] result = new Object[] {2L, docs};
    List<Movie> movies = CatalogService.parseSearchResults(result);

    assertEquals(2, movies.size());
    assertEquals("Movie A", movies.getFirst().title());
    assertEquals("Movie B", movies.get(1).title());
  }

  @Test
  void parseSearchResultsHandlesMissingPaths() {
    Map<GlideString, GlideString> fields = new LinkedHashMap<>();
    fields.put(gs("title"), gs("No Paths"));
    fields.put(gs("genre"), gs("Drama"));
    fields.put(gs("description"), gs(""));
    fields.put(gs("tags"), gs(""));
    fields.put(gs("releaseYear"), gs("2025"));
    fields.put(gs("rating"), gs("0"));
    fields.put(gs("durationMinutes"), gs("90"));

    Map<GlideString, Map<GlideString, GlideString>> docs = new LinkedHashMap<>();
    docs.put(gs("catalog:99"), fields);

    Object[] result = new Object[] {1L, docs};
    List<Movie> movies = CatalogService.parseSearchResults(result);

    assertEquals(1, movies.size());
    assertEquals("", movies.getFirst().videoPath());
    assertEquals("", movies.getFirst().thumbnailPath());
  }

  @Test
  void escapeQueryEscapesSpecialCharacters() {
    assertEquals("hello", CatalogService.escapeQuery("hello"));
    assertEquals("hello world", CatalogService.escapeQuery("hello-world"));
    assertEquals("test\\.query", CatalogService.escapeQuery("test.query"));
    assertEquals("Sci Fi", CatalogService.escapeQuery("Sci-Fi"));
  }

  @Test
  void escapeTagEscapesSpecialCharacters() {
    assertEquals("Sci\\-Fi", CatalogService.escapeTag("Sci-Fi"));
    assertEquals("Action", CatalogService.escapeTag("Action"));
  }

  // Adversarial query escaping tests (§18)

  @Test
  void escapeQueryBlocksQueryOperatorInjection() {
    // Pipe operator — could inject OR clauses
    assertEquals("action \\| horror", CatalogService.escapeQuery("action | horror"));
    // Negation operator — hyphen replaced with space by escapeQuery
    assertEquals(" excluded", CatalogService.escapeQuery("-excluded"));
    // Parentheses — could alter grouping
    assertEquals("\\(injected\\)", CatalogService.escapeQuery("(injected)"));
    // Curly braces — TAG filter syntax
    assertEquals("\\{tag\\}", CatalogService.escapeQuery("{tag}"));
    // At sign — field prefix
    assertEquals("\\@title", CatalogService.escapeQuery("@title"));
    // Asterisk — wildcard
    assertEquals("\\*", CatalogService.escapeQuery("*"));
    // Percent — fuzzy marker
    assertEquals("\\%\\%term\\%\\%", CatalogService.escapeQuery("%%term%%"));
    // Tilde — optional
    assertEquals("\\~optional", CatalogService.escapeQuery("~optional"));
  }

  @Test
  void escapeTagBlocksTagInjection() {
    // Comma — TAG field separator
    assertEquals("genre1\\,genre2", CatalogService.escapeTag("genre1,genre2"));
    // Pipe in tag
    assertEquals("a \\| b", CatalogService.escapeTag("a | b"));
    // Curly braces
    assertEquals("\\{injected\\}", CatalogService.escapeTag("{injected}"));
    // Backslash — escape character itself
    assertEquals("back\\\\slash", CatalogService.escapeTag("back\\slash"));
  }

  @Test
  void escapeQueryHandlesEmptyAndWhitespace() {
    assertEquals("", CatalogService.escapeQuery(""));
    assertEquals("   ", CatalogService.escapeQuery("   "));
  }

  @Test
  void escapeQueryEscapesUnicodeCharacters() {
    // Non-ASCII characters get escaped for safety
    assertEquals("caf\\é", CatalogService.escapeQuery("café"));
  }

  @Test
  void escapeQueryBlocksArrowInjection() {
    // => is the FT.SEARCH filter-to-KNN delimiter — must be neutralized
    assertEquals("\\=\\>", CatalogService.escapeQuery("=>"));
    assertEquals(
        "\\*\\=\\>\\[KNN 5 \\@embedding \\$vector\\]",
        CatalogService.escapeQuery("*=>[KNN 5 @embedding $vector]"));
  }
}
