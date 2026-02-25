# PHP GLIDE Skill Development Plan

## Overview
Develop comprehensive and specifically PHP GLIDE skill documentation by creating working examples, gathering lessons learned, and distilling patterns into a terse reference guide.

## 1. Environment Setup
- Install PHP GLIDE client dependency
- Create PHP project structure
- **Testing host**: Found in `VALKEY_HOST` environment variable (local development only)
- **Documentation host**: `localhost` (final examples)

*Build and run all PHP demos via a docker container, see [README.md](README.md) for instructions.

## 2. Core POC Examples (3 demos)
Create in `php/demos/` directory:
- **basic-operations/**: Connect, set/get, error handling
- **batch-pipeline/**: Atomic transactions vs non-atomic pipelines
- **cluster-operations/**: Multi-node routing, hash slot constraints

Skip vector search demos, GLIDE for PHP does not support the FT module features yet.

*POCs use Valkey host from `VALKEY_HOST` environment variable and port `6379` for testing, final docs use `localhost`*

## 3. Document Lessons Learned
Create `php/LESSONS_LEARNED.md` with:
- Import patterns and package structure
- API calling conventions (method vs function style)
- Error handling specifics (exception types)
- Type system differences (generics, nullability)
- Async patterns (CompletableFuture vs callbacks)
- Byte handling for vectors and results
- Common pitfalls and gotchas
- Side-by-side Node.js vs PHP comparisons

## 4. Flesh Out PHP.md
Mirror Node.js structure, and Java structure to a lesser extent, using lessons learned:
- Package selection (correct vs incorrect)
- Client creation patterns (sync/async, cluster/standalone)
- Batch/pipeline patterns with retry strategies
- Any relevant Node-specific syntactical enhancements
- Testing patterns (mocking)
- Common pitfalls section
- Summary checklist

## 5. Validation
- Test all code examples against Valkey host from `VALKEY_HOST` environment variable and port `6379`
- Verify patterns against GLIDE PHP docs
- Cross-reference with Node.js patterns for consistency, and Java patterns to a lesser extent where relevant and where Node.js does not provide any clear pattern
- Ensure all "TBD" or "TODO" placeholders in skill documents are either removed or populated

## 6. Cleanup Phase (requires approval)
**Before removal, present to user:**
- List of interim files to remove: `php/demos/`, `php/LESSONS_LEARNED.md`
- Confirmation that essential patterns are captured in `PHP.md`
- Rationale: Keep skill terse, agents can infer from examples in final doc

**After approval:**
- Remove demo projects
- Remove lessons learned document
- Keep only `php/PHP.md` with distilled patterns

## Estimated Effort
4-6 hours for POCs + documentation + 30min cleanup

## Success Criteria
- All POCs run successfully against Valkey
- PHP.md mirrors Java and Node.js structures and completeness
- Final skill is terse yet comprehensive
- No interim artifacts remain after cleanup
