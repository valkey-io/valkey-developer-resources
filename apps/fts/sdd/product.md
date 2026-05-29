# Product Overview — FlicEnjoyer

## Purpose

FlicEnjoyer is a streaming platform sample app that showcases Valkey as a high-performance caching layer over a traditional database, combined with ValkeySearch 1.2 Full Text Search (FTS) for sub-10ms search. It demonstrates how adding Valkey to an existing PostgreSQL-backed application dramatically improves read latency — with benchmarks proving the performance uplift. It also showcases ValkeySearch FTS for typeahead and fuzzy search, user session management with watch history and resume points, and offline analytics using FT.AGGREGATE. Contributed to the valkey-io/Valkey-Samples repository as a developer reference.

It is a fictitious movie / TV show tracking application that a "flic" enjoyer would use to track their watch history and search for new shows / movies to watch.

## Target Users

- Valkey developers evaluating Valkey as a caching layer to accelerate database-backed applications
- Teams considering ValkeySearch FTS as an alternative to external search engines
- Developers wanting to see cache-aside patterns with valkey-glide in practice

## Current Scope

- PostgreSQL as the primary datastore (source of truth) for catalog metadata and watch history
- Valkey as a cache-aside layer providing sub-millisecond reads for cached data
- ValkeySearch 1.2 FTS indexes (populated from DB) for typeahead, fuzzy search, and aggregation
- Performance benchmarks comparing DB-direct vs Valkey-cached latency — proving the value of the caching layer
- Curated dataset: 50–100 catalog entries and proportional watch history records across multiple simulated users, sufficient to demonstrate performance differences
- Typeahead search powered by FTS prefix matching (<10ms) and fuzzy search for misspelling tolerance
- User identified by a locally persisted profile: on first launch, the app prompts for the user's full name and generates a unique ID (UUID). This profile is stored locally and loaded on subsequent runs.
- Watch history and resume timestamps stored in PostgreSQL (source of truth) with Valkey cache for fast retrieval
- Session hydration on startup syncs DB data into Valkey cache and FTS indexes
- Resume playback retrieving correct timestamps with sub-millisecond latency (from cache)
- Offline aggregation reports via FT.AGGREGATE: content ranked by viewer count, catalog summary grouped by genre
- README with setup instructions, architecture overview, and walkthrough of each feature
- *Upload* new videos with thumbnail, title and description (with optional tags)
- *(Experimental)* Auto-generate thumbnail by extracting a frame from the uploaded video

## Key Design Constraints

- Must use ValkeySearch 1.2 and valkey-glide Java client library (local build from branch `edlng/vss-1.2-commands` at `../../../valkey-glide` until 2.4 release)
- PostgreSQL as primary datastore — Valkey is a caching/search acceleration layer, not the source of truth
- No Redis dependency — Valkey-native from the ground up

## Non-Goals

- Production-grade authentication, authorization, or login flows
- Streaming infrastructure, or a fully functional video player
- Deployment automation or CI/CD pipelines
- Fixed stand-in videos for playback (i.e. no seed data)
- Deleting or updating uploaded videos (upload is append-only for now)

## Future Phases

- Additional aggregation report types
- Multi-user concurrent session demos
- Vector search / hybrid query examples alongside FTS

## Success Criteria

- Typeahead returns results within 10ms using FTS prefix queries
- Fuzzy search handles misspellings gracefully
- Resume retrieval achieves sub-millisecond latency (from Valkey cache)
- Benchmarks clearly demonstrate Valkey cache speedup over direct DB access (target: 10x+ improvement)
- FT.AGGREGATE produces at least two report types (viewer-ranked content, genre-grouped catalog)
- All performance benchmarks documented with dataset size noted

## References

- Jira Story: AEA-325
- Repository: https://github.com/valkey-io/Valkey-Samples
- ValkeySearch: https://github.com/valkey-io/Valkey-Search
