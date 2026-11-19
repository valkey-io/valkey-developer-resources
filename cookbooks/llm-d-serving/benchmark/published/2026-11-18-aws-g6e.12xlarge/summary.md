Measured 2026-11-18T14:26:34Z on aws g6e.12xlarge in ap-northeast-1: 4x NVIDIA L40S 45 GiB, driver 595.112.07; model Qwen/Qwen3-8B, vLLM 0.33.0, lmcache 0.5.7.post1; commit 1acb113629e0.

| Configuration | Concurrency | Runs | TTFT p50 ms | TTFT p90 ms | TTFT p99 ms | Requests/s | Prompt tokens from GPU prefix cache | Prompt tokens from LMCache (L1 or Valkey) | Failed requests |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| random-no-lmcache | 8 | 3 | 411 (411–412) | 714 (683–737) | 1,072 (1,025–1,101) | 3.19 (3.19–3.20) | 15% (14–15%) | 0% | 0 |
| random-no-lmcache | 16 | 3 | 428 (427–428) | 1,015 (955–1,045) | 1,625 (1,534–1,630) | 4.85 (4.81–4.87) | 15% (14–15%) | 0% | 0 |
| random-no-lmcache | 32 | 3 | 512 (477–567) | 1,376 (1,313–1,544) | 2,577 (2,568–2,880) | 6.68 (6.42–6.76) | 15% (14–15%) | 0% | 0 |
| random | 8 | 3 | 388 (372–408) | 537 (535–548) | 793 (757–880) | 4.01 (3.99–4.02) | 14% (14–16%) | 81% (79–81%) | 1 |
| random | 16 | 3 | 462 (461–491) | 673 (659–764) | 1,540 (1,451–1,624) | 7.27 (7.18–7.29) | 14% (14–14%) | 86% (86–86%) | 0 |
| random | 32 | 3 | 1,088 (1,049–1,218) | 2,279 (2,197–2,868) | 3,599 (3,560–3,951) | 10.13 (9.81–10.22) | 15% (14–15%) | 85% (85–86%) | 0 |
| approximate | 8 | 3 | 284 (283–286) | 502 (498–506) | 700 (690–747) | 4.21 (4.19–4.21) | 46% (46–46%) | 50% (49–50%) | 0 |
| approximate | 16 | 3 | 359 (346–370) | 575 (559–592) | 1,178 (1,034–1,185) | 7.61 (7.58–7.62) | 45% (45–45%) | 55% (55–55%) | 0 |
| approximate | 32 | 3 | 546 (523–576) | 1,470 (1,210–1,499) | 3,069 (2,701–3,163) | 12.28 (12.23–12.51) | 43% (42–44%) | 56% (56–57%) | 0 |
| precise-memory | 8 | 3 | 275 (257–276) | 510 (498–511) | 653 (634–655) | 4.21 (4.20–4.22) | 64% (63–64%) | 32% (32–33%) | 0 |
| precise-memory | 16 | 3 | 327 (325–331) | 532 (530–540) | 920 (907–989) | 7.69 (7.66–7.72) | 63% (63–63%) | 37% (37–37%) | 0 |
| precise-memory | 32 | 3 | 382 (380–395) | 745 (688–750) | 2,098 (2,053–2,170) | 13.34 (13.27–13.35) | 62% (62–63%) | 38% (37–38%) | 0 |
| precise-valkey | 8 | 3 | 264 (254–277) | 505 (492–517) | 655 (620–686) | 4.21 (4.21–4.21) | 63% (63–64%) | 32% (32–33%) | 0 |
| precise-valkey | 16 | 3 | 325 (317–332) | 528 (511–543) | 995 (917–1,015) | 7.72 (7.67–7.74) | 63% (63–63%) | 37% (37–37%) | 0 |
| precise-valkey | 32 | 3 | 390 (365–400) | 734 (649–749) | 2,141 (2,122–2,234) | 13.33 (13.29–13.45) | 63% (61–63%) | 37% (37–39%) | 0 |

Each cell is the median of the runs, with the spread (min–max) in brackets. Prompt-token shares come from vLLM's prefix_cache_hits (local) and external_prefix_cache_hits (LMCache: its L1 memory or Valkey) counters, as shares of prompt_tokens. The Valkey table below splits LMCache's lookups into chunks found in L1 and chunks loaded from Valkey.

### Valkey after each run

Measured 2026-11-18T14:26:34Z on aws g6e.12xlarge in ap-northeast-1: 4x NVIDIA L40S 45 GiB, driver 595.112.07; model Qwen/Qwen3-8B, vLLM 0.33.0, lmcache 0.5.7.post1; commit 1acb113629e0.

| Configuration | Run | Valkey used_memory GiB | used_memory_peak GiB | maxmemory GiB | KV keys (db 0) | Index keys (db 1) | Index keys at start (db 1) | OOM rejections | Lookup chunks from L1 | Lookup chunks from Valkey | Prefetch p50 ms |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| random-no-lmcache | 1 | 0.0 | 31.6 | 192 | 0 | 0 | 0 | 0 | n/a | n/a | n/a |
| random-no-lmcache | 2 | 0.0 | 31.6 | 192 | 0 | 0 | 0 | 0 | n/a | n/a | n/a |
| random-no-lmcache | 3 | 0.0 | 31.6 | 192 | 0 | 0 | 0 | 0 | n/a | n/a | n/a |
| random | 1 | 150.0 | 150.4 | 192 | 3840 | 0 | 0 | 0 | 10,797 | 24,526 | 214 |
| random | 2 | 150.0 | 150.4 | 192 | 3840 | 0 | 0 | 0 | 10,637 | 25,108 | 225 |
| random | 3 | 150.0 | 150.4 | 192 | 3840 | 0 | 0 | 0 | 10,736 | 24,883 | 212 |
| approximate | 1 | 150.0 | 150.4 | 192 | 3840 | 0 | 0 | 0 | 5,869 | 16,117 | 180 |
| approximate | 2 | 150.0 | 150.4 | 192 | 3840 | 0 | 0 | 0 | 6,275 | 15,667 | 173 |
| approximate | 3 | 150.0 | 150.4 | 192 | 3840 | 0 | 0 | 0 | 5,702 | 16,464 | 175 |
| precise-memory | 1 | 150.0 | 150.4 | 192 | 3840 | 0 | 0 | 0 | 4,121 | 10,343 | 56 |
| precise-memory | 2 | 150.0 | 150.4 | 192 | 3840 | 0 | 0 | 0 | 4,115 | 10,216 | 56 |
| precise-memory | 3 | 150.0 | 150.4 | 192 | 3840 | 0 | 0 | 0 | 4,213 | 10,205 | 57 |
| precise-valkey | 1 | 150.0 | 150.4 | 192 | 3840 | 25730 | 0 | 0 | 4,192 | 10,407 | 56 |
| precise-valkey | 2 | 150.0 | 150.4 | 192 | 3840 | 25521 | 0 | 0 | 4,212 | 10,216 | 55 |
| precise-valkey | 3 | 150.0 | 150.4 | 192 | 3840 | 25713 | 0 | 0 | 4,224 | 10,284 | 56 |

used_memory after a run is close to that run's peak: nothing is deleted during a run (noeviction), and database 0 is flushed before the next. used_memory_peak is since Valkey started, so it covers every run so far.
