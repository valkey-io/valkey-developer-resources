package com.flicenjoyer.valkey;

/** Centralized Valkey key prefixes and index names. */
public final class ValkeyKeys {
  private ValkeyKeys() {}

  public static final String CATALOG_PREFIX = "catalog:";
  public static final String WATCH_PREFIX = "watch:";
  public static final String CATALOG_INDEX = "idx:catalog";
  public static final String WATCH_INDEX = "idx:watch";

  public static String catalogKey(String id) {
    return CATALOG_PREFIX + id;
  }

  public static String watchKey(String userId, String catalogId) {
    return WATCH_PREFIX + userId + ":" + catalogId;
  }
}
