# Completion performance — 2026-10-18

Measured locally on macOS with zsh 5.9, comparing the published `v0.3.0`
file with the candidate-snapshot, statistics-cache and native-filter changes.
Both versions ran sequentially on the same machine, outside the test suites.
These are synthetic workloads, not promises about every terminal or filesystem.

| Workload | v0.3.0 median | Updated median | v0.3.0 p95 | Updated p95 |
|---|---:|---:|---:|---:|
| Warm package-menu filter | 296.562 ms | 12.406 ms | 402.277 ms | 108.567 ms |
| Warm large-directory filter | 758.028 ms | 86.983 ms | 819.854 ms | 526.571 ms |
| Source plugin, compinit disabled | 46.129 ms | 48.729 ms | 54.919 ms | 53.350 ms |

Warm-filter medians improved by about 24× and 8.7× in this run. Loading the
plugin cost about 2.6 ms more at the median. Scheduling noise was substantial,
especially in the directory p95; the improvement is not a claim of consistently
instant menus on large directories.

## Method

- Standard Python and zsh; no third-party benchmark package.
- 200 package scripts, 5,000 directories and 8,000 valid TSV history entries.
  The history entries belong to other commands, so this exercises the common
  zero-score path while still measuring a populated statistics file.
- Warm each provider once, then model an active menu. Each of 20 trials filters
  four increasingly specific prefixes, including returning to the broader
  prefix for the next trial. Report milliseconds per filter; the benchmark uses
  the upper middle sample for even-sized warm-filter medians.
- No ZLE rendering, blocking input loop, completion-system initialization or
  network requests in the measured warm-filter workload.
- Startup timing covers sourcing the plugin with `SPACUE_COMPINIT=0`, not
  starting the entire user's shell. Twelve independent shells per version
  were alternated for the startup comparison above.
- Native fallback remains off by default. Its speed depends on the installed
  completion function and is not represented by these numbers.

Reproduce the warm-filter comparison:

```sh
git show v0.3.0:spacue.zsh > /tmp/spacue-v0.3.0.zsh
python3 tests/benchmark.py --plugin /tmp/spacue-v0.3.0.zsh
python3 tests/benchmark.py
```

The command also reports 12 independent source timings per invocation. Run it
without concurrent test suites or other benchmarks. Timings are observations;
correctness is enforced by the regression and PTY suites, not timing thresholds.

## Why the work decreases

Statistics are parsed once until the native file identity/metadata, configured
path, directory or prompt changes. Atomic renames from another terminal change
the inode even when size and second-level mtime are identical. In-place manual
edits with unchanged metadata are refreshed at the next prompt.

An active interaction keeps its built-in provider's unfiltered candidate set.
Source metadata, context, existing provider TTLs and interaction cleanup bound
its lifetime. Filtering happens before the display cap, including after
backspace, so candidates beyond the first 200 remain discoverable. Custom
providers continue to receive each update.

Fresh package/Makefile snapshots also validate decoder-cache content with the
standard POSIX `cksum` utility. This avoids stale data after same-second,
same-size edits without rerunning Node/awk on every new menu. It runs when
generating candidates, not on every character of an unchanged active menu.
If a content stamp cannot be obtained, decoding works without the payload cache.

Plain file providers use native zsh array filtering and bulk array construction.
They avoid interpreted per-file filtering and deduplication where filenames are
already unique. Statistics writes keep native operations inside the file lock,
preserving private permissions, atomic replacement and the caller's umask.
