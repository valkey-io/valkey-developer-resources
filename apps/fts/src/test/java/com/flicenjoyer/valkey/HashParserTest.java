package com.flicenjoyer.valkey;

import static glide.api.models.GlideString.gs;
import static org.junit.jupiter.api.Assertions.*;

import glide.api.models.GlideString;
import java.util.LinkedHashMap;
import java.util.Map;
import org.junit.jupiter.api.Test;

class HashParserTest {

  @Test
  void strReturnsValue() {
    Map<GlideString, GlideString> f = Map.of(gs("name"), gs("hello"));
    assertEquals("hello", HashParser.str(f, "name"));
  }

  @Test
  void strReturnsEmptyForMissing() {
    assertEquals("", HashParser.str(Map.of(), "missing"));
  }

  @Test
  void toIntParsesValue() {
    Map<GlideString, GlideString> f = Map.of(gs("val"), gs("42"));
    assertEquals(42, HashParser.toInt(f, "val"));
  }

  @Test
  void toIntReturnsZeroForEmpty() {
    assertEquals(0, HashParser.toInt(Map.of(), "val"));
  }

  @Test
  void toDoubleParsesValue() {
    Map<GlideString, GlideString> f = Map.of(gs("val"), gs("3.14"));
    assertEquals(3.14, HashParser.toDouble(f, "val"), 0.001);
  }

  @Test
  void toLongParsesValue() {
    Map<GlideString, GlideString> f = Map.of(gs("val"), gs("9999999"));
    assertEquals(9999999L, HashParser.toLong(f, "val"));
  }

  @Test
  void toMovieExtractsAllFields() {
    var f = new LinkedHashMap<GlideString, GlideString>();
    f.put(gs("title"), gs("Test"));
    f.put(gs("genre"), gs("Action"));
    f.put(gs("description"), gs("Desc"));
    f.put(gs("tags"), gs("t1,t2"));
    f.put(gs("releaseYear"), gs("2025"));
    f.put(gs("rating"), gs("8.5"));
    f.put(gs("durationMinutes"), gs("120.5"));
    f.put(gs("videoPath"), gs("/v.mp4"));
    f.put(gs("thumbnailPath"), gs("/t.jpg"));

    var movie = HashParser.toMovie("catalog:abc", f);
    assertEquals("abc", movie.id());
    assertEquals("Test", movie.title());
    assertEquals("Action", movie.genre());
    assertEquals(2025, movie.releaseYear());
    assertEquals(8.5, movie.rating(), 0.01);
    assertEquals(120.5, movie.durationMinutes(), 0.01);
    assertEquals("/v.mp4", movie.videoPath());
  }

  @Test
  void toMovieStripsPrefix() {
    var movie = HashParser.toMovie("catalog:xyz", Map.of());
    assertEquals("xyz", movie.id());
  }

  @Test
  void toMovieKeysKeyWithoutPrefix() {
    var movie = HashParser.toMovie("plain-id", Map.of());
    assertEquals("plain-id", movie.id());
  }

  @Test
  void toWatchEntryExtractsFields() {
    var f = new LinkedHashMap<GlideString, GlideString>();
    f.put(gs("userId"), gs("u1"));
    f.put(gs("catalogId"), gs("v1"));
    f.put(gs("title"), gs("Movie"));
    f.put(gs("resumeTimestamp"), gs("500"));
    f.put(gs("completed"), gs("true"));
    f.put(gs("lastWatched"), gs("12345"));

    var entry = HashParser.toWatchEntry(f);
    assertEquals("u1", entry.userId());
    assertEquals("v1", entry.catalogId());
    assertEquals(500L, entry.resumeTimestamp());
    assertTrue(entry.completed());
    assertEquals(12345L, entry.lastWatched());
  }
}
