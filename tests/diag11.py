"""End-to-end UX test WITH compinit loaded (real-world condition).

Flow: cd + space -> menu list, Down moves selection, Enter accepts (no run),
second Enter runs, typing filters/reopens, npm scripts list, Esc restores.
"""
import re
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from pterm import Term

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "spacue.zsh"))

t = Term(["zsh", "-f", "-i"], cols=110, rows=34)
t.wait_idle(0.5, 5)
t.send("PS1='PS> '\n")
t.wait_for("PS>", 5)
t.send("autoload -Uz compinit; compinit -u -C -d /tmp/spacue-zcompdump\n")
t.wait_idle(1.0)
t.send(f"source {PLUGIN}\n")
t.wait_idle(0.6)
t.send("cd /tmp/spacue-demo\n")
t.wait_idle(0.5)


def marks():
    out = []
    for m in re.finditer(rb"\x1b\[7m([^\x1b]{1,50})", t.raw):
        out.append(m.group(1).decode("utf-8", "replace"))
    return out[-6:]


def tail(n=8):
    lines = [l for l in t.screen.text().splitlines() if l.strip()]
    return lines[-n:]


def show(label, n=8):
    print(f"--- {label}")
    for line in tail(n):
        print("   |", line)
    print("   inverse:", marks())


print("=== STEP 1: cd <space> should open the menu ===")
t.send("clear\n")
t.wait_idle(0.3)
t.send("cd ")
t.wait_idle(1.2)
show("after 'cd '")

print("=== STEP 2: Down should move selection to next item ===")
t.send_keys("Down")
t.wait_idle(0.6)
show("after Down")

print("=== STEP 3: Enter accepts selection, must NOT run ===")
t.send_keys("Enter")
t.wait_idle(0.7)
show("after Enter", 4)

print("=== STEP 4: second Enter runs the command ===")
t.send_keys("Enter")
t.wait_idle(0.8)
t.send("pwd\n")
t.wait_idle(0.4)
show("after Enter + pwd", 4)

print("=== STEP 5: reopen + type 'g' (filter to gamma/) ===")
t.send("cd /tmp/spacue-demo\n")
t.wait_idle(0.4)
t.send("clear\n")
t.wait_idle(0.3)
t.send("cd ")
t.wait_idle(1.0)
t.send("g")
t.wait_idle(0.9)
show("after typing 'g' in menu")

print("=== STEP 6: cleanup + npm <space> ===")
t.send_keys("C-u", "C-g")
t.wait_idle(0.4)
t.send("clear\n")
t.wait_idle(0.3)
t.send("npm ")
t.wait_idle(1.4)
show("after 'npm '", 12)

print("=== STEP 7: Down x2 + Enter on npm menu ===")
t.send_keys("Down", "Down")
t.wait_idle(0.6)
show("after Down x2", 4)
t.send_keys("Enter")
t.wait_idle(0.6)
show("after Enter", 4)

print("=== STEP 8: Esc restores pre-menu buffer ===")
t.send_keys("C-u", "C-g")
t.wait_idle(0.4)
t.send("clear\n")
t.wait_idle(0.3)
t.send("cd ")
t.wait_idle(1.0)
t.send_keys("Down")
t.wait_idle(0.4)
t.send_keys("Esc")
t.wait_idle(0.6)
show("after Esc", 4)

t.send_keys("C-u", "C-g")
t.wait_idle(0.3)
t.close()
