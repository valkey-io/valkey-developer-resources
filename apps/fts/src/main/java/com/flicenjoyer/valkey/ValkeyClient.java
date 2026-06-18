package com.flicenjoyer.valkey;

import glide.api.models.Batch;
import glide.api.models.GlideString;
import glide.api.models.commands.FT.FTAggregateOptions;
import glide.api.models.commands.FT.FTCreateOptions;
import glide.api.models.commands.FT.FTCreateOptions.FieldInfo;
import glide.api.models.commands.FT.FTSearchOptions;
import glide.api.models.commands.scan.ScanOptions;
import java.util.Map;
import java.util.concurrent.CompletableFuture;

/** Testable interface over GlideClient methods used by services. */
public interface ValkeyClient {

  CompletableFuture<Long> hset(GlideString key, Map<GlideString, GlideString> fields);

  CompletableFuture<GlideString> hget(GlideString key, GlideString field);

  CompletableFuture<Map<GlideString, GlideString>> hgetall(GlideString key);

  CompletableFuture<Long> del(GlideString[] keys);

  CompletableFuture<Object[]> exec(Batch batch, boolean raiseOnError);

  CompletableFuture<Object[]> scan(String cursor, ScanOptions options);

  // FT module wrappers
  CompletableFuture<Object[]> ftSearch(String indexName, String query, FTSearchOptions options);

  @SuppressWarnings("unchecked")
  CompletableFuture<Map<GlideString, Object>[]> ftAggregate(
      String indexName, String query, FTAggregateOptions options);

  CompletableFuture<GlideString[]> ftList();

  CompletableFuture<String> ftCreate(String indexName, FieldInfo[] schema, FTCreateOptions options);
}
