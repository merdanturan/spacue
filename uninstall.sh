#!/bin/sh
# spacue uninstaller -- https://github.com/merdanturan/spacue
# Run:  curl -fsSL https://raw.githubusercontent.com/merdanturan/spacue/main/uninstall.sh | sh
#       (or ./uninstall.sh from a clone)
set -eu
ZSHRC="${ZDOTDIR:-$HOME}/.zshrc"

if [ -f "$ZSHRC" ]; then
  if sed -i.bak '/# >>> spacue >>>/,/# <<< spacue <<</d' "$ZSHRC" 2>/dev/null; then
    rm -f "$ZSHRC.bak"
    echo "removed the source line from $ZSHRC"
  else
    echo "spacue: could not edit $ZSHRC -- remove the '# >>> spacue >>>' block manually" >&2
  fi
fi

rm -rf "$HOME/.spacue"
echo "spacue removed. Restart your terminal to apply."
echo "(In an open session, run: spacue_uninstall)"
