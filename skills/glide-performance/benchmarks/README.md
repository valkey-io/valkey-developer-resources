# GLIDE Performance Benchmarks

This directory contains anti-pattern examples demonstrating common performance issues in Valkey GLIDE client usage. These examples serve two purposes:

1. Provide the AI skill with concrete code patterns to match against during reviews
2. Enable prompt-based evaluation of the skill's detection accuracy

## Directory Structure

```
benchmarks/
├── README.md                          # This file
├── tests/                             # Anti-pattern & best-practice code files
│   ├── node-antipatterns.js           # Node.js/TypeScript
│   ├── python-antipatterns.py         # Python async/sync
│   ├── java-antipatterns.java         # Java
│   ├── go-antipatterns.go             # Go
│   └── php-antipatterns.php           # PHP
└── expected/
    └── RESULTS.md                     # Answer key (DO NOT read before review)
```

## Anti-Pattern Files

- `tests/node-antipatterns.js` - Node.js/TypeScript anti-patterns
- `tests/python-antipatterns.py` - Python async/sync anti-patterns
- `tests/java-antipatterns.java` - Java anti-patterns
- `tests/go-antipatterns.go` - Go anti-patterns
- `tests/php-antipatterns.php` - PHP anti-patterns

Each file contains realistic code showing per-request client creation, missing timeouts, sequential operations, blocking commands on shared clients, missing TLS, and inefficient data access patterns. The files also include known-good code and subtle edge cases to test false-positive resistance and nuanced analysis.

## Evaluating the Skill

Since this is an AI skill (not a runtime library), "testing" means prompting an AI agent with the skill loaded and checking whether it correctly identifies anti-patterns and recommends fixes.

### Quick Evaluation

Pick any anti-pattern file from `tests/` and paste a class into your AI tool with the skill installed:

```
Review this code for Valkey performance issues:

<paste a class from one of the anti-pattern files>
```

The AI should identify the relevant anti-patterns without you pointing them out.

### Structured Evaluation (Blind Exam)

For a thorough, repeatable assessment, follow this two-phase process:

#### Phase 1: Blind Review

Prompt the AI with the skill loaded. Give it an entire anti-pattern file from `tests/` (or specific classes) and ask for a review. The AI must NOT read `expected/RESULTS.md` during this phase.

Example prompt:

```
Review the following code for Valkey GLIDE performance issues. For each class/function,
list every anti-pattern you find. Also identify any code that follows best practices
and should NOT be flagged.

<paste the contents of one of the files from tests/>
```

Save the AI's output.

#### Phase 2: Self-Scoring

After the AI completes its review, ask it to score itself:

```
Now read benchmarks/expected/RESULTS.md and score your review against the answer key.

IMPORTANT: Calculate these metrics:
- Detection rate: (correctly flagged anti-patterns) / (total known anti-patterns)
- False positive rate: (incorrectly flagged good code) / (total good code sections)

Target: detection rate ≥ 90%, false positive rate = 0%

Present results as a table showing each class, expected findings, your findings,
and whether each was detected or missed.
```

#### Why This Order Matters

The AI must complete its review BEFORE seeing `expected/RESULTS.md`. If it reads the answer key first, it will just parrot the expected findings back — that tests reading comprehension, not the skill's effectiveness. The blind-then-score approach tests whether the skill actually enables the AI to reason about code semantics.

### What to Look For

Beyond raw detection rates, pay attention to:

- **Nuanced analysis on edge cases**: Classes like `ConfigHydrator` are singletons (good for client reuse) but missing timeout/retry config. The AI should give partial credit, not blanket pass/fail.
- **Semantic reasoning vs name matching**: Classes use non-obvious names like `stashBlob`, `hydrateNamespace`, `probeExistence`. The AI should reason about what the code does, not just pattern-match on names like `createClient` or `getWithoutTimeout`.
- **Mixed-pattern classes**: Some classes have both good and bad patterns. The AI should identify the specific issues without dismissing the entire class.

### Running After Skill Updates

Re-run the blind exam after each skill update to catch regressions. Compare detection rates across versions to track whether changes improved or degraded the skill's effectiveness.

## Related Resources

- [GLIDE Official Benchmarks](https://github.com/valkey-io/valkey-glide/tree/main/benchmarks) - General client performance comparisons
- [AZ Affinity Blog](https://valkey.io/blog/az-affinity-strategy/) - Cost optimization strategies
- [Skill Reference Patterns](../reference/) - Best practice implementations
