# Sourced by demo.tape in zsh -f. All demo data and cache files are temporary.
typeset -g _spacue_demo_plugin=${${(%):-%x}:A:h:h}/spacue.zsh
typeset -g _spacue_demo_tmp=$(mktemp -d "${TMPDIR:-/tmp}/spacue-recording.XXXXXX")
[[ -d $_spacue_demo_tmp ]] || return 1
trap 'command rm -rf -- "$_spacue_demo_tmp"' EXIT
mkdir -p "$_spacue_demo_tmp/workspace/"{src,docs,tests}
builtin cd "$_spacue_demo_tmp/workspace" || return 1

cat > package.json <<'JSON'
{
  "name": "spacue-demo",
  "version": "1.0.0",
  "private": true,
  "scripts": {
    "build": "node --check src/index.js",
    "dev": "node src/index.js",
    "test": "node --test"
  }
}
JSON
print -r -- 'console.log("Hello from spacue.");' > src/index.js

# Keep the user's shell, completions and learned ranking out of the recording.
export ZDOTDIR=$_spacue_demo_tmp
export SPACUE_STATS=0 SPACUE_NATIVE=0 SPACUE_HINTS=1
export SPACUE_ENABLED=1 SPACUE_GENERIC=1 SPACUE_FUZZY=1 SPACUE_TYPING_TRIGGER=1 SPACUE_MAX=200
SPACUE_DISABLED=()
export SPACUE_STATS_FILE=$_spacue_demo_tmp/stats.tsv
export npm_config_update_notifier=false npm_config_audit=false npm_config_fund=false
bindkey -e
KEYTIMEOUT=1
PROMPT='%F{8}%1~%f %F{green}❯%f '
RPROMPT=''
autoload -Uz compinit
compinit -u -d "$_spacue_demo_tmp/zcompdump"
source "$_spacue_demo_plugin"

_spacue_demo_scene() {
  builtin cd "$_spacue_demo_tmp/workspace"
  printf '\033[H\033[2J'
  print -P '%F{green}%Bspacue%b%f  %F{8}/  inline autocomplete for zsh%f'
  print
  case $1 in
    (1)
      # Keep all npm subcommands visible in the compact opening scene.
      SPACUE_HINTS=0
      print -P '%B01  Space shows. Down selects.%b'
      print -P '%F{8}Suggestions appear. Your input stays yours.%f' ;;
    (2)
      SPACUE_HINTS=1
      print -P '%B02  Type to filter. Esc to step back.%b'
      print -P '%F{8}Even one match waits for your choice.%f' ;;
    (3)
      print -P '%B03  The same control, for your files.%b'
      print -P '%F{8}Preview a path. Tab to accept. Enter to go.%f' ;;
    (done)
      print -P '%BYour prompt. Your choice.%b'
      print -P '%F{8}One file. Zero dependencies.%f'
      print
      print -P '%F{green}SPACE%f  discover    %F{green}↓%f  select    %F{green}TAB%f  accept    %F{green}ESC%f  dismiss'
      print
      print -P '%F{8}github.com/merdanturan/spacue%f' ;;
  esac
  print
}
