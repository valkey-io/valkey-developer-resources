package com.flicenjoyer.valkey;

import static org.junit.jupiter.api.Assertions.*;

import org.junit.jupiter.api.Test;

class AppPathsTest {

  @Test
  void pathsAreConsistent() {
    assertTrue(AppPaths.MEDIA.startsWith(AppPaths.HOME));
    assertTrue(AppPaths.VIDEOS.startsWith(AppPaths.MEDIA));
    assertTrue(AppPaths.THUMBNAILS.startsWith(AppPaths.MEDIA));
    assertTrue(AppPaths.PROFILE.startsWith(AppPaths.HOME));
    assertTrue(AppPaths.LOG_FILE.startsWith(AppPaths.HOME));
  }

  @Test
  void pathsEndWithExpectedNames() {
    assertTrue(AppPaths.PROFILE.toString().endsWith("profile.yaml"));
    assertTrue(AppPaths.VIDEOS.toString().endsWith("videos"));
    assertTrue(AppPaths.THUMBNAILS.toString().endsWith("thumbnails"));
  }
}
