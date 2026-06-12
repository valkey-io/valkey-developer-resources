package com.flicenjoyer;

import com.flicenjoyer.db.CatalogRepository;
import com.flicenjoyer.db.DatabaseProvider;
import com.flicenjoyer.db.WatchHistoryRepository;
import com.flicenjoyer.model.Movie;
import com.flicenjoyer.model.WatchHistoryEntry;
import com.flicenjoyer.valkey.AppConfig;
import java.sql.SQLException;
import java.time.Instant;
import java.util.UUID;
import java.util.concurrent.ThreadLocalRandom;

/**
 * Seeds fake catalog and watch history data for demos and benchmarks. All seeded IDs use the
 * "bench-" prefix (catalog) or "s" prefix (viewers) for easy cleanup via {@code ./gradlew
 * unseedData}.
 *
 * <p>Usage: ./gradlew seedData [--args="500"] (default 200 catalog entries)
 */
public class SeedData {

  static final String CATALOG_PREFIX = "bench-";

  private static final String[] TITLES = {
    "The Great Adventure", "Midnight Run", "Silent Echo", "Dark Horizon", "Stellar Dawn",
    "Crimson Tide", "Broken Arrow", "Frozen Hearts", "Thunder Road", "Silver Lining",
    "Shadow Protocol", "Crystal Falls", "Iron Valley", "Golden Gate", "Amber Waves",
    "Neon Nights", "Velvet Storm", "Cosmic Drift", "Savage Grace", "Rogue Element",
    "Blazing Trail", "Deep Current", "Wild Frontier", "Stone Cold", "Bright Star",
    "Last Horizon", "First Light", "Red Planet", "Blue Ocean", "Green Valley",
    "White Noise", "Black Mirror", "Lost City", "Hidden Depths", "Open Range",
    "Final Stand", "New Dawn", "Old Flames", "Rising Tide", "Falling Skies",
    "Burning Bridges", "Hollow Point", "Sharp Edge", "Soft Landing", "Hard Rain",
    "Sweet Revenge", "Bitter End", "Long Road", "Short Circuit", "Double Cross"
  };
  private static final String[] GENRES = {
    "Action", "Drama", "Sci-Fi", "Thriller", "Comedy", "Horror", "Romance", "Documentary"
  };

  public static void main(String[] args) throws SQLException {
    int catalogCount = args.length > 0 ? Integer.parseInt(args[0]) : 200;
    var config = AppConfig.load();
    var dbProvider = new DatabaseProvider(config);
    var catalogRepo = new CatalogRepository(dbProvider.getDataSource());
    var watchRepo = new WatchHistoryRepository(dbProvider.getDataSource());
    var rng = ThreadLocalRandom.current();

    // Seed catalog
    for (int i = 0; i < catalogCount; i++) {
      var id = CATALOG_PREFIX + UUID.randomUUID().toString().substring(0, 8);
      var title = TITLES[rng.nextInt(TITLES.length)] + " " + (i + 1);
      var genre = GENRES[rng.nextInt(GENRES.length)];
      var movie =
          new Movie(
              id, title, genre, "Benchmark seed entry " + i, "benchmark",
              rng.nextInt(1980, 2025), rng.nextDouble(1.0, 10.0),
              rng.nextDouble(60, 180), "", "");
      catalogRepo.insert(movie);
    }
    System.out.println("Seeded " + catalogCount + " catalog entries");

    // Seed watch history for ALL catalog entries (real + seeded)
    var allMovies = catalogRepo.findAll();
    int totalViewers = 0;
    for (var movie : allMovies) {
      int viewers = rng.nextInt(10, 201);
      for (int i = 0; i < viewers; i++) {
        var fakeUserId = "s" + UUID.randomUUID().toString().substring(0, 35);
        var now = Instant.now().getEpochSecond() - rng.nextInt(0, 86400 * 30);
        var entry = new WatchHistoryEntry(fakeUserId, movie.id(), movie.title(), 0, true, now);
        watchRepo.upsert(entry);
      }
      totalViewers += viewers;
    }
    System.out.println(
        "Seeded " + totalViewers + " watch history entries across " + allMovies.size() + " titles");

    dbProvider.close();
  }
}
