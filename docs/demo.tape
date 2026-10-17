# spacue demo — github.com/merdanturan/spacue
# recorded in a clean "zsh -f" shell: nothing from the user's setup

Output docs/demo.gif
Output docs/demo.mp4

Set Shell bash
Set FontSize 17
Set Width 1000
Set Height 580
Set Padding 36
Set Theme Dracula
Set TypingSpeed 80ms

Hide
Type "exec zsh -f -i"
Enter
Sleep 900ms
Type "PROMPT=' %F{magenta}spacue%f ❯ '; RPS1=' %F{cyan}%1~%f'"
Enter
Type "autoload -Uz compinit && compinit -u -C -d /tmp/spacue-zcompdump; source /Users/merdanturan/Projects/cli-tool/spacue.zsh"
Enter
Sleep 900ms
Show
Sleep 500ms
Type "cd /tmp/spacue-video"
Enter
Ctrl+L
Sleep 1000ms

# --- scene 1: npm scripts with hints; one fuzzy keystroke completes + runs ---
Type "npm "
Sleep 1800ms
Type "b"
Sleep 1500ms
Enter
Sleep 1000ms
Enter
Sleep 2200ms
Ctrl+U
Ctrl+L
Sleep 700ms

# --- scene 2: make targets with hints; arrows pick, insert, run ---
Type "make "
Sleep 1800ms
Down
Down
Down
Sleep 900ms
Enter
Sleep 1000ms
Enter
Sleep 2200ms
Ctrl+U
Ctrl+L
Sleep 700ms

# --- scene 3: ls flags after '-'; pick one, insert, run ---
Type "ls -"
Sleep 1800ms
Down
Down
Sleep 900ms
Enter
Sleep 1000ms
Enter
Sleep 2200ms
Ctrl+U
Ctrl+L
Sleep 700ms

# --- scene 4: cd directories; select, insert, run ---
Type "cd "
Sleep 1800ms
Down
Down
Sleep 900ms
Enter
Sleep 1000ms
Enter
Sleep 1800ms
Ctrl+U
Ctrl+L
Sleep 700ms

# --- scene 5: git; subcommand menu, fuzzy branch, switch ---
Type "git ch"
Sleep 1800ms
Enter
Sleep 1000ms
Type " f"
Sleep 1600ms
Enter
Sleep 2200ms
Ctrl+U
Ctrl+L
Sleep 700ms

# --- sign-off ---
Type "echo '  github.com/merdanturan/spacue'"
Enter
Sleep 2500ms
