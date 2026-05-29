package com.flicenjoyer.db;

import com.flicenjoyer.model.Movie;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;
import javax.sql.DataSource;

/** JDBC repository for the catalog table. */
public final class CatalogRepository {

  private final DataSource ds;

  public CatalogRepository(DataSource ds) {
    this.ds = ds;
  }

  public void insert(Movie movie) throws SQLException {
    var sql =
        "INSERT INTO catalog (id, title, genre, description, tags, release_year, rating,"
            + " duration_minutes, video_path, thumbnail_path) VALUES (?,?,?,?,?,?,?,?,?,?)";
    try (var conn = ds.getConnection();
        var ps = conn.prepareStatement(sql)) {
      ps.setString(1, movie.id());
      ps.setString(2, movie.title());
      ps.setString(3, movie.genre());
      ps.setString(4, movie.description());
      ps.setString(5, movie.tags());
      ps.setInt(6, movie.releaseYear());
      ps.setDouble(7, movie.rating());
      ps.setDouble(8, movie.durationMinutes());
      ps.setString(9, movie.videoPath());
      ps.setString(10, movie.thumbnailPath());
      ps.executeUpdate();
    }
  }

  public Optional<Movie> findById(String id) throws SQLException {
    try (var conn = ds.getConnection();
        var ps = conn.prepareStatement("SELECT * FROM catalog WHERE id = ?")) {
      ps.setString(1, id);
      try (var rs = ps.executeQuery()) {
        return rs.next() ? Optional.of(mapRow(rs)) : Optional.empty();
      }
    }
  }

  public List<Movie> findAll() throws SQLException {
    var list = new ArrayList<Movie>();
    try (var conn = ds.getConnection();
        var ps = conn.prepareStatement("SELECT * FROM catalog ORDER BY title");
        var rs = ps.executeQuery()) {
      while (rs.next()) list.add(mapRow(rs));
    }
    return list;
  }

  public void updateDuration(String id, double minutes) throws SQLException {
    try (var conn = ds.getConnection();
        var ps = conn.prepareStatement("UPDATE catalog SET duration_minutes = ? WHERE id = ?")) {
      ps.setDouble(1, minutes);
      ps.setString(2, id);
      ps.executeUpdate();
    }
  }

  public void updateRating(String id, double rating) throws SQLException {
    try (var conn = ds.getConnection();
        var ps = conn.prepareStatement("UPDATE catalog SET rating = ? WHERE id = ?")) {
      ps.setDouble(1, rating);
      ps.setString(2, id);
      ps.executeUpdate();
    }
  }

  public void updateMetadata(
      String id, String title, String genre, String description, String tags, int releaseYear)
      throws SQLException {
    var sql =
        "UPDATE catalog SET title=?, genre=?, description=?, tags=?, release_year=? WHERE id=?";
    try (var conn = ds.getConnection();
        var ps = conn.prepareStatement(sql)) {
      ps.setString(1, title);
      ps.setString(2, genre);
      ps.setString(3, description);
      ps.setString(4, tags);
      ps.setInt(5, releaseYear);
      ps.setString(6, id);
      ps.executeUpdate();
    }
  }

  public void updateThumbnail(String id, String thumbnailPath) throws SQLException {
    try (var conn = ds.getConnection();
        var ps = conn.prepareStatement("UPDATE catalog SET thumbnail_path = ? WHERE id = ?")) {
      ps.setString(1, thumbnailPath);
      ps.setString(2, id);
      ps.executeUpdate();
    }
  }

  public void delete(String id) throws SQLException {
    try (var conn = ds.getConnection();
        var ps = conn.prepareStatement("DELETE FROM catalog WHERE id = ?")) {
      ps.setString(1, id);
      ps.executeUpdate();
    }
  }

  private Movie mapRow(ResultSet rs) throws SQLException {
    return new Movie(
        rs.getString("id"),
        rs.getString("title"),
        rs.getString("genre"),
        rs.getString("description"),
        rs.getString("tags"),
        rs.getInt("release_year"),
        rs.getDouble("rating"),
        rs.getDouble("duration_minutes"),
        rs.getString("video_path"),
        rs.getString("thumbnail_path"));
  }
}
