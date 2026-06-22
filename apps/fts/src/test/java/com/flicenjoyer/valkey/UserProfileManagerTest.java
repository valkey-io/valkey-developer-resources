package com.flicenjoyer.valkey;

import static org.junit.jupiter.api.Assertions.*;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class UserProfileManagerTest {

  @TempDir Path tempDir;

  @Test
  void profileExistsReturnsFalseWhenNoFile() {
    UserProfileManager mgr = new UserProfileManager(tempDir.resolve("profile.yaml"));
    assertFalse(mgr.profileExists());
  }

  @Test
  void createProfileWritesFileAndSetsFields() throws IOException {
    Path profileFile = tempDir.resolve("profile.yaml");
    UserProfileManager mgr = new UserProfileManager(profileFile);

    mgr.createProfile("John Doe");

    assertTrue(Files.exists(profileFile));
    assertNotNull(mgr.getUserId());
    assertFalse(mgr.getUserId().isEmpty());
    assertEquals("John Doe", mgr.getDisplayName());
  }

  @Test
  void loadReadsExistingProfile() throws IOException {
    Path profileFile = tempDir.resolve("profile.yaml");
    Files.writeString(profileFile, "userId: \"test-uuid-123\"\ndisplayName: \"Jane Smith\"\n");

    UserProfileManager mgr = new UserProfileManager(profileFile);
    assertTrue(mgr.profileExists());
    mgr.load();

    assertEquals("test-uuid-123", mgr.getUserId());
    assertEquals("Jane Smith", mgr.getDisplayName());
  }

  @Test
  void createThenLoadRoundTrips() throws IOException {
    Path profileFile = tempDir.resolve("sub/profile.yaml");
    UserProfileManager creator = new UserProfileManager(profileFile);
    creator.createProfile("Round Trip");

    UserProfileManager loader = new UserProfileManager(profileFile);
    loader.load();

    assertEquals(creator.getUserId(), loader.getUserId());
    assertEquals("Round Trip", loader.getDisplayName());
  }
}
