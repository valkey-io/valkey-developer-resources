# GLIDE ValkeySearch 1.2 API Reference — FlicEnjoyer

Source: [valkey-glide](https://github.com/valkey-io/valkey-glide) version 2.4.1 (Maven Central)

## Java API Source Files
- `java/client/src/main/java/glide/api/commands/servermodules/FT.java`
- `java/client/src/main/java/glide/api/models/commands/FT/FTCreateOptions.java`
- `java/client/src/main/java/glide/api/models/commands/FT/FTSearchOptions.java`
- `java/client/src/main/java/glide/api/models/commands/FT/FTAggregateOptions.java`
- `java/client/src/main/java/glide/api/models/commands/FT/FTInfoOptions.java`

## FT.CREATE — Index-Level Options (FTCreateOptions)

New builder methods on `FTCreateOptions.builder()`:

| Method | Type | Description |
|---|---|---|
| `score(double)` | Double | Default document score (default 1.0) |
| `language(String)` | String | Default stemming language |
| `skipInitialScan(true)` | boolean | Skip indexing existing docs on creation |
| `minStemSize(int)` | Integer | Minimum word length for stemming |
| `withOffsets(true)` | boolean | Store term offsets (mutually exclusive with `noOffsets`) |
| `noOffsets(true)` | boolean | Disable term offsets (mutually exclusive with `withOffsets`) |
| `noStopWords(true)` | boolean | Disable stop-word filtering (mutually exclusive with `stopWords`) |
| `stopWords(String[])` | String[] | Custom stop words (mutually exclusive with `noStopWords`) |
| `punctuation(String)` | String | Custom punctuation characters for tokenization |

## FT.CREATE — Field Types

### TextField

Constructor: `new TextField(boolean noStem, Double weight, boolean withSuffixTrie, boolean noSuffixTrie, boolean sortable)`

| Param | Description |
|---|---|
| `noStem` | Disable stemming for this field |
| `weight` | Field importance weight (default 1.0) |
| `withSuffixTrie` | Keep suffix trie for contains/suffix queries (mutually exclusive with `noSuffixTrie`) |
| `noSuffixTrie` | Disable suffix trie (mutually exclusive with `withSuffixTrie`) |
| `sortable` | Allow sorting by this field |

### NumericField

Constructor: `new NumericField(boolean sortable)`

### TagField

Constructor: `new TagField(char separator, boolean caseSensitive, boolean sortable)`

Also: `new TagField(boolean caseSensitive, boolean sortable)`

## FT.SEARCH — Query Options (FTSearchOptions)

New builder methods on `FTSearchOptions.builder()`:

| Method | Description |
|---|---|
| `nocontent()` | Return only document IDs, no field content |
| `verbatim()` | Disable stemming on query terms |
| `inorder()` | Require proximity terms in order |
| `slop(int)` | Max intervening terms for proximity matching |
| `sortBy(GlideString field, SortOrder order)` | Sort results by field (ASC/DESC) |
| `withSortKeys()` | Include sort keys in results (requires `sortBy`) |
| `shardScope(ShardScope)` | ALLSHARDS or SOMESHARDS (cluster mode) |
| `consistency(ConsistencyMode)` | CONSISTENT or INCONSISTENT (cluster mode) |
| `dialect(int)` | Query dialect version |

## FT.AGGREGATE — Query Flags (FTAggregateOptions)

New builder methods on `FTAggregateOptions.builder()`:

| Method | Description |
|---|---|
| `verbatim()` | Disable stemming |
| `inorder()` | Require term order |
| `slop(int)` | Proximity slop |
| `dialect(int)` | Query dialect version |

## FT.INFO — New Overload (FTInfoOptions)

`FT.info(client, indexName, new FTInfoOptions(scope, shardScope, consistency))`

| Enum | Values | Description |
|---|---|---|
| `InfoScope` | LOCAL, PRIMARY, CLUSTER | Which nodes provide index info |
| `ShardScope` | ALLSHARDS, SOMESHARDS | Shard participation |
| `ConsistencyMode` | CONSISTENT, INCONSISTENT | Consistency requirements |
