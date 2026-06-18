package com.flicenjoyer.valkey;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.UUID;
import org.yaml.snakeyaml.Yaml;

/** Manages the local user profile (userId, displayName) persisted in YAML. */
public class UserProfileManager {

  private final Path profileFile;
  private final Yaml yaml =
      new Yaml(
          new org.yaml.snakeyaml.constructor.SafeConstructor(
              new org.yaml.snakeyaml.LoaderOptions()));
  private String userId;
  private String displayName;

  public UserProfileManager() {
    this(AppPaths.PROFILE);
  }

  public UserProfileManager(Path profileFile) {
    this.profileFile = profileFile;
  }

  public boolean profileExists() {
    return Files.exists(profileFile);
  }

  public void load() throws IOException {
    Map<String, String> data = yaml.load(Files.readString(profileFile));
    if (data == null) throw new IOException("Empty or malformed profile: " + profileFile);
    this.userId = data.get("userId");
    this.displayName = data.get("displayName");
  }

  public void createProfile(String fullName) throws IOException {
    this.userId = UUID.randomUUID().toString();
    this.displayName = fullName;
    Files.createDirectories(profileFile.getParent());
    Map<String, String> data = new LinkedHashMap<>();
    data.put("userId", userId);
    data.put("displayName", displayName);
    Files.writeString(profileFile, yaml.dump(data));
  }

  public String getUserId() {
    return userId;
  }

  public String getDisplayName() {
    return displayName;
  }
}
