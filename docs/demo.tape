# Run from the repository root: vhs docs/demo.tape
# A real zsh session using the current plugin and disposable demo fixtures.
Require zsh
Require node
Require npm

Output docs/demo.gif
Output docs/demo.mp4

Set Shell bash
Set FontFamily "Menlo"
Set FontSize 20
Set Width 1120
Set Height 520
Set Padding 28
Set Margin 16
Set MarginFill "#080e0c"
Set BorderRadius 12
Set WindowBar Colorful
Set Framerate 24
Set CursorBlink false
Set TypingSpeed 110ms
Set Theme { "name": "spacue", "background": "#111916", "foreground": "#e2eae5", "black": "#17221c", "red": "#f08888", "green": "#8cdeb0", "yellow": "#e5c890", "blue": "#8db6da", "magenta": "#c6a4d9", "cyan": "#9cd8ce", "white": "#e2eae5", "brightBlack": "#82978c", "brightRed": "#f5a3a3", "brightGreen": "#a4ecc4", "brightYellow": "#f0dbaf", "brightBlue": "#b1d2ed", "brightMagenta": "#d9bfe7", "brightCyan": "#bcebe1", "brightWhite": "#f5faf7", "cursor": "#8cdeb0", "selection": "#2d493a" }

Hide
Type@0 "exec zsh -f -i"
Enter
Sleep 500ms
Type@0 "source ./docs/demo-setup.zsh; _spacue_demo_scene 1"
Enter
Sleep 1500ms
Show
Sleep 800ms

# No candidate is inserted when the dropdown opens.
Type "npm "
Sleep 2000ms
Down
Sleep 700ms
Down
Sleep 650ms
Up
Sleep 700ms
Tab
Sleep 1100ms
Enter
Sleep 1800ms

Hide
Type@0 "_spacue_demo_scene 2"
Enter
Sleep 300ms
Show
Sleep 650ms
Type "npm run "
Sleep 850ms
Type "te"
Sleep 1600ms
Down
Sleep 900ms
Escape
Sleep 1100ms
Ctrl+U

Hide
Type@0 "_spacue_demo_scene 3"
Enter
Sleep 300ms
Show
Sleep 650ms
Type "cd "
Sleep 1000ms
Type "sr"
Sleep 1200ms
Down
Sleep 800ms
Tab
Sleep 800ms
Enter
Sleep 1500ms

Hide
Type@0 "_spacue_demo_scene done"
Enter
Sleep 300ms
Show
Sleep 2600ms

# Return to the opening composition for a clean loop.
Hide
Type@0 "_spacue_demo_scene 1"
Enter
Sleep 300ms
Show
Sleep 250ms
