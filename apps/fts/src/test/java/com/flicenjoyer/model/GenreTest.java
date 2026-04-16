package com.flicenjoyer.model;

import static org.junit.jupiter.api.Assertions.*;

import org.junit.jupiter.api.Test;

class GenreTest {

  @Test
  void valueReturnsLowercase() {
    assertEquals("sci-fi", Genre.SCI_FI.value());
    assertEquals("action", Genre.ACTION.value());
    assertEquals("other", Genre.OTHER.value());
  }

  @Test
  void displayNameCapitalizes() {
    assertEquals("Sci-Fi", Genre.SCI_FI.displayName());
    assertEquals("Action", Genre.ACTION.displayName());
    assertEquals("Gaming", Genre.GAMING.displayName());
    assertEquals("Other", Genre.OTHER.displayName());
  }

  @Test
  void isKnownReturnsTrueForKnownGenres() {
    assertTrue(Genre.isKnown("action"));
    assertTrue(Genre.isKnown("sci-fi"));
    assertTrue(Genre.isKnown("gaming"));
  }

  @Test
  void isKnownReturnsFalseForUnknown() {
    assertFalse(Genre.isKnown("documentary"));
    assertFalse(Genre.isKnown("other"));
  }

  @Test
  void isKnownIsCaseInsensitive() {
    assertTrue(Genre.isKnown("ACTION"));
    assertTrue(Genre.isKnown("Sci-Fi"));
  }

  @Test
  void displayNamesReturnsAllGenres() {
    var names = Genre.displayNames();
    assertEquals(Genre.values().length, names.length);
    assertEquals("Sci-Fi", names[0]);
  }

  @Test
  void displayNamesWithAllIncludesAll() {
    var names = Genre.displayNamesWithAll();
    assertEquals(Genre.values().length + 1, names.length);
    assertEquals("All", names[0]);
    assertEquals("Sci-Fi", names[1]);
  }
}
