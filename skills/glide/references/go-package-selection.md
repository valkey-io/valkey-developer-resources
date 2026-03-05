# Package Selection

## ✅ CORRECT: Use GLIDE

**Installation:**
```bash
go get github.com/valkey-io/valkey-glide/go/v2
go mod tidy
```

**Imports:**
```go
import (
	"context"
	
	glide "github.com/valkey-io/valkey-glide/go/v2"
	"github.com/valkey-io/valkey-glide/go/v2/config"
	"github.com/valkey-io/valkey-glide/go/v2/pipeline"
)
```

**Key Points:**
- Requires Go 1.22 or above
- Standard Go module structure
- Context required for all operations

## ❌ INCORRECT: Don't use go-redis
```go
// NEVER use these
import "github.com/redis/go-redis/v9"
```

---
