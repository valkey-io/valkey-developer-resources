package com.flicenjoyer.model;

/** Per-user watch session record with resume position and completion status. */
public record WatchHistoryEntry(
    String userId,
    String catalogId,
    String title,
    long resumeTimestamp,
    boolean completed,
    long lastWatched) {}
