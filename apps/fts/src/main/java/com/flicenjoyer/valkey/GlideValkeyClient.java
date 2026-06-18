package com.flicenjoyer.valkey;

import glide.api.GlideClient;
import glide.api.commands.servermodules.FT;
import glide.api.models.Batch;
import glide.api.models.GlideString;
import glide.api.models.commands.FT.FTAggregateOptions;
import glide.api.models.commands.FT.FTCreateOptions;
import glide.api.models.commands.FT.FTCreateOptions.FieldInfo;
import glide.api.models.commands.FT.FTSearchOptions;
import glide.api.models.commands.scan.ScanOptions;
import java.util.Map;
import java.util.concurrent.CompletableFuture;

/** Delegates to a real GlideClient. */
public class GlideValkeyClient implements ValkeyClient {

  private final GlideClient delegate;

  public GlideValkeyClient(GlideClient delegate) {
    this.delegate = delegate;
  }

  @Override
  public CompletableFuture<Long> hset(GlideString key, Map<GlideString, GlideString> fields) {
    return delegate.hset(key, fields);
  }

  @Override
  public CompletableFuture<GlideString> hget(GlideString key, GlideString field) {
    return delegate.hget(key, field);
  }

  @Override
  public CompletableFuture<Map<GlideString, GlideString>> hgetall(GlideString key) {
    return delegate.hgetall(key);
  }

  @Override
  public CompletableFuture<Long> del(GlideString[] keys) {
    return delegate.del(keys);
  }

  @Override
  public CompletableFuture<Object[]> exec(Batch batch, boolean raiseOnError) {
    return delegate.exec(batch, raiseOnError);
  }

  @Override
  public CompletableFuture<Object[]> scan(String cursor, ScanOptions options) {
    return delegate.scan(cursor, options);
  }

  @Override
  public CompletableFuture<Object[]> ftSearch(
      String indexName, String query, FTSearchOptions options) {
    return FT.search(delegate, indexName, query, options);
  }

  @Override
  @SuppressWarnings("unchecked")
  public CompletableFuture<Map<GlideString, Object>[]> ftAggregate(
      String indexName, String query, FTAggregateOptions options) {
    return FT.aggregate(delegate, indexName, query, options);
  }

  @Override
  public CompletableFuture<GlideString[]> ftList() {
    return FT.list(delegate);
  }

  @Override
  public CompletableFuture<String> ftCreate(
      String indexName, FieldInfo[] schema, FTCreateOptions options) {
    return FT.create(delegate, indexName, schema, options);
  }
}
