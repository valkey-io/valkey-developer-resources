# GLIDE Performance Optimization Skill

Expert guidance for optimizing Valkey GLIDE clients across Node.js, Python, Java, Go, and PHP. This skill provides context-aware performance optimization feedback through AI development tools (Kiro, Claude, WindSurf, VS Code).

## Problem

Common performance mistakes when using Valkey GLIDE clients can degrade latency by orders of magnitude:

- **Per-request client creation** adds connection overhead to every request
- **Missing timeouts** cause operations to hang indefinitely, leading to cascading failures
- **Sequential operations** multiply network roundtrip latency (3 sequential calls = 3x the latency)
- **Blocking commands on shared clients** freeze all operations for seconds at a time

These issues are easy to introduce and hard to spot in code review without domain expertise. This skill encodes that expertise so AI tools can catch these patterns automatically during development before they reach production.

## Features

- **Progressive Disclosure**: Loads only relevant language-specific patterns, significantly reducing context usage
- **Multi-Language Support**: Node.js, Python, Java, Go, and PHP
- **Automatic Language Detection**: Detects language from file extensions, imports, and syntax
- **Actionable Recommendations**: Provides before/after code examples and configuration guidance
- **Anti-Pattern Detection**: Identifies common performance issues like per-request client creation, missing timeouts, sequential operations

## Installation

### Quick Install (Recommended)

```bash
# Using NPX (requires Node.js 16+)
npx skills add valkey-io/valkey-samples/skills/glide-performance
```

This automatically installs the skill to your AI tool's skills directory.

### Updating

```bash
# Update to latest version
npx skills update glide-performance
```

### Manual Installation

```bash
git clone https://github.com/valkey-io/valkey-samples
```

Then copy the skill to your AI tool's skills directory:

```bash
# For Kiro:
cp -r valkey-samples/skills/glide-performance ~/.kiro/skills/glide-performance
rm -rf ~/.kiro/skills/glide-performance/benchmarks

# For Claude:
cp -r valkey-samples/skills/glide-performance ~/.claude/skills/glide-performance
rm -rf ~/.claude/skills/glide-performance/benchmarks

# For VSCode (User Profile):
cp -r valkey-samples/skills/glide-performance ~/.agents/skills/glide-performance
rm -rf ~/.agents/skills/glide-performance/benchmarks

# For WindSurf (Global):
cp -r valkey-samples/skills/glide-performance ~/.codeium/windsurf/skills/glide-performance
rm -rf ~/.codeium/windsurf/skills/glide-performance/benchmarks
```

### Prerequisites

- **Git** installed (for manual installation)
- **Node.js 16+** (if using npx skills command)
- **AI development tool** installed (Kiro, Claude Desktop, WindSurf, or VS Code with compatible extension)

### Verification

After installation, verify the skill is available by asking in your AI tool's chat interface:

```
"List available skills"
```

You should see "glide-performance" or "GLIDE Performance Optimization" in the list.

## Usage

### Basic Code Review

1. Open a file containing Valkey GLIDE client code (e.g., `userService.js`)
2. Request code review: "Review this code for Valkey performance issues"
3. The skill automatically:
   - Loads core principles and anti-patterns
   - Detects your programming language
   - Loads language-specific patterns on-demand
   - Provides targeted recommendations with code examples

### Example Prompts

**General Review**:
- "Review this code for Valkey performance issues"
- "Check for GLIDE anti-patterns in this file"
- "Optimize this Valkey client code"

**Specific Issues**:
- "Is this client configuration optimal?"
- "Should I use batching here?"
- "How can I reduce latency in this code?"
- "Review my error handling strategy"

## What Gets Loaded

The skill uses progressive disclosure to minimize context usage:

### Always Loaded (Core)
- `SKILL.md` - Universal anti-patterns and optimization strategies (~200 lines)

### Loaded On-Demand (Language-Specific)
- `reference/nodejs-patterns.md` - Node.js/TypeScript patterns (loaded only for .js/.ts files)
- `reference/python-patterns.md` - Python patterns (loaded only for .py files)
- `reference/java-patterns.md` - Java patterns (loaded only for .java files)
- `reference/go-patterns.md` - Go patterns (loaded only for .go files)
- `reference/php-patterns.md` - PHP patterns (loaded only for .php files)

### Additional Resources (Loaded When Referenced)
- `assets/server-configuration-guide.md` - Valkey/ElastiCache infrastructure optimization
- `reference/config-templates/` - Production-ready configuration examples per language

