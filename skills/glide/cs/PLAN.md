# C-Sharp GLIDE Skill Development Plan

## Overview
Develop comprehensive and specifically C-Sharp GLIDE skill documentation by creating working examples, gathering lessons learned, and distilling patterns into a terse reference guide.

## 1. Environment Setup
- Install C-Sharp GLIDE client dependency
- Create C-Sharp project structure
- **Testing host**: Found in `VALKEY_HOST` environment variable (local development only)
- **Documentation host**: `localhost` (final examples)

*Build and run all C-Sharp demos via a docker container, see [demos/README.md](demos/README.md) for instructions and [demos/validate.sh](demos/validate.sh) for specific validation script.

## 2. Core POC Examples (4 demos)
Create each as sub-directories of `cs/demos/`, and drop associated demos in:
- **basic-operations/**: Connect, set/get, error handling
- **batch-pipeline/**: Atomic transactions vs non-atomic pipelines
- **vector-search/**: FT.CREATE index, add documents, FT.SEARCH with KNN
- **cluster-operations/**: Multi-node routing, hash slot constraints

*POCs use Valkey host from `VALKEY_HOST` environment variable and port `6379` for testing, final docs use `localhost`*
*For vector-search API, refer to GLIDE API source files at `../../../valkey-glide/node/src/server-modules/` for a reference

## 3. Document Lessons Learned
Create `cs/LESSONS_LEARNED.md` with:
- Import patterns and package structure
- API calling conventions (method vs function style)
- Error handling specifics (exception types)
- Type system differences (generics, nullability)
- Async patterns (CompletableFuture vs callbacks)
- Byte handling for vectors and results
- Common pitfalls and gotchas
- Side-by-side Node.js vs C-Sharp comparisons

## 4. Flesh Out CSharp.md
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
- Verify patterns against GLIDE C-Sharp docs
- Cross-reference with Node.js patterns for consistency, and Java patterns to a lesser extent where relevant and where Node.js does not provide any clear pattern
- Ensure all "TBD" or "TODO" placeholders in skill documents are either removed or populated
- Update 'Language-Specific Guides' section in `SKILL.md` with C-Sharp details 

## 6. Cleanup Phase (requires approval)
**Before removal, present to user:**
- List of interim files to remove: `cs/demos/`, `cs/LESSONS_LEARNED.md`
- Confirmation that essential patterns are captured in `CSharp.md`
- Rationale: Keep skill terse, agents can infer from examples in final doc

**After approval:**
- Remove demo projects
- Remove lessons learned document
- Keep only `cs/CSharp.md` with distilled patterns

## Estimated Effort
4-6 hours for POCs + documentation + 30min cleanup

## Success Criteria
- All POCs run successfully against Valkey
- CSharp.md mirrors Java and Node.js structures and completeness
- Final skill is terse yet comprehensive
- No interim artifacts remain after cleanup
