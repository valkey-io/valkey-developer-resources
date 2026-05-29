package com.flicenjoyer.valkey;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Map;
import org.yaml.snakeyaml.Yaml;

/** Application configuration loaded from config.yaml (Valkey, database, feature flags). */
public record AppConfig(
    String valkeyHost,
    int valkeyPort,
    String dbHost,
    int dbPort,
    String dbName,
    String dbUser,
    String dbPassword,
    boolean adminEnabled) {

  private static final String DEFAULT_HOST = "localhost";
  private static final int DEFAULT_VALKEY_PORT = 6379;
  private static final int DEFAULT_DB_PORT = 5432;
  private static final String DEFAULT_DB_NAME = "flicenjoyer";
  private static final String DEFAULT_DB_USER = "flicenjoyer";
  private static final String DEFAULT_DB_PASSWORD = "flicenjoyer";

  public static AppConfig load() {
    return load(Path.of("config.yaml"));
  }

  @SuppressWarnings("unchecked")
  public static AppConfig load(Path path) {
    if (!Files.exists(path)) {
      return defaults();
    }
    try {
      var yaml =
          new Yaml(
              new org.yaml.snakeyaml.constructor.SafeConstructor(
                  new org.yaml.snakeyaml.LoaderOptions()));
      Map<String, Object> root = yaml.load(Files.readString(path));
      if (root == null) return defaults();

      var valkey = (Map<String, Object>) root.getOrDefault("valkey", Map.of());
      var valkeyHost = valkey.getOrDefault("host", DEFAULT_HOST).toString();
      var valkeyPort =
          valkey.containsKey("port")
              ? ((Number) valkey.get("port")).intValue()
              : DEFAULT_VALKEY_PORT;

      var db = (Map<String, Object>) root.getOrDefault("database", Map.of());
      var dbHost = db.getOrDefault("host", DEFAULT_HOST).toString();
      var dbPort =
          db.containsKey("port") ? ((Number) db.get("port")).intValue() : DEFAULT_DB_PORT;
      var dbName = db.getOrDefault("name", DEFAULT_DB_NAME).toString();
      var dbUser = db.getOrDefault("user", DEFAULT_DB_USER).toString();
      var dbPassword = db.getOrDefault("password", DEFAULT_DB_PASSWORD).toString();

      var admin = (Map<String, Object>) root.getOrDefault("admin", Map.of());
      var adminEnabled = Boolean.TRUE.equals(admin.get("enabled"));

      return new AppConfig(
          valkeyHost, valkeyPort, dbHost, dbPort, dbName, dbUser, dbPassword, adminEnabled);
    } catch (IOException e) {
      return defaults();
    }
  }

  private static AppConfig defaults() {
    return new AppConfig(
        DEFAULT_HOST,
        DEFAULT_VALKEY_PORT,
        DEFAULT_HOST,
        DEFAULT_DB_PORT,
        DEFAULT_DB_NAME,
        DEFAULT_DB_USER,
        DEFAULT_DB_PASSWORD,
        false);
  }
}
