package com.flicenjoyer.model;

import java.util.Map;

public record AggregationResult(String label, Map<String, Object> metrics) {
  public AggregationResult {
    metrics = Map.copyOf(metrics);
  }
}
