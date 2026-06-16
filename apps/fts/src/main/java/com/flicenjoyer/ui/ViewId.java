package com.flicenjoyer.ui;

/** Type-safe view identifiers for navigation. */
public enum ViewId {
  SEARCH("Search"),
  BROWSE("Browse"),
  UPLOAD("Upload"),
  HISTORY("My History"),
  PLAYER("Player"),
  REPORTS("Reports"),
  BENCHMARKS("Benchmarks"),
  ADMINISTRATION("Administration"),
  EDIT_VIDEO("Edit Video");

  private final String label;

  ViewId(String label) {
    this.label = label;
  }

  public String label() {
    return label;
  }

  @Override
  public String toString() {
    return label;
  }
}
