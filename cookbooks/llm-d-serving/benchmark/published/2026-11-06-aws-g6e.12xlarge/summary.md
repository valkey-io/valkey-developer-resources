Measured 2026-11-06T20:03:31Z on aws g6e.12xlarge in ap-northeast-1: 4x NVIDIA L40S 45 GiB, driver 595.112.07; model Qwen/Qwen3-8B, vLLM 0.30.0, lmcache 0.5.5; commit 1acc7860fa7e.

| Configuration | Concurrency | Runs | TTFT p50 ms | TTFT p90 ms | TTFT p99 ms | Requests/s | Prompt tokens from GPU prefix cache | Prompt tokens from LMCache (L1 or Valkey) | Failed requests |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| random-no-lmcache | 8 | 3 | 400 (395–401) | 694 (638–704) | 1,034 (1,020–1,286) | 3.26 (3.21–3.29) | 14% (13–17%) | 0% | 0 |
| random-no-lmcache | 16 | 3 | 407 (406–415) | 785 (781–917) | 1,447 (1,407–2,015) | 5.08 (4.93–5.09) | 15% (15–15%) | 0% | 0 |
| random-no-lmcache | 32 | 3 | 464 (446–515) | 1,380 (1,339–1,452) | 2,614 (2,501–2,623) | 6.81 (6.71–6.85) | 15% (13–16%) | 0% | 0 |
| random | 8 | 3 | 441 (432–445) | 581 (552–588) | 951 (814–951) | 3.93 (3.93–3.96) | 15% (14–15%) | 81% (81–82%) | 0 |
| random | 16 | 3 | 508 (496–522) | 697 (696–758) | 1,539 (1,473–1,763) | 7.12 (7.03–7.14) | 15% (14–16%) | 85% (83–85%) | 0 |
| random | 32 | 3 | 1,040 (1,035–1,225) | 2,673 (2,359–2,737) | 3,895 (3,830–4,058) | 9.93 (9.85–9.96) | 15% (13–16%) | 83% (83–85%) | 0 |
| approximate | 8 | 3 | 392 (387–396) | 553 (544–558) | 881 (821–926) | 4.05 (4.05–4.06) | 46% (45–47%) | 50% (48–50%) | 0 |
| approximate | 16 | 3 | 498 (492–517) | 701 (675–707) | 1,560 (1,556–1,664) | 7.25 (7.19–7.28) | 46% (45–46%) | 54% (53–55%) | 0 |
| approximate | 32 | 3 | 1,170 (1,098–1,190) | 2,371 (2,326–2,860) | 3,966 (3,789–4,009) | 10.07 (9.69–10.21) | 40% (38–40%) | 59% (59–61%) | 0 |
| precise-memory | 8 | 3 | 389 (372–389) | 544 (536–560) | 790 (789–813) | 4.04 (4.02–4.04) | 63% (62–63%) | 33% (32–34%) | 0 |
| precise-memory | 16 | 3 | 503 (494–516) | 712 (687–721) | 1,642 (1,611–1,708) | 7.20 (7.18–7.25) | 64% (64–64%) | 36% (36–36%) | 0 |
| precise-memory | 32 | 3 | 1,140 (1,045–1,310) | 2,387 (2,375–2,513) | 3,964 (3,831–4,103) | 10.14 (9.89–10.19) | 62% (62–62%) | 37% (37–38%) | 0 |
| precise-valkey | 8 | 3 | 382 (382–393) | 558 (547–560) | 816 (808–823) | 4.02 (4.02–4.04) | 63% (63–64%) | 33% (32–33%) | 0 |
| precise-valkey | 16 | 3 | 514 (507–515) | 688 (687–704) | 1,803 (1,641–1,958) | 7.20 (7.18–7.21) | 62% (61–63%) | 38% (37–38%) | 0 |
| precise-valkey | 32 | 3 | 1,099 (1,030–1,151) | 2,543 (2,357–2,638) | 3,894 (3,794–3,923) | 10.09 (10.02–10.28) | 63% (62–64%) | 37% (36–37%) | 0 |

Each cell is the median of the runs, with the spread (min–max) in brackets. Prompt-token shares come from vLLM's prefix_cache_hits (local) and external_prefix_cache_hits (LMCache: its L1 memory or Valkey) counters, as shares of prompt_tokens. The Valkey table below splits LMCache's lookups into chunks found in L1 and chunks loaded from Valkey.

### Valkey after each run

Measured 2026-11-06T20:03:31Z on aws g6e.12xlarge in ap-northeast-1: 4x NVIDIA L40S 45 GiB, driver 595.112.07; model Qwen/Qwen3-8B, vLLM 0.30.0, lmcache 0.5.5; commit 1acc7860fa7e.

| Configuration | Run | Valkey used_memory GiB | used_memory_peak GiB | maxmemory GiB | KV keys (db 0) | Index keys (db 1) | Index keys at start (db 1) | OOM rejections | Lookup chunks from L1 | Lookup chunks from Valkey | Prefetch p50 ms |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| random-no-lmcache | 1 | 0.0 | 31.6 | 192 | 0 | 0 | 0 | 0 | n/a | n/a | n/a |
| random-no-lmcache | 2 | 0.0 | 31.6 | 192 | 0 | 0 | 0 | 0 | n/a | n/a | n/a |
| random-no-lmcache | 3 | 0.0 | 31.6 | 192 | 0 | 0 | 0 | 0 | n/a | n/a | n/a |
| random | 1 | 150.0 | 150.4 | 192 | 3840 | 0 | 0 | 0 | 13,775 | 27,710 | 234 |
| random | 2 | 150.0 | 150.4 | 192 | 3840 | 0 | 0 | 0 | 13,538 | 27,965 | 224 |
| random | 3 | 150.0 | 150.4 | 192 | 3840 | 0 | 0 | 0 | 13,790 | 27,695 | 233 |
| approximate | 1 | 150.0 | 150.4 | 192 | 3840 | 0 | 0 | 0 | 13,549 | 27,901 | 235 |
| approximate | 2 | 150.0 | 150.4 | 192 | 3840 | 0 | 0 | 0 | 13,765 | 27,736 | 232 |
| approximate | 3 | 150.0 | 150.4 | 192 | 3840 | 0 | 0 | 0 | 13,966 | 27,518 | 228 |
| precise-memory | 1 | 150.0 | 150.4 | 192 | 3840 | 0 | 0 | 0 | 13,666 | 27,851 | 224 |
| precise-memory | 2 | 150.0 | 150.4 | 192 | 3839 | 0 | 0 | 0 | 13,696 | 27,787 | 228 |
| precise-memory | 3 | 150.0 | 150.4 | 192 | 3839 | 0 | 0 | 0 | 13,700 | 27,834 | 228 |
| precise-valkey | 1 | 150.0 | 150.4 | 192 | 3839 | 20602 | 0 | 0 | 13,507 | 28,080 | 227 |
| precise-valkey | 2 | 150.0 | 150.4 | 192 | 3839 | 20210 | 0 | 0 | 13,688 | 27,830 | 227 |
| precise-valkey | 3 | 150.0 | 150.4 | 192 | 3839 | 20468 | 0 | 0 | 13,802 | 27,715 | 226 |

used_memory after a run is close to that run's peak: nothing is deleted during a run (noeviction), and database 0 is flushed before the next. used_memory_peak is since Valkey started, so it covers every run so far.
