#!/bin/sh
# spacue installer -- https://github.com/merdanturan/spacue
#
# Run from a pipe (recommended in the README):
#   curl -fsSL https://raw.githubusercontent.com/merdanturan/spacue/main/install.sh | sh
# or from a clone of the repo:
#   ./install.sh
#
# What it does:
#   1. checks that zsh exists
#   2. copies spacue.zsh into ~/.spacue/
#   3. appends one source line to ~/.zshrc (idempotent)
# That source line makes spacue load in every new zsh session -- every
# terminal window, and on every reboot -- with no login item or daemon.
set -u

REPO="https://raw.githubusercontent.com/merdanturan/spacue/main"
DIR="$HOME/.spacue"
ZSHRC="$HOME/.zshrc"

fetch() {
  if command -v curl >/dev/null 2>&1; then
    curl -fsSL "$1"
  elif command -v wget >/dev/null 2>&1; then
    wget -qO- "$1"
  else
    echo "spacue: curl or wget is required" >&2
    exit 1
  fi
}

# 1) zsh present?
if ! command -v zsh >/dev/null 2>&1; then
  echo "spacue: 'zsh' was not found on PATH."
  case "$(uname -s 2>/dev/null)" in
    Darwin)
      echo "macOS ships zsh by default (since Catalina); open a new terminal and try again." ;;
    Linux*)
      echo "spacue is a zsh plugin, so it needs zsh first. Install it with your"
      echo "package manager, for example:"
      echo "  Debian/Ubuntu/WSL:  sudo apt install -y zsh"
      echo "  Fedora:             sudo dnf install -y zsh"
      echo "  Arch:               sudo pacman -S zsh" ;;
    *)
      echo "Install zsh, then rerun this installer." ;;
  esac
  exit 1
fi

# 2) fetch the plugin (from the clone we're in, when run as ./install.sh)
mkdir -p "$DIR"
if [ -f "$(dirname "$0")/spacue.zsh" ]; then
  cp "$(dirname "$0")/spacue.zsh" "$DIR/spacue.zsh"
else
  fetch "$REPO/spacue.zsh" > "$DIR/spacue.zsh" || {
    echo "spacue: download failed" >&2
    rm -f "$DIR/spacue.zsh"
    exit 1
  }
fi
grep -q "SPACUE_VERSION" "$DIR/spacue.zsh" 2>/dev/null || {
  echo "spacue: downloaded file looks wrong, aborting" >&2
  rm -f "$DIR/spacue.zsh"
  exit 1
}

# 3) wire into ~/.zshrc (idempotent)
touch "$ZSHRC"
if grep -q "spacue.zsh" "$ZSHRC" 2>/dev/null; then
  echo "already wired in $ZSHRC"
else
  cat >> "$ZSHRC" <<'EOF'

# >>> spacue >>>
[[ -f "$HOME/.spacue/spacue.zsh" ]] && source "$HOME/.spacue/spacue.zsh"
# <<< spacue <<<
EOF
  echo "added source line to $ZSHRC"
fi

# 4) login-shell hint
case "${SHELL:-}" in
  */zsh) ;;
  *)
    echo
    echo "note: your login shell is ${SHELL:-unknown}, spacue is a zsh plugin."
    echo "It runs inside zsh sessions. To switch your default shell:"
    echo "  chsh -s \"\$(command -v zsh)\"" ;;
esac

echo
echo "spacue installed -> $DIR/spacue.zsh"
echo "Open a NEW terminal window (or run: exec zsh), then try:"
echo "  cd <space>    npm <space>    git <space>"
