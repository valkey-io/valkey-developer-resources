package com.flicenjoyer.service;

import static glide.api.models.GlideString.gs;
import static org.junit.jupiter.api.Assertions.*;

import com.flicenjoyer.model.WatchHistoryEntry;
import com.flicenjoyer.valkey.HashParser;
import glide.api.models.GlideString;
import java.util.LinkedHashMap;
import java.util.Map;
import org.junit.jupiter.api.Test;

class WatchHistoryServiceTest {

  @Test
  void toWatchEntryExtractsFields() {
    Map<GlideString, GlideString> fields = new LinkedHashMap<>();
    fields.put(gs("userId"), gs("user-abc"));
    fields.put(gs("catalogId"), gs("42"));
    fields.put(gs("title"), gs("Inception"));
    fields.put(gs("resumeTimestamp"), gs("1834"));
    fields.put(gs("completed"), gs("false"));
    fields.put(gs("lastWatched"), gs("1711800000"));

    WatchHistoryEntry e = HashParser.toWatchEntry(fields);
    assertEquals("user-abc", e.userId());
    assertEquals("42", e.catalogId());
    assertEquals("Inception", e.title());
    assertEquals(1834, e.resumeTimestamp());
    assertFalse(e.completed());
    assertEquals(1711800000L, e.lastWatched());
  }

  @Test
  void toWatchEntryHandlesCompletedEntry() {
    Map<GlideString, GlideString> fields = new LinkedHashMap<>();
    fields.put(gs("userId"), gs("user-xyz"));
    fields.put(gs("catalogId"), gs("7"));
    fields.put(gs("title"), gs("Forrest Gump"));
    fields.put(gs("resumeTimestamp"), gs("8520"));
    fields.put(gs("completed"), gs("true"));
    fields.put(gs("lastWatched"), gs("1711900000"));

    WatchHistoryEntry e = HashParser.toWatchEntry(fields);
    assertTrue(e.completed());
  }

  @Test
  void toWatchEntryHandlesMissingFields() {
    Map<GlideString, GlideString> fields = new LinkedHashMap<>();
    fields.put(gs("userId"), gs("user-abc"));
    fields.put(gs("catalogId"), gs("1"));

    WatchHistoryEntry e = HashParser.toWatchEntry(fields);
    assertEquals("", e.title());
    assertEquals(0, e.resumeTimestamp());
    assertFalse(e.completed());
    assertEquals(0, e.lastWatched());
  }
}
