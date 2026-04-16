package com.flicenjoyer.service;

import static glide.api.models.GlideString.gs;

import com.flicenjoyer.valkey.AppPaths;
import com.flicenjoyer.valkey.ValkeyKeys;
import glide.api.GlideClient;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ExecutionException;

/** Handles video upload: copies media files to local storage and creates catalog hash in Valkey. */
public class UploadService {

  private final GlideClient client;

  public UploadService(GlideClient client) {
    this.client = client;
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

    client
        .hset(
            gs(ValkeyKeys.catalogKey(id)),
            Map.of(
                gs("title"), gs(title),
                gs("genre"), gs(genre),
                gs("description"), gs(description),
                gs("tags"), gs(tags),
                gs("releaseYear"), gs(String.valueOf(releaseYear)),
                gs("rating"), gs("0"),
                gs("durationMinutes"), gs(String.valueOf(durationMinutes)),
                gs("videoPath"), gs(videoTarget.toAbsolutePath().toString()),
                gs("thumbnailPath"), gs(thumbnailPath)))
        .get();

    return id;
  }

  static String getExtension(Path file) {
    var name = file.getFileName().toString();
    int dot = name.lastIndexOf('.');
    return dot >= 0 ? name.substring(dot) : "";
  }
}
