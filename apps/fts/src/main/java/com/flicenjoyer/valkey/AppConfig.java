package com.flicenjoyer.valkey;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Map;
import org.yaml.snakeyaml.Yaml;

/** Application configuration loaded from config.yaml (Valkey connection, feature flags). */
public record AppConfig(String valkeyHost, int valkeyPort, boolean adminEnabled) {

  private static final String DEFAULT_HOST = "localhost";
  private static final int DEFAULT_PORT = 6379;

  public static AppConfig load() {
    return load(Path.of("config.yaml"));
  }

  @SuppressWarnings("unchecked")
  public static AppConfig load(Path path) {
    if (!Files.exists(path)) {
      return new AppConfig(DEFAULT_HOST, DEFAULT_PORT, false);
    }
    try {
      var yaml =
          new Yaml(
              new org.yaml.snakeyaml.constructor.SafeConstructor(
                  new org.yaml.snakeyaml.LoaderOptions()));
      Map<String, Object> root = yaml.load(Files.readString(path));
      if (root == null) return new AppConfig(DEFAULT_HOST, DEFAULT_PORT, false);

      var valkey = (Map<String, Object>) root.getOrDefault("valkey", Map.of());
      var host = valkey.getOrDefault("host", DEFAULT_HOST).toString();
      var port =
          valkey.containsKey("port") ? ((Number) valkey.get("port")).intValue() : DEFAULT_PORT;

      var admin = (Map<String, Object>) root.getOrDefault("admin", Map.of());
      var adminEnabled = Boolean.TRUE.equals(admin.get("enabled"));

      return new AppConfig(host, port, adminEnabled);
    } catch (IOException e) {
      return new AppConfig(DEFAULT_HOST, DEFAULT_PORT, false);
    }
  }
}
