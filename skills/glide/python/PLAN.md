# Python GLIDE Skill Development Plan

## Overview
Develop comprehensive Python-specific GLIDE skill documentation by creating working examples, gathering lessons learned, and distilling patterns into a terse reference guide.

## 1. Environment Setup
- Install Python GLIDE client dependency
- Create Python project structure
- **Testing host**: Found in `VALKEY_HOST` environment variable (local development only)
- **Documentation host**: `localhost` (final examples)

### Testing TLS connectivity
TLS connectivity can be tested using the CLI tool / commands:
```#!shell
cd ../../../../valkey/tls
../src/valkey-cli -h $VALKEY_HOST -p 6480 \
    --tls --cert valkey.crt --key valkey.key --cacert valkey.crt \
    --sni $VALKEY_HOST
```

## 2. Core POC Examples (7 demos)
Create each as sub-directories of `python/demos/`, and drop associated demos in:
- **basic-operations/**: Connect, set/get, error handling
- **batch-pipeline/**: Atomic transactions vs non-atomic pipelines, retry strategies
- **vector-search/**: FT.CREATE index, add documents, FT.SEARCH with KNN
- **cluster-operations/**: Multi-node routing, hash slot constraints
- **authentication/**: Basic auth via `ServerCredentials`, TLS/SSL, AWS IAM auth

*POCs use Valkey host from `VALKEY_HOST` environment variable for testing, and use the following for specific testing:*
- All core operations use port `6379`
- Cluster operations use port `7000`
- Authentication and TLS uses port `6479`

The final documentation output uses `localhost`

**NOTE:** TLS testing will require using insecure from the client side (ignore server certificate validation), but 
document both secure and insecure certificate client connection modes in the skill.

**NOTE:** AWS IAM auth cannot be runtime tested, but a demo should be created none-the-less for validation, and it should
at least compile without errors, and it should run without any errors specific to AWS. 

**NOTE:** Batch operations retry strategies should show examples of when to use `retryServerError`, `retryConnectionError`, and when to avoid both.

## 3. Document Lessons Learned
Create `python/LESSONS_LEARNED.md` with:
- Import patterns and package structure
- API calling conventions (method vs function style)
- Error handling specifics (exception types)
- Type system differences (generics, nullability)
- Async patterns (async/await)
- Byte handling for vectors and results
- Common pitfalls and gotchas
- Authentication and TLS testing results

## 4. Flesh Out PYTHON.md
Using lessons learned:
- Package selection (correct vs incorrect)
- Client creation patterns (sync/async, cluster/standalone)
- Authentication and TLS configuration
- Batch/pipeline patterns with retry strategies
- FT.SEARCH command pattern with code examples
- FT.CREATE command pattern with schema building
- Testing patterns (mocking)
- Common pitfalls section
- Summary checklist

## 5. Validation
- Test all code examples against Valkey host from `VALKEY_HOST` environment variable and port `6379`
- Verify patterns against GLIDE Python docs
- Cross-reference with other language patterns for consistency
- Ensure all "TBD" or "TODO" placeholders in skill documents are either removed or populated
- Test authentication with password-protected Valkey instance

## 6. Cleanup Phase (requires approval)
**Before removal, present to user:**
- List of interim files to remove: `python/demos/`, `python/LESSONS_LEARNED.md`
- Confirmation that essential patterns are captured in `PYTHON.md`
- Rationale: Keep skill terse, agents can infer from examples in final doc

**After approval:**
- Remove demo projects
- Remove lessons learned document
- Keep only `python/PYTHON.md` with distilled patterns

## Estimated Effort
4-6 hours for POCs + documentation + 30min cleanup

## Success Criteria
- All POCs run successfully against Valkey
- PYTHON.md is comprehensive with ✅/❌ examples
- Authentication patterns validated
- Anti-patterns documented
- Final skill is terse yet comprehensive
- No interim artifacts remain after cleanup
