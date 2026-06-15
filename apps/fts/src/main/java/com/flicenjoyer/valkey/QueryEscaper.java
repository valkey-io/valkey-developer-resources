package com.flicenjoyer.valkey;

/** Shared query escaping utilities for ValkeySearch FTS queries. */
public final class QueryEscaper {
  private QueryEscaper() {}

  public static String escapeTag(String input) {
    return input.replaceAll("[^a-zA-Z0-9 ]", "\\\\$0");
  }

  public static String escapeQuery(String input) {
    return input.replace('-', ' ').replaceAll("[^a-zA-Z0-9 ]", "\\\\$0");
  }
}
