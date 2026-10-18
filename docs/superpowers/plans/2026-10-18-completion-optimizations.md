# Completion optimizations

Goal: reduce repeated work without changing v0.3.0's default key behavior,
candidate ordering, provider API, quoting, stats format, or installation.
Keep one distributable zsh file and no new runtime dependency.

Implementation stays on `codex/completion-optimizations`; the published tag
and main branch remain untouched. Do not publish or tag a release in this task.

## Boundaries

- Enter/Tab accept once; a subsequent Enter executes. Previews never count.
- Esc/Ctrl-G, emacs/vi modes, type-ahead and stock Tab must keep working.
- Cache invalidation covers own writes, atomic writes from other terminals,
  stats-file changes, directory changes, missing files and prompt boundaries.
- Registered providers may depend on every typed character: do not cache them.
- Cache complete, unfiltered candidates before the display limit. Backspace,
  fuzzy fallback, hidden files and entering a child directory must work.
- A menu's candidate snapshot lives only for that interaction. New menus
  refresh from providers; source changes and existing TTLs invalidate snapshots.
- Built-in and registered providers retain precedence over native completion.
- Native fallback is opt-in (`SPACUE_NATIVE=0` by default). It uses installed
  zsh completions and their quoting/suffix rules. It must not run the submitted
  command. Completion functions themselves may execute programs, like stock Tab.
- Do not replace user completion styles, including dynamic `zstyle -e` rules.

## Steps

- [x] Run the published version's maintained tests before product changes.
- [x] Add a repeatable benchmark for warm package menus, live filtering and a
  large directory with 8,000 ranking records. Save baseline measurements.
- [x] Add failing cache tests, then cache parsed statistics using native file
  identity/metadata plus PWD and configured path. Invalidate after writes and
  at prompt boundaries, including failures/removal.
- [x] Add failing reuse tests, then snapshot built-in provider candidates for
  active-menu filtering. Keep custom providers dynamic, preserve descriptions,
  ranking, flags, fuzzy behavior and the cap-after-filter rule.
- [x] Replace overlapping active/pending flags and completion counters with
  explicit idle/preview/menu state and prefix/list/select phases. Centralize
  acceptance and cleanup. Prove the refactor with the same PTY contracts.
- [x] Connect native completion in an isolated completion widget context.
  Test multiple/one/zero candidates, flags, suffixes, spaces/metacharacters,
  native errors, dismissal, type-ahead, vi mode and precedence. Preserve native
  match ordering; do not attempt to reinterpret or rerank native compadd groups.
- [x] Document behavior, opt-in, native ranking limitation and measurements.
  Add new suites to the sequential runner and run the full release checks.

## Verification

Fast proof: isolated regression and PTY tests with no third-party Python packages.
Release proof: `python3 tests/run.py` on macOS locally; the existing CI matrix
runs macOS and Linux when pushed. Process tests need permission to run `ps`.
Performance proof: run the same benchmark against the v0.3.0 file and final
file on the same machine; report measured workloads, not universal speed claims.

Review especially: same-second atomic replacement, stats deletion/recreation,
deeply escaped paths, menus narrowed beyond the 200 displayed items, custom
providers receiving raw context, and existing dynamic completion styles.

## Completed proof

- Published baseline: 8/8 maintained suites.
- Updated release runner: 9/9 suites, including native completion integration.
- Final cache-invalidation checks: 32/32 regression tests; 13/13 native tests.
- Existing acceptance/quoting UI suite and provider suite also passed.
- Shell syntax and `git diff --check` passed. No release or tag was published.
- Local platform: macOS, zsh 5.9. Linux remains covered by the existing CI matrix
  when the branch is pushed; it was not run locally.
- Measurements and limitations: `docs/performance.md`.
