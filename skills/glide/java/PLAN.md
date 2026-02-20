# Java GLIDE Skill Development Plan

## Overview
Develop comprehensive Java-specific GLIDE skill documentation by creating working examples, gathering lessons learned, and distilling patterns into a terse reference guide.

## 1. Environment Setup
- Install Java GLIDE client dependency
- Create Maven/Gradle project structure
- **Testing host**: Found in `VALKEY_HOST` environment variable (local development only)
- **Documentation host**: `localhost` (final examples)

## 2. Core POC Examples (4 demos)
Create in `java/demos/` directory:
- **basic-operations/**: Connect, set/get, error handling
- **batch-pipeline/**: Atomic transactions vs non-atomic pipelines
- **vector-search/**: FT.CREATE index, add documents, FT.SEARCH with KNN
- **cluster-operations/**: Multi-node routing, hash slot constraints

*POCs use Valkey host from `VALKEY_HOST` environment variable and port `6379` for testing, final docs use `localhost`*

## 3. Document Lessons Learned
Create `java/LESSONS_LEARNED.md` with:
- Import patterns and package structure
- API calling conventions (method vs function style)
- Error handling specifics (exception types)
- Type system differences (generics, nullability)
- Async patterns (CompletableFuture vs callbacks)
- Byte handling for vectors and results
- Common pitfalls and gotchas
- Side-by-side Python vs Java comparisons

## 4. Flesh Out JAVA.md
Mirror Python structure using lessons learned:
- Package selection (correct vs incorrect)
- Client creation patterns (sync/async, cluster/standalone)
- FT.SEARCH command pattern with code examples
- FT.CREATE command pattern with schema building
- Batch/pipeline patterns with retry strategies
- Distance metrics mapping
- Type hints and generics
- Testing patterns (mocking)
- Common pitfalls section
- Summary checklist

## 5. Validation
- Test all code examples against Valkey host from `VALKEY_HOST` environment variable and port `6379`
- Verify patterns against GLIDE Java docs
- Cross-reference with Python patterns for consistency
- Ensure all "TBD" or "TODO" placeholders in skill documents are either removed or populated

## 6. Cleanup Phase (requires approval)
**Before removal, present to user:**
- List of interim files to remove: `java/demos/`, `java/LESSONS_LEARNED.md`
- Confirmation that essential patterns are captured in `JAVA.md`
- Rationale: Keep skill terse, agents can infer from examples in final doc

**After approval:**
- Remove demo projects
- Remove lessons learned document
- Keep only `java/JAVA.md` with distilled patterns

## Estimated Effort
4-6 hours for POCs + documentation + 30min cleanup

## Success Criteria
- All POCs run successfully against Valkey
- JAVA.md mirrors Python structure and completeness
- Final skill is terse yet comprehensive
- No interim artifacts remain after cleanup
