# C# GLIDE Status

## Current Status (2026-02-27)

**C# GLIDE is available but in early development:**

- **Repository:** https://github.com/valkey-io/valkey-glide-csharp
- **Latest Release:** v0.9.0 (September 17, 2025)
- **NuGet Package:** Not yet published to NuGet.org
- **Documentation:** https://glide.valkey.io/languages/csharp (shows "Coming Soon")

## Key Findings

1. **Active Development:** 10 contributors, 20 stars, recent release
2. **Rust Core:** Built on Rust core like other GLIDE clients
3. **Async/Await:** Supports .NET async patterns
4. **Features:** Connection pooling, pipeline support, pub/sub
5. **Not Production Ready:** v0.9.0 indicates pre-1.0 status

## Installation

Since not on NuGet yet, installation requires building from source:

```bash
git clone https://github.com/valkey-io/valkey-glide-csharp.git  # ✅ DONE
cd valkey-glide-csharp
# Follow DEVELOPER.md instructions
```

The repository is available at `../../../../valkey-glide-csharp`

## Decision

**Given the early status of C# GLIDE (v0.9.0, not on NuGet), we should:**

1. **Document the current state** in the plan
2. **Create a placeholder CSharp.md** with:
   - Status note about v0.9.0
   - Link to GitHub repository
   - Basic patterns from README
   - Note that full skill will be developed when v1.0 is released
3. **Skip full POC development** until C# GLIDE reaches v1.0 and NuGet availability

This aligns with the skill development philosophy: focus on production-ready, stable clients.
