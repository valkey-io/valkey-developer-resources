# Consolidated Code Review: `cookbooks/dynamo` — Dynamo Cookbook

**Branch:** `cookbooks/dynamo`
**Last updated:** 2026-06-02
**Review scope:** commit 8abbda8 (all 5 files)

## Round 2 Verdict: PASS with minor fixes (4 Medium remaining)

### Resolved from Round 1 (all 6 Critical + 7 Medium fixed ✓)

The conceptual architecture is sound, but **all Dynamo SDK code examples are fabricated** — they don't match the real Dynamo API. The cookbook cannot be followed as written.

---

## ✅ Resolved (Round 2)

- ~~F-001: Fabricated Dynamo SDK~~ — Fixed: uses `python -m dynamo.frontend`/`python -m dynamo.vllm` CLI
- ~~F-002: `valkeys://` TLS scheme~~ — Fixed: uses `tls_enable: true` in extra_config
- ~~F-003: Fake Helm chart~~ — Fixed: uses `dynamo-platform` OCI chart + DynamoGraphDeployment CRD
- ~~F-004: Fake `aws elasticache generate-auth-token`~~ — Fixed: removed
- ~~F-005: Fake `dynamo serve` command~~ — Fixed: uses real CLI launch
- ~~F-006: False "scales to 0" claim~~ — Fixed: states minimum baseline
- ~~F-007 through F-013~~ — All fixed (connector, env vars, metrics, Content-Type, claims, citations)

## 🟡 Round 2 — Medium (Should Fix)

### R2-F01: meta.json still claims "sub-millisecond"
**File:** meta.json line 11
**Fix:** Change to "enabling low-latency cache lookups"

### R2-F02: K8s env vars use non-standard naming
**File:** 03-production-deployment.md lines 123-129
`L1_SIZE_GB`, `L2_ADAPTER` don't follow `LMCACHE_*` prefix convention.
**Fix:** Use `LMCACHE_MAX_LOCAL_CPU_SIZE`, `LMCACHE_REMOTE_URL`, etc.

### R2-F03: `--network host` + `-p 6379:6379` conflict
**File:** 01-getting-started.md lines 46-47
Docker ignores port mapping with host networking.
**Fix:** Remove `-p 6379:6379`

### R2-F04: Missing `valkey_mode: "cluster"` for ElastiCache Serverless
**File:** 03-production-deployment.md (TLS config section)
**Fix:** Add `"valkey_mode": "cluster"` to extra_config JSON.

---

## 🔴 Critical — Previously Open (ALL RESOLVED)

### F-001: Entire Dynamo Python SDK API is fabricated (High)
**File:** `01-getting-started.md` lines 65–98  
**Also:** `02-kv-cache-routing.md` lines 41–70  
**Reviewers:** domain, antipattern

`dynamo.sdk`, `@service`, `DynamoConfig`, `depends()`, `VllmEngine`, `KvRouter`, `IndexConfig` — none of these exist in NVIDIA Dynamo. The real API uses:
- `@dynamo_worker()` decorator with `DistributedRuntime`
- CLI-based launch: `python -m dynamo.frontend --router-mode kv`
- K8s deployment via `DynamoGraphDeploymentRequest` CRDs

**Fix:** Rewrite all Python examples to use the actual Dynamo API (v1.1.0+).

---

### F-002: `valkeys://` TLS scheme does not exist in LMCache (High)
**File:** `03-production-deployment.md` lines 66, 70, 88, 109, 118, 200, 207  
**Reviewers:** domain

LMCache does NOT use a `valkeys://` URL scheme for TLS. TLS is enabled via `tls_enable: true` in `extra_config`. The URL is always `valkey://`.

**Fix:** Replace all `valkeys://` with `valkey://` + `LMCACHE_EXTRA_CONFIG={"tls_enable": true}`.

---

### F-003: `dynamo/dynamo` Helm chart does not exist (High)
**File:** `03-production-deployment.md` lines 77–80, 123  
**Reviewers:** domain, antipattern

The real Dynamo K8s deployment uses `dynamo-platform` OCI chart from `oci://helm.ngc.nvidia.com/nvidia/ai-dynamo/charts/dynamo-platform` + `DynamoGraphDeploymentRequest` CRDs.

**Fix:** Replace with actual deployment approach (platform chart + DGDR YAML).

---

### F-004: `aws elasticache generate-auth-token` does not exist (High)
**File:** `03-production-deployment.md` line 208  
**Reviewers:** domain, antipattern

