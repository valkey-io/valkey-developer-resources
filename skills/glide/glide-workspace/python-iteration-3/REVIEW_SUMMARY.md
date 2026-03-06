# Iteration 3 - Results Summary

## Critical Issue STILL Persists

Despite adding explicit pitfalls for `client.ft_search()` and `client.ft_create()`, the AI continues to generate these incorrect patterns.

### Affected Tests:
1. **vector-search-json**: Uses `await client.ft_search()` ❌
2. **create-index**: Uses `await client.ft_create()` ❌

### What We've Tried:
- ✅ Moved critical constraints to main python.md file
- ✅ Added "CRITICAL CONSTRAINTS" section at top
- ✅ Added explicit pitfalls in Common Pitfalls table
- ❌ **Still generating wrong code**

### Hypothesis:

The AI may be seeing `client.ft_search()` and `client.ft_create()` as **valid methods** in the GLIDE API documentation or examples. The skill is fighting against what the AI believes is the correct API.

### Verification Needed:

1. **Does GLIDE actually have these methods?** 
   - If `client.ft_search()` exists in the actual GLIDE API, then the skill is wrong
   - If it doesn't exist, we need to find where the AI is learning this pattern

2. **Search the skill for examples**:
   - Are there any code examples showing `client.ft_*()` methods?
   - Are there conflicting patterns in different sections?

3. **Check the actual GLIDE API**:
   - What is the correct way to call FT.SEARCH in Python GLIDE?
   - Is it `ft.search(client, ...)` or `client.ft_search(...)`?

### Recommendation:

Before running Iteration 4, we need to verify:
1. What is the **actual correct API** for GLIDE Python?
2. Are we documenting the right pattern?
3. If we are, why does the AI keep generating the wrong one?
