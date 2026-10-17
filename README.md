# spacue

**kiro-style dropdown autocomplete for zsh — one file, zero dependencies.**

Type a command, press space, and a dropdown of likely candidates appears right
under your prompt: `package.json` scripts for npm/pnpm/yarn/bun, git
subcommands and branches, Makefile targets, ssh hosts, running PIDs,
directories for `cd`, files for everything else. Arrow keys to navigate,
Enter to insert, Enter again to run, Esc to dismiss.

```
you:  npm ␣
      ────────────────────────────────────────────
      npm run ␣dev        vite --port 3000
      npm run ␣build      tsc -b
      npm run ␣test       vitest
      npm install   npm run   npm test   npm exec ...
```

## Why

Tools like [kiro cli](https://kiro.dev) ship this exact UX — but bundle it
inside a full assistant runtime: daemons, downloads, model hooks, storage.
spacue is the part you actually use: **a single 30 KB zsh file** that loads in
about 10 ms, with no daemon, no background process and no dependency.

## Install

### macOS & Linux (one line)

```sh
curl -fsSL https://raw.githubusercontent.com/merdanturan/spacue/main/install.sh | sh
```

The installer copies `spacue.zsh` to `~/.spacue/` and adds one source line to
`~/.zshrc`. From then on spacue loads automatically in **every** terminal
window, including the first one after every reboot — no login item, no
background daemon, nothing to start manually.

Open a new terminal window (or run `exec zsh`) and try `cd ␣`.

### Windows (WSL)

Native PowerShell/cmd has no zsh, so spacue runs inside [WSL](https://learn.microsoft.com/windows/wsl/install):

```powershell
wsl --install                                          # one-time, then reboot
wsl sh -c "sudo apt update && sudo apt install -y zsh" # one-time
irm https://raw.githubusercontent.com/merdanturan/spacue/main/install.ps1 | iex
```

Then open a new WSL terminal. `spacue_uninstall` or `uninstall.sh` removes
everything cleanly.

### Manual

```sh
git clone https://github.com/merdanturan/spacue
echo 'source ~/spacue/spacue.zsh' >> ~/.zshrc
```

### Plugin managers

```sh
antigen bundle merdanturan/spacue
zinit light merdanturan/spacue                       # zinit
git clone https://github.com/merdanturan/spacue \
  ~/.oh-my-zsh/custom/plugins/spacue                 # oh-my-zsh, then: plugins+=(spacue)
```

## Usage

| Key                | Action                                        |
|--------------------|-----------------------------------------------|
| `space`            | open the menu after a command                 |
| `↑` `↓`            | move the selection                            |
| `Enter`            | insert the selected item (does **not** run)   |
| `Enter` (again)    | run the line                                  |
| `Esc` / `Ctrl+G`   | close the menu, keep what you typed           |
| keep typing        | live-filter while the menu is open            |

What shows up per command:

| Command                                  | Candidates                                    |
|------------------------------------------|-----------------------------------------------|
| `npm` / `pnpm` / `yarn` / `bun`          | `package.json` scripts (with the real command as hint) + subcommands; dependencies for `install`/`add` |
| `git`                                    | subcommands; branches & changed files per subcommand; remotes for push/pull |
| `make`                                   | Makefile targets (`## comment` shown as hint) |
| `ssh` / `scp` / `sftp`                   | hosts from `~/.ssh/config` + `known_hosts`    |
| `kill` / `killall` / `pkill`             | running PIDs / process names                  |
| `cd` / `pushd`                           | directories (including `../`)                 |
| `ls`, `cat`, `vim`, `code`, `grep`, ...  | files & directories                           |
| `ls -`, `curl -`, `git commit -`, ...    | common flags                                  |
| anything else                            | files & directories of the current folder (first argument) |
| `sudo` / `env` / `time` / `command` ...  | the wrapped command's own candidates          |

Fuzzy fallback: `npm run bi␣` still finds `build`.

## Configuration

Set these before spacue loads (or export them in `~/.zshrc`):

| Variable                 | Default | Meaning                                            |
|--------------------------|---------|----------------------------------------------------|
| `SPACUE_ENABLED`         | `1`     | master kill switch                                 |
| `SPACUE_HINTS`           | `1`     | show descriptions next to items                    |
| `SPACUE_GENERIC`         | `1`     | file candidates for unknown commands               |
| `SPACUE_FUZZY`           | `1`     | substring fallback when prefix matching is empty   |
| `SPACUE_TYPING_TRIGGER`  | `1`     | reopen the menu while typing after `dir/`          |
| `SPACUE_COMPINIT`        | `1`     | auto-load compinit when your setup lacks it        |
| `SPACUE_DISABLED`        | `()`    | providers to turn off, e.g. `SPACUE_DISABLED="ssh kill"` |
| `SPACUE_MAX`             | `200`   | max candidates per menu                            |

## Custom providers

A provider is a zsh function that receives `(cmd token args...)`, appends
candidates with `spacue_add VALUE [DESC] [MATCH]`, and optionally sets
`SPACUE_KIND` to `words` or `paths`:

```zsh
# ~/.zshrc, after spacue loads
spacue_register docker _my_docker
_my_docker() {
  local cmd=$1 token=$2 sub=$3
  SPACUE_KIND=words
  case $sub in
    ('') for s in run build ps images pull push logs exec compose; do
           spacue_add "$s"
         done ;;
  esac
}
```

## FAQ

**Does it need macOS Login Items or a startup daemon?**
No — and it can't be one. A Login Item (or LaunchAgent) is for *processes* the
system starts at boot. spacue is not a process; it is code that runs inside
every zsh session. The `source` line in `~/.zshrc` is the persistence
mechanism: every shell you open — first thing after a reboot included — loads
it automatically. If spacue ever ran a daemon instead, it *would* show up as a
background item — which is exactly the kind of hidden baggage this tool exists
to avoid.

**Does it slow down my prompt?** Loading costs ~10 ms. Candidates are computed
on demand and cached (`git` 3 s, `ssh` 10 s, `ps` 2 s TTLs).

**Does it break Tab?** No. Plain `Tab` keeps zsh's standard completion; spacue
only hijacks the space key and a few edit keys while its menu is open.

**Known conflicts:** `fzf-tab` replaces the same menu machinery, so don't load
both.

## Compatibility

zsh 5.1+ (any macOS since Catalina, most Linux distros, WSL). The JSON reader
for `package.json` prefers `node`, then `jq`, then `python3`, and finally falls
back to pure awk — no hard dependency.

## Development

Tests drive a real pty running zsh and assert on the rendered screen:

```sh
python3 tests/diag12.py    # end-to-end UX suite (15 checks)
python3 tests/smoke.py     # quick smoke test
```

## License

[MIT](LICENSE)
