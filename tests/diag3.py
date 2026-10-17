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
t.send("autoload -Uz compinit; compinit -u\n")
t.wait_idle(1.0)
t.send("cd /tmp/spacue-demo\n")
t.wait_idle(0.5)

print("=== WITH compinit: cd <space> ===")
t.send("cd ")
t.wait_idle(0.8)
print(t.screen.text())
t.send_keys("C-u", "C-g")
t.wait_idle(0.3)
t.close()
