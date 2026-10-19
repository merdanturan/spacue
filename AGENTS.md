# AGENTS.md - spacue

Rules for AI coding agents in this repository. They add to the global AGENTS.md
(`~/.codex/AGENTS.md`, `~/.config/opencode/AGENTS.md`).

spacue is an inline dropdown autocomplete for zsh: one file (`spacue.zsh`), zero dependencies, no
daemon. Users get it through `curl ... install.sh | sh`, plugin managers (antigen, zinit, oh-my-zsh)
or a git clone.

## Layout
- `spacue.zsh` - the whole plugin. Sections: config, utilities, usage ranking, providers,
  collect + parse, completion plumbing, menu open / state, triggers, widget wrappers, bootstrap.
- `spacue.plugin.zsh` - plugin-manager entry point; it only sources `spacue.zsh`.
- `install.sh`, `uninstall.sh` (POSIX sh) and `install.ps1` (Windows: runs `install.sh` in WSL).
- `tests/` - Python 3 standard library only. `run.py` runs the maintained suites, `pterm.py` is the
  pty driver and screen emulator, `benchmark.py` measures without asserting. `diag*.py` files that
  `run.py` doesn't list, and the `_*.py` files, are old diagnostics: don't extend them or treat
  them as release checks.
- `docs/` - demo assets (`demo.tape`, `demo-setup.zsh`), `performance.md`, plans in
  `docs/superpowers/plans/`.

## Invariants (never break these)
1. One distributable file, zero runtime dependencies. `node`, `jq` and `python3` stay optional
   JSON readers, with the pure awk fallback last.
2. No daemon, background job or network access from the plugin.
3. Public behaviour is a contract: the key bindings (space opens, Up/Down select, Enter/Tab accept
   once and a second Enter runs, Esc/Ctrl-G dismiss, plain Tab stays stock zsh completion), the
   provider API (`spacue_register`, `spacue_add`, `SPACUE_KIND`), every `SPACUE_*` variable with
   its default, and the stats file format (TSV: `command:candidate`, count, directory). Changing
   any of them needs my OK and a README update.
4. Opening or filtering the menu never changes the typed input. Only accepted items count in the
   ranking; previews and dismissals don't.
5. Never execute the command line on the user's behalf. Native completion stays opt-in
   (`SPACUE_NATIVE=0` by default) and must not run the submitted command.
6. Stats writes stay atomic (lock + rename), private to the user and capped at 8,000 records.
   Names with tabs or newlines are never recorded.
7. Registered (custom) providers are never cached: they may depend on every typed character.
8. Never replace the user's completion styles (`zstyle`, including `zstyle -e`) and always restore
   the previous key bindings when a menu closes.
9. The installers stay POSIX `sh` and idempotent (exactly one `# >>> spacue >>>` block). They
   validate a download (`SPACUE_VERSION` present, `zsh -n` passes) before replacing the installed
   file, and touch only `~/.spacue/` and `${ZDOTDIR:-$HOME}/.zshrc`.
10. Never run the installers, or a zsh that sources the plugin, against the real home directory.
    Tests use a temporary `HOME`/`ZDOTDIR` and `SPACUE_STATS_FILE`, and start zsh with `-f`.

## zsh style
- Tested on zsh 5.9; oldest supported version: FILL. Check new syntax and modules against it.
- Internal functions and globals start with `_spacue_`, public ones with `spacue_`. Declare locals
  with `local`, globals with `typeset -g`.
- Code that runs per key press or per menu update avoids forks (`$(...)`, pipes, external
  commands): use builtins, parameter expansion and the existing caches.
- Candidates may contain spaces, quotes and glob characters: quote expansions the way the
  surrounding code does.

## Verify before saying "done"
1. Syntax: `zsh -n spacue.zsh` and `zsh -n spacue.plugin.zsh`; `sh -n install.sh` and
   `sh -n uninstall.sh`.
2. Tests: `python3 tests/run.py`. The pty suites share fixtures: run them one after another, never
   in parallel. Quick loop: `python3 tests/regression.py`.
3. New behaviour or a fixed bug gets a test in the matching suite: `regression.py` (logic, no pty),
   `test_ui.py` (keys, rendering, quoting), `test_native.py` (native completion),
   `test_install.py` (installers).
4. Performance-sensitive changes: run `python3 tests/benchmark.py` before and after, compare with
   `--plugin` as in `docs/performance.md`, and report the numbers. Never while tests are running.
5. How it feels in a real terminal can't be checked here: list what I should try by hand.

CI (`.github/workflows/tests.yml`) runs the same checks on ubuntu-latest and macos-latest.

## Releases (never tag or push yourself)
- The version lives in `SPACUE_VERSION` at the top of `spacue.zsh`; tags are `vX.Y.Z` and must match
  it. When preparing a release, bump `SPACUE_VERSION` and the README, then hand over to me for the
  tag and push.
- `install.sh` downloads `spacue.zsh` from `main`, so every merge reaches new installs at once.
  Work on a branch (`codex/<topic>`) and keep `main` releasable.
- Superpowers documents for larger changes: specs in `docs/superpowers/specs/`, plans in
  `docs/superpowers/plans/YYYY-MM-DD-<topic>.md`.
