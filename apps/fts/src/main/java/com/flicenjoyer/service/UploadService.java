package com.flicenjoyer.service;

import static glide.api.models.GlideString.gs;

import com.flicenjoyer.db.CatalogRepository;
import com.flicenjoyer.model.Movie;
import com.flicenjoyer.valkey.AppPaths;
import com.flicenjoyer.valkey.HashParser;
import com.flicenjoyer.valkey.ValkeyKeys;
import glide.api.GlideClient;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.sql.SQLException;
import java.util.UUID;
import java.util.concurrent.ExecutionException;

/** Handles video upload: copies media, writes to DB, then populates Valkey cache. */
public class UploadService {

  private final GlideClient client;
  private final CatalogRepository catalogRepo;

  public UploadService(GlideClient client, CatalogRepository catalogRepo) {
    this.client = client;
    this.catalogRepo = catalogRepo;
  }

  public String uploadVideo(
      String title,
      String genre,
      String description,
      String tags,
      int releaseYear,
      double durationMinutes,
      Path videoFile,
      Path thumbnailFile)
      throws IOException, ExecutionException, InterruptedException {

    var id = UUID.randomUUID().toString();

    Files.createDirectories(AppPaths.VIDEOS);
    var videoExt = getExtension(videoFile);
    var videoTarget = AppPaths.VIDEOS.resolve(id + videoExt);
    Files.copy(videoFile, videoTarget, StandardCopyOption.REPLACE_EXISTING);

    String thumbnailPath = "";
    if (thumbnailFile != null) {
      Files.createDirectories(AppPaths.THUMBNAILS);
      var thumbExt = getExtension(thumbnailFile);
      var thumbTarget = AppPaths.THUMBNAILS.resolve(id + thumbExt);
      Files.copy(thumbnailFile, thumbTarget, StandardCopyOption.REPLACE_EXISTING);
      thumbnailPath = thumbTarget.toAbsolutePath().toString();
    }

    var movie =
        new Movie(
            id,
            title,
            genre,
            description,
            tags,
            releaseYear,
            0.0,
            durationMinutes,
            videoTarget.toAbsolutePath().toString(),
            thumbnailPath);

    // Write to DB first (source of truth)
    try {
      catalogRepo.insert(movie);
    } catch (SQLException e) {
      throw new RuntimeException("DB insert failed for catalog " + id, e);
    }

    // Populate Valkey cache (ValkeySearch auto-indexes via prefix)
    client.hset(gs(ValkeyKeys.catalogKey(id)), HashParser.movieToHash(movie)).get();

    return id;
  }

  static String getExtension(Path file) {
    var name = file.getFileName().toString();
    int dot = name.lastIndexOf('.');
    return dot >= 0 ? name.substring(dot) : "";
  }
}
