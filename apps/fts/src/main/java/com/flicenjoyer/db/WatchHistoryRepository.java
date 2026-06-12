package com.flicenjoyer.db;

import com.flicenjoyer.model.WatchHistoryEntry;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;
import javax.sql.DataSource;

/** JDBC repository for the watch_history table. */
public final class WatchHistoryRepository {

  private final DataSource ds;

  public WatchHistoryRepository(DataSource ds) {
    this.ds = ds;
  }

  public void upsert(WatchHistoryEntry entry) throws SQLException {
    var sql =
        "INSERT INTO watch_history (user_id, catalog_id, title, resume_timestamp, completed,"
            + " last_watched) VALUES (?,?,?,?,?,?) ON CONFLICT (user_id, catalog_id) DO UPDATE SET"
            + " title=EXCLUDED.title, resume_timestamp=EXCLUDED.resume_timestamp,"
            + " completed=EXCLUDED.completed, last_watched=EXCLUDED.last_watched";
    try (var conn = ds.getConnection();
        var ps = conn.prepareStatement(sql)) {
      ps.setString(1, entry.userId());
      ps.setString(2, entry.catalogId());
      ps.setString(3, entry.title());
      ps.setLong(4, entry.resumeTimestamp());
      ps.setBoolean(5, entry.completed());
      ps.setLong(6, entry.lastWatched());
      ps.executeUpdate();
    }
  }

  public List<WatchHistoryEntry> findByUserId(String userId) throws SQLException {
    var list = new ArrayList<WatchHistoryEntry>();
    try (var conn = ds.getConnection();
        var ps =
            conn.prepareStatement(
                "SELECT * FROM watch_history WHERE user_id = ? ORDER BY last_watched DESC")) {
      ps.setString(1, userId);
      try (var rs = ps.executeQuery()) {
        while (rs.next()) list.add(mapRow(rs));
      }
    }
    return list;
  }

  public Optional<WatchHistoryEntry> findByUserAndCatalog(String userId, String catalogId)
      throws SQLException {
    try (var conn = ds.getConnection();
        var ps =
            conn.prepareStatement(
                "SELECT * FROM watch_history WHERE user_id = ? AND catalog_id = ?")) {
      ps.setString(1, userId);
      ps.setString(2, catalogId);
      try (var rs = ps.executeQuery()) {
        return rs.next() ? Optional.of(mapRow(rs)) : Optional.empty();
      }
    }
  }

  public List<WatchHistoryEntry> findAll() throws SQLException {
    var list = new ArrayList<WatchHistoryEntry>();
    try (var conn = ds.getConnection();
        var ps = conn.prepareStatement("SELECT * FROM watch_history");
        var rs = ps.executeQuery()) {
      while (rs.next()) list.add(mapRow(rs));
    }
    return list;
  }

  public void deleteByCatalogId(String catalogId) throws SQLException {
    try (var conn = ds.getConnection();
        var ps = conn.prepareStatement("DELETE FROM watch_history WHERE catalog_id = ?")) {
      ps.setString(1, catalogId);
      ps.executeUpdate();
    }
  }

  private WatchHistoryEntry mapRow(ResultSet rs) throws SQLException {
    return new WatchHistoryEntry(
        rs.getString("user_id"),
        rs.getString("catalog_id"),
        rs.getString("title"),
        rs.getLong("resume_timestamp"),
        rs.getBoolean("completed"),
        rs.getLong("last_watched"));
  }
}
