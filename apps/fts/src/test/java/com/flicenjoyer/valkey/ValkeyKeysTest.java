package com.flicenjoyer.valkey;

import static org.junit.jupiter.api.Assertions.*;

import org.junit.jupiter.api.Test;

class ValkeyKeysTest {

  @Test
  void catalogKeyPrefixes() {
    assertEquals("catalog:abc", ValkeyKeys.catalogKey("abc"));
  }

  @Test
  void watchKeyFormatsCorrectly() {
    assertEquals("watch:u1:v1", ValkeyKeys.watchKey("u1", "v1"));
  }

  @Test
  void constantsAreCorrect() {
    assertEquals("catalog:", ValkeyKeys.CATALOG_PREFIX);
    assertEquals("watch:", ValkeyKeys.WATCH_PREFIX);
    assertEquals("idx:catalog", ValkeyKeys.CATALOG_INDEX);
    assertEquals("idx:watch", ValkeyKeys.WATCH_INDEX);
  }
}
