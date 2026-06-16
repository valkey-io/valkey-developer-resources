package com.flicenjoyer.model;

/** Catalog entry representing a video with metadata, rating, and file paths. */
public record Movie(
    String id,
    String title,
    String genre,
    String description,
    String tags,
    int releaseYear,
    double rating,
    double durationMinutes,
    String videoPath,
    String thumbnailPath) {}
