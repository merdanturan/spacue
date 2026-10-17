import sys, os, re
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

mark = len(t.raw)
t.send("cd ")
t.wait_idle(1.0)
chunk = t.raw[mark:]
print("screen:")
print(t.screen.text())
print()
print("raw contains 'alpha/':", b"alpha/" in chunk)
print("raw contains 'beta/':", b"beta/" in chunk)
print()
print("raw chunk (escaped):")
print(repr(chunk[:2000]))
t.close()