This CLI command is fabricated. ElastiCache IAM auth uses SDK-based presigned tokens.

**Fix:** Remove. Show `valkey_username`/`valkey_password` in LMCache extra_config, or link to IAM auth docs.

---

### F-005: `dynamo serve dynamo_graph:Frontend` command does not exist (High)
**File:** `01-getting-started.md` line 122  
**Reviewers:** domain

Real Dynamo launch: `python -m dynamo.frontend` + `python -m dynamo.vllm`.

**Fix:** Replace with actual launch commands.

---

### F-006: "scales to 0 at idle" is false (Medium)
**File:** `03-production-deployment.md` line 217  
**Reviewers:** antipattern

ElastiCache Serverless has a minimum baseline charge. It does NOT scale to zero.

**Fix:** Remove claim or replace with "(scales down at low traffic, minimum baseline applies)".

---

## 🟡 Medium — Should Fix

### F-007: Wrong KV connector for Dynamo
**File:** `01-getting-started.md` line 94  
The correct connector for Dynamo is `LMCacheMPConnector` (with `lmcache server` sidecar), not `LMCacheConnectorV1`.

### F-008: Fabricated env vars `DYNAMO_REPORT_CACHE_STATE`, `DYNAMO_REPORT_INTERVAL_MS`
**File:** `02-kv-cache-routing.md` lines 88–89  
These don't exist. Dynamo uses `DYN_`-prefixed vars. KV event reporting is automatic with `--router-mode kv`.

### F-009: Fabricated metric names throughout
**Files:** `02-kv-cache-routing.md` lines 125–127, `03-production-deployment.md` lines 160–163  
`dynamo_kv_router_cache_hit_ratio`, `lmcache_remote_latency_ms`, etc. are unverifiable.
**Fix:** Mark as illustrative or verify against actual metrics endpoints.

### F-010: Missing Content-Type header in curl commands
**File:** `02-kv-cache-routing.md` lines 98, 105  
OpenAI-compatible APIs reject non-JSON content types. `01-getting-started.md` correctly includes the header.

### F-011: "sub-millisecond" claim without citation
**File:** `01-getting-started.md` line 3  
Network-based Valkey lookups are typically 1–5ms with TLS. Unqualified "sub-millisecond" is misleading.

### F-012: "11.7× read/write ratio" without source
**Files:** `02-kv-cache-routing.md` line 133, `03-production-deployment.md` line 181  
Needs a citation link to the NVIDIA blog/paper.

### F-013: Python forward reference — `Worker` used before defined
**File:** `01-getting-started.md` lines 81, 88  
`depends(Worker)` at line 81 references `Worker` class defined at line 88. This is a NameError in standard Python.

---

## 🟢 Low — Nice to Have

### F-014: Cost estimates without date/region
**File:** `03-production-deployment.md` lines 215–217  
Add "As of [date], in us-east-1" and link to pricing calculator.

### F-015: `:latest` container tags
**File:** `01-getting-started.md` lines 46, 55, 121  
Pin to specific versions for reproducibility.

### F-016: Placeholder values (sg-xxxx) not visually called out
**File:** `03-production-deployment.md` lines 44–45  
Add inline comments: `# ← Replace with your values`

### F-017: No error handling/troubleshooting guidance
**Files:** All three cookbooks  
No guidance on what to do when commands fail.

---

## ✅ Positives

- Conceptual architecture is accurate (multi-worker + shared L2 Valkey via LMCache)
- Tiered caching explanation (GPU → CPU L1 → Valkey L2) is clear and correct
- WORM access pattern description is insightful
- LMCache env var names (LMCACHE_CHUNK_SIZE, LMCACHE_REMOTE_URL, etc.) are real
- ElastiCache Serverless `create-serverless-cache` CLI is correct
- Hardware disclaimer in README is honest and appropriate
- Architecture diagrams are clear and professional
- Comparison tables (HNSW vs FLAT, routing strategies) add real value

## Checklist Assessment

| Area | Status | Notes |
|------|--------|-------|
| Functionality | ❌ | Code examples won't work — fabricated API |
| Code Quality | ❌ | Invalid Python (forward ref), wrong connectors |
| Testing | ⚠️ | Not validated on hardware (disclosed) |
| Security | ⚠️ | Fabricated auth command, but TLS concept correct |
| Performance | ⚠️ | Claims unverified but conceptually sound |
| Documentation | ✅ | Clear writing, good structure, honest disclaimers |
