package com.flicenjoyer.model;

import java.util.Arrays;
import java.util.Set;
import java.util.stream.Collectors;

/** Known genre constants and validation for catalog entries. */
public enum Genre {
  SCI_FI("sci-fi"),
  ACTION("action"),
  DRAMA("drama"),
  CRIME("crime"),
  THRILLER("thriller"),
  COMEDY("comedy"),
  FANTASY("fantasy"),
  GAMING("gaming"),
  OTHER("other");

  private final String value;

  Genre(String value) {
    this.value = value;
  }

  public String value() {
    return value;
  }

  public String displayName() {
    if (this == SCI_FI) return "Sci-Fi";
    return value.substring(0, 1).toUpperCase() + value.substring(1);
  }

  private static final Set<String> KNOWN =
      Arrays.stream(values())
          .filter(g -> g != OTHER)
          .map(Genre::value)
          .collect(Collectors.toUnmodifiableSet());

  public static boolean isKnown(String genre) {
    return genre != null && KNOWN.contains(genre.toLowerCase());
  }

  public static String[] displayNames() {
    return Arrays.stream(values()).map(Genre::displayName).toArray(String[]::new);
  }

  public static String[] displayNamesWithAll() {
    var names = new String[values().length + 1];
    names[0] = "All";
    var vals = values();
    for (int i = 0; i < vals.length; i++) {
      names[i + 1] = vals[i].displayName();
    }
    return names;
  }
}
