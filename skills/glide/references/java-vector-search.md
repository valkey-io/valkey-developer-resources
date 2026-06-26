# Java Vector Search (FT Module)

## Imports
```java
import glide.api.commands.servermodules.FT;
import glide.api.models.commands.FT.FTCreateOptions;
import glide.api.models.commands.FT.FTCreateOptions.FieldInfo;
import glide.api.models.commands.FT.FTCreateOptions.VectorFieldFlat;
import glide.api.models.commands.FT.FTCreateOptions.DistanceMetric;
import glide.api.models.commands.FT.FTSearchOptions;
import glide.api.models.GlideString;
```

## Index Creation
```java
FieldInfo[] schema = new FieldInfo[] {
    new FieldInfo("embedding", 
        VectorFieldFlat.builder(DistanceMetric.COSINE, 768).build())
};
FT.create(client, "my_idx", schema).get();
```

## Store Documents with Vectors
```java
// CRITICAL: Use GlideString for binary vector data
Map<GlideString, GlideString> doc = Map.of(
    GlideString.of("embedding"), GlideString.of(vectorBytes),
    GlideString.of("text"), GlideString.of("content")
);
client.hset(GlideString.of("doc:1"), doc).get();
```

## Vector Search

**⚠️ SECURITY:** The `=>` token in FT.SEARCH syntax separates a filter from a KNN clause. If user-controlled input (e.g., a filter parameter) contains `=>`, an attacker can inject a KNN query that bypasses all filters and returns all documents. Reject `=>` in any user-supplied filter or field name before interpolating into query strings:
```java
if (userFilter != null && userFilter.contains("=>")) {
    throw new IllegalArgumentException("Filter must not contain '=>'");
}
```

```java
String query = "*=>[KNN 5 @embedding $vector AS score]";
FTSearchOptions opts = FTSearchOptions.builder()
    .params(Map.of(GlideString.of("vector"), GlideString.of(queryVectorBytes)))
    .build();

Object[] results = FT.search(client, "my_idx", query, opts).get();
Long count = (Long) results[0];
if (results.length > 1) {
    Map<GlideString, Map<GlideString, GlideString>> docs = 
        (Map<GlideString, Map<GlideString, GlideString>>) results[1];
}
```

## Index Management
```java
// Drop index
FT.dropindex(client, "my_idx").get();

// Get info
Map<String, Object> info = FT.info(client, "my_idx").get();

// List indexes
GlideString[] indexes = FT.list(client).get();
```

## Vector Encoding Helper
```java
private static byte[] floatArrayToBytes(float[] array) {
    ByteBuffer buffer = ByteBuffer.allocate(array.length * 4)
        .order(ByteOrder.LITTLE_ENDIAN);
    for (float f : array) {
        buffer.putFloat(f);
    }
    return buffer.array();
}
```

**Key Points:**
- FT methods are static on `FT` class, not client methods
- Use `GlideString.of()` factory method for binary data
- **CRITICAL:** Binary vectors MUST use `GlideString`, NOT `String` - converting bytes to String corrupts data
- Search returns `Object[]`: `[count, documents_map]`
- Documents map only present if count > 0 - check `results.length > 1`
- Use `ByteOrder.LITTLE_ENDIAN` for vector encoding
