package com.flicenjoyer.db;

import com.flicenjoyer.valkey.AppConfig;
import com.zaxxer.hikari.HikariConfig;
import com.zaxxer.hikari.HikariDataSource;
import java.io.IOException;
import java.sql.SQLException;
import java.util.logging.Logger;
import javax.sql.DataSource;

/** Manages HikariCP connection pool and runs schema.sql on init. */
public final class DatabaseProvider {

  private static final Logger LOG = Logger.getLogger(DatabaseProvider.class.getName());
  private final HikariDataSource dataSource;

  public DatabaseProvider(AppConfig config) {
    var hikari = new HikariConfig();
    hikari.setJdbcUrl(
        "jdbc:postgresql://" + config.dbHost() + ":" + config.dbPort() + "/" + config.dbName());
    hikari.setUsername(config.dbUser());
    hikari.setPassword(config.dbPassword());
    hikari.setMaximumPoolSize(5);
    hikari.setConnectionTimeout(5000);
    this.dataSource = new HikariDataSource(hikari);
    runSchema();
  }

  public DataSource getDataSource() {
    return dataSource;
  }

  public void close() {
    dataSource.close();
  }

  private void runSchema() {
    try (var is = getClass().getResourceAsStream("/schema.sql")) {
      if (is == null) {
        LOG.warning("schema.sql not found on classpath");
        return;
      }
      var sql = new String(is.readAllBytes());
      try (var conn = dataSource.getConnection();
          var stmt = conn.createStatement()) {
        stmt.execute(sql);
        LOG.info("Database schema applied");
      }
    } catch (IOException | SQLException e) {
      throw new RuntimeException("Failed to apply database schema", e);
    }
  }
}
