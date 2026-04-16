# Product Overview — FlicEnjoyer

## Purpose

FlicEnjoyer is a streaming platform sample app that showcases ValkeySearch 1.2 Full Text Search (FTS) capabilities end-to-end. It showcases catalog search with typeahead and fuzzy matching, user session management with watch history and resume points, and offline analytics using FT.AGGREGATE. Contributed to the valkey-io/Valkey-Samples repository as a developer reference.

It is a fictitious movie / TV show tracking application that a "flic" enjoyer would use to track their watch history and search for new shows / movies to watch.

## Target Users

- Valkey developers evaluating ValkeySearch FTS for real-world use cases
- Teams considering Valkey/ElastiCache for search, session management, and analytics

## Current Scope

- Movie/show catalog stored in Valkey Hash with FTS indexes on title, genre, description, and tags (FT.CREATE)
- Curated dataset: 50–100 catalog entries and proportional watch history records across multiple simulated users, sufficient to demonstrate Valkey's search and aggregation performance
- Typeahead search powered by FTS prefix matching (<10ms) and fuzzy search for misspelling tolerance
- User identified by a locally persisted profile: on first launch, the app prompts for the user's full name and generates a unique ID (UUID). This profile is stored locally and loaded on subsequent runs.
- Watch history and resume timestamps stored in Valkey per userId — first launch starts with an empty session; state accumulates as the user interacts with the app
- Session hydration on startup loads existing watch history from Valkey using the persisted userId
- Resume playback retrieving correct timestamps with sub-millisecond latency
- Offline aggregation reports via FT.AGGREGATE: content ranked by viewer count, catalog summary grouped by genre
- Performance benchmarks documented for search, resume, and aggregation operations at scale
- README with setup instructions, architecture overview, and walkthrough of each feature
- *Upload* new videos with thumbnail, title and description (with optional tags)
- *(Experimental)* Auto-generate thumbnail by extracting a frame from the uploaded video

## Key Design Constraints

- Must use ValkeySearch 1.2 and valkey-glide Java client library (local build from branch `edlng/vss-1.2-commands` at `../../../valkey-glide` until 2.4 release)
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
- Resume retrieval achieves sub-millisecond latency
- FT.AGGREGATE produces at least two report types (viewer-ranked content, genre-grouped catalog)
- All performance benchmarks documented with dataset size noted

## References

- Jira Story: AEA-325
- Repository: https://github.com/valkey-io/Valkey-Samples
- ValkeySearch: https://github.com/valkey-io/Valkey-Search
