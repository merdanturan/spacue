import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from pterm import Term

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "spacue.zsh"))
INSTR = "/private/var/folders/y2/5xd3vngn4tg22wy8sstw9bx00000gn/T/opencode/spacue-instr.zsh"
LOG = "/tmp/spacue-debug.log"

try: os.unlink(LOG)
except OSError: pass

t = Term(["zsh", "-f", "-i"], cols=100, rows=30)
t.wait_idle(0.5, 5)
t.send("PS1='PS> '\n")
t.wait_for("PS>", 5)
t.send("autoload -Uz compinit; compinit -u\n")
t.wait_idle(0.8)
t.send(f"source {PLUGIN}\n")
t.wait_idle(0.5)
t.send(f"source {INSTR}\n")
t.wait_idle(0.3)
t.send("cd /tmp/spacue-demo\n")
t.wait_idle(0.4)
t.send("cd ")
t.wait_idle(0.8)
print("=== screen ===")
print(t.screen.text())
t.close()

print("=== log ===")
try: print(open(LOG).read())
except OSError as e: print("no log:", e)
