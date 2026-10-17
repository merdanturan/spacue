# spacue demo — github.com/merdanturan/spacue
# recorded in a clean "zsh -f" shell: nothing from the user's setup.
# the plugin is sourced from a neutral fixture copy -- no local paths on screen.

Output docs/demo.gif
Output docs/demo.mp4

Set Shell bash
Set FontSize 20
Set Width 1040
Set Height 620
Set Padding 40
Set Theme Dracula
Set TypingSpeed 140ms

Hide
Type "exec zsh -f -i"
Enter
Sleep 900ms
Type "PROMPT=' %F{magenta}spacue%f ❯ '; RPS1=' %F{cyan}%1~%f'"
Enter
Type "autoload -Uz compinit && compinit -u -C -d /tmp/spacue-demo-dump"
Enter
Type "cd /tmp/spacue-video"
Enter
Type "source ./spacue.zsh"
Enter
Sleep 900ms
Show
Ctrl+L
Sleep 1200ms

# --- 1: npm package.json scripts -- menu, arrows, insert, run ---
Type "npm "
Sleep 2600ms
Down
Sleep 700ms
Down
Sleep 1100ms
Enter
Sleep 1600ms
Enter
Sleep 3000ms
Ctrl+U
Ctrl+L
Sleep 1000ms

# --- 2: cd directories -- menu, arrows, insert, run; prompt cwd flips ---
Type "cd "
Sleep 2600ms
Down
Sleep 700ms
Down
Sleep 1100ms
Enter
Sleep 1600ms
Enter
Sleep 3000ms
Ctrl+U
Ctrl+L
Sleep 1000ms

# --- 3: git -- fuzzy subcommand filter, then fuzzy branch switch ---
Type "git ch"
Sleep 2600ms
Enter
Sleep 1600ms
Type " f"
Sleep 2600ms
Enter
Sleep 3000ms
Ctrl+U
Ctrl+L
Sleep 1000ms

# --- sign-off ---
Type "echo 'github.com/merdanturan/spacue'"
Sleep 500ms
Enter
Sleep 3500ms
