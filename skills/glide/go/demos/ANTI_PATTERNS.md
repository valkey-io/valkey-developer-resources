# Go GLIDE Anti-Pattern Tests

This directory contains negative assertion tests that prove the anti-patterns documented in GO.md.

## Test Files

### `anti_patterns_test.go`
Proper Go test suite demonstrating anti-patterns and their correct alternatives.

**Run tests:**
```bash
go test -v anti_patterns_test.go
```

**Tests included:**

1. **TestUnsafeTypeAssertion** - Proves unsafe type assertions panic
   - ❌ `result.(string)` panics on wrong type
   - ✅ `if val, ok := result.(string); ok` is safe

2. **TestSafeTypeAssertion** - Proves safe type assertions work correctly
   - Handles mixed return types without panicking
   - Uses two-value form for safety

3. **TestMissingErrorCheck** - Demonstrates why error checking is critical
   - Shows nil client when error is ignored
   - Proves error checking catches connection failures

4. **TestContextCancellation** - Proves context cancellation works
   - Cancelled context causes operations to fail
   - Context errors are properly propagated

5. **TestBatchDereference** - Compile-time check for batch dereferencing
   - ✅ `client.Exec(ctx, *batch, true)` compiles
   - ❌ `client.Exec(ctx, batch, true)` won't compile

### `anti_patterns_demo.go`
Interactive demo showing anti-patterns with explanations.

**Run demo:**
```bash
go run anti_patterns_demo.go
```

## Test Results

All tests pass, proving:
- ✅ Unsafe type assertions cause panics (as expected)
- ✅ Safe type assertions prevent panics
- ✅ Missing error checks lead to nil clients
- ✅ Context cancellation works correctly
- ✅ Batch dereferencing is enforced at compile-time

## Related Documentation

See [GO.md](../GO.md) for:
- Complete anti-pattern documentation
- Best practices section
- Common pitfalls with solutions
