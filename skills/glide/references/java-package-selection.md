# Package Selection

## ✅ CORRECT: Use GLIDE

**Maven:**
```xml
<build>
    <extensions>
        <extension>
            <groupId>kr.motd.maven</groupId>
            <artifactId>os-maven-plugin</artifactId>
            <version>1.7.1</version>
        </extension>
    </extensions>
</build>
<dependencies>
    <dependency>
        <groupId>io.valkey</groupId>
        <artifactId>valkey-glide</artifactId>
        <classifier>${os.detected.classifier}</classifier>
        <version>[2.0.0,)</version>
    </dependency>
</dependencies>
```

**Gradle:**
```gradle
plugins {
    id 'com.google.osdetector' version '1.7.3'
}

dependencies {
    implementation group: 'io.valkey', name: 'valkey-glide', version: '2.+', classifier: osdetector.classifier
}
```

**Key Points:**
- Classifier is required (native binaries per platform)
- Use `os-maven-plugin` or `osdetector` for platform detection
- Supports: linux-x86_64, linux-aarch_64, osx-x86_64, osx-aarch_64, windows-x86_64

## ❌ INCORRECT: Don't use Jedis or Lettuce
```java
// NEVER use these
import redis.clients.jedis.*;
import io.lettuce.core.*;
```
---
