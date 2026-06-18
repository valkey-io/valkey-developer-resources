package com.flicenjoyer.valkey;

import static org.junit.jupiter.api.Assertions.*;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class AppConfigTest {

  @TempDir Path tempDir;

  @Test
  void loadReturnsDefaultsWhenFileAbsent() {
    var config = AppConfig.load(tempDir.resolve("nonexistent.yaml"));
    assertEquals("localhost", config.valkeyHost());
    assertEquals(6379, config.valkeyPort());
  }

  @Test
  void loadParsesCustomValues() throws IOException {
    var file = tempDir.resolve("config.yaml");
    Files.writeString(file, "valkey:\n  host: 172.17.0.3\n  port: 6380\n");
    var config = AppConfig.load(file);
    assertEquals("172.17.0.3", config.valkeyHost());
    assertEquals(6380, config.valkeyPort());
  }

  @Test
  void loadHandlesPartialConfig() throws IOException {
    var file = tempDir.resolve("config.yaml");
    Files.writeString(file, "valkey:\n  host: myhost\n");
    var config = AppConfig.load(file);
    assertEquals("myhost", config.valkeyHost());
    assertEquals(6379, config.valkeyPort());
  }

  @Test
  void loadHandlesEmptyFile() throws IOException {
    var file = tempDir.resolve("config.yaml");
    Files.writeString(file, "");
    var config = AppConfig.load(file);
    assertEquals("localhost", config.valkeyHost());
    assertEquals(6379, config.valkeyPort());
  }
}