**Context Efficiency**: Reviewing Node.js code loads only Node.js patterns. Python/Java/Go/PHP patterns remain unloaded, reducing the amount of context loaded into your AI tool.

## Common Anti-Patterns Detected

1. **Per-Request Client Creation** - Creating clients inside request handlers
2. **Missing Request Timeouts** - No timeout configuration
3. **Sequential Operations** - Not using batching or concurrency
4. **Blocking Commands on Shared Client** - BLPOP/BRPOP blocking other operations
5. **Large Batch Sizes** - Batches with >1000 operations
6. **Missing Error Handling** - No retry strategy or error handling

## Optimization Strategies Provided

1. **Batching** - Pipeline and transaction patterns
2. **Cluster-Aware Operations** - Hash tags for co-location
3. **AZ Affinity** - Cost optimization for read-heavy workloads
4. **Async/Concurrent Patterns** - Reducing wall-clock time
5. **Data Size Optimization** - Hash structures vs JSON strings
6. **Configuration Tuning** - Timeouts, retries, inflight request limits
7. **SCAN vs Valkey-Search** - Using FT.* indexes instead of O(N) keyspace scans
8. **Valkey Module Detection** - Optimization guidance for Valkey-Search, JSON, and BloomFilter modules

## Architecture

```
glide-performance/
├── SKILL.md                          # Core skill (always loaded)
├── README.md                         # This file
├── reference/                        # On-demand language patterns
│   ├── nodejs-patterns.md            # Node.js/TypeScript
│   ├── python-patterns.md            # Python async/sync
│   ├── java-patterns.md              # Java
│   ├── go-patterns.md                # Go
│   ├── php-patterns.md               # PHP
│   └── config-templates/             # Production-ready configs
│       ├── nodejs-config.ts
│       ├── python-config.py
│       ├── java-config.java
│       ├── go-config.go
│       ├── php-config.php
│       └── README.md
├── benchmarks/                       # Performance impact measurement
│   ├── README.md                     # Benchmark instructions
│   ├── app-benchmark.js              # Benchmark runner
│   └── valkey-template.js            # Stubs for AI to implement
└── assets/
    └── server-configuration-guide.md # Valkey/ElastiCache infrastructure
```

## Performance Impact

Expected improvements when moving from anti-patterns to recommended patterns. Actual results vary significantly based on your infrastructure, network conditions, data sizes, and workload characteristics. See [benchmarks/](benchmarks/) for a runnable benchmark that measures the real-world impact of following the skill's recommendations.

| Anti-Pattern | Impact | Recommended Pattern | Complexity |
|--------------|--------|---------------------|------------|
| Per-request client creation | Adds connection overhead to every request; dramatically reduces throughput | Reuse client across requests | Low |
| Sequential operations | Latency scales with number of roundtrips | Use batching: reduces N roundtrips to 1 | Low-Medium |
| Missing timeouts | Operations can hang indefinitely; risk of cascading failures | Configure request timeouts | Low |
| Cross-AZ reads (read-heavy) | Higher latency and data transfer costs | Enable AZ Affinity routing | Medium |
| Blocking commands on shared client | Blocks all operations for duration of blocking call | Use dedicated client for blocking operations | Low |
| Large batches (>1000 ops) | Memory pressure; increased timeout risk | Split into smaller batches (10-100 ops) | Low |

**Note**: Performance improvements are workload-dependent. The [benchmarks/](benchmarks/) directory includes a template-based benchmark where you generate two implementations (with and without the skill) and compare latency side-by-side.

## Supported GLIDE Versions

- Node.js: `@valkey/valkey-glide` v1.0.0+
- Python: `valkey-glide` v1.0.0+
- Java: `io.valkey:valkey-glide` v1.0.0+
- Go: `valkey-glide/go` v1.0.0+
- PHP: `valkey-glide-php` v1.0.0+

**Note**: C# support will be added once the GLIDE C# client is released.

## Contributing

Contributions are welcome!

## Additional Resources

- [Valkey GLIDE Repository](https://github.com/valkey-io/valkey-glide)
- [GLIDE Wiki](https://glide.valkey.io/)
- [AZ Affinity Blog](https://valkey.io/blog/az-affinity-strategy/)
- [Benchmarks](https://github.com/valkey-io/valkey-glide/tree/main/benchmarks)
- [Examples](https://github.com/valkey-io/valkey-glide/tree/main/examples)

## Support

For issues or questions:
- Open an issue on [GitHub](https://github.com/valkey-io/valkey-samples/issues)
- Join the [Valkey Community](https://valkey.io/community/)
- Check the [GLIDE Wiki](https://glide.valkey.io/)
