package com.flicenjoyer.valkey;

import java.nio.file.Path;

/** Centralized application paths. */
public final class AppPaths {
  private AppPaths() {}

  public static final Path HOME = Path.of(System.getProperty("user.home"), ".flicenjoyer");
  public static final Path MEDIA = HOME.resolve("media");
  public static final Path VIDEOS = MEDIA.resolve("videos");
  public static final Path THUMBNAILS = MEDIA.resolve("thumbnails");
  public static final Path PROFILE = HOME.resolve("profile.yaml");
  public static final Path LOG_FILE = HOME.resolve("flicenjoyer.log");
}
