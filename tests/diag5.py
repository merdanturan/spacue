import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from pterm import Term

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "spacue.zsh"))

t = Term(["zsh", "-f", "-i"], cols=100, rows=30)
t.wait_idle(0.5, 5)
t.send("PS1='PS> '\n")
t.wait_for("PS>", 5)
t.send(f"source {PLUGIN}\n")
t.wait_idle(0.5)
t.send("cd /tmp/spacue-demo\n")
t.wait_idle(0.4)

# single complete-word call
t.send("_spacue_show_menu() { _spacue_on=1; _spacue_style_on; zle spacue-complete; }\n")
t.wait_idle(0.3)

print("=== SINGLE call: cd <space> ===")
t.send("cd ")
t.wait_idle(0.8)
print(t.screen.text())

print("=== Down ===")
t.send_keys("Down")
t.wait_idle(0.5)
print(t.screen.text())

print("=== Enter ===")
t.send_keys("Enter")
t.wait_idle(0.5)
print(t.screen.text())
t.close()
