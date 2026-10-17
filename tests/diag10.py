"""Isolate which compadd flag combination kills the completion list.

Each variant redefines _spacue_complete with a different compadd call, then
types `cd ` (space triggers the plugin's double spacue-complete). We then
probe: (1) is the list drawn, (2) does Down move the menu selection,
(3) does Enter accept (no execute) or run the command.
"""
import re
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from pterm import Term

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "spacue.zsh"))

VARIANTS = [
    ("plain",    "compadd alpha beta gamma"),
    ("U",        "compadd -U alpha beta gamma"),
    ("V",        "compadd -V spacue alpha beta gamma"),
    ("a",        "compadd -a items"),
    ("d-a",      "compadd -d descs -a items"),
    ("V-a",      "compadd -V spacue -a items"),
    ("V-d-a",    "compadd -V spacue -d descs -a items"),
    ("U-V-d-a",  "compadd -U -V spacue -d descs -a items"),
    ("V-d-a-realpath",
     "local -a it=('../' 'alpha/' 'beta/' 'Documents/' 'gamma/') "
     "ds=('' '' '' '' ''); compadd -V spacue -d ds -a it"),
    ("describe", "local -a d; d=(alpha:d-one beta:d-two gamma:d-three); "
                 "_describe -t spacue 'spacue' d"),
]

t = Term(["zsh", "-f", "-i"], cols=100, rows=30)
t.wait_idle(0.5, 5)
t.send("PS1='PS> '\n")
t.wait_for("PS>", 5)
t.send("autoload -Uz _describe\n")
t.wait_idle(0.3)
t.send(f"source {PLUGIN}\n")
t.wait_idle(0.5)
t.send("cd /tmp/spacue-demo\n")
t.wait_idle(0.5)
t.send("items=(alpha beta gamma); descs=('d-one' 'd-two' 'd-three')\n")
t.wait_idle(0.4)


def prompt_line():
    for line in reversed(t.screen.text().splitlines()):
        if "PS>" in line:
            return line.strip()
    return "<no prompt>"


for name, body in VARIANTS:
    t.send(f"_spacue_complete() {{ {body} }}\n")
    t.wait_idle(0.3)
    t.send("clear\n")
    t.wait_idle(0.3)
    t.send("cd ")
    t.wait_idle(1.2)

    txt = t.screen.text()
    list_drawn = bool(re.search(r"alpha\s+beta", txt))
    print(f"=== {name}: list={'YES' if list_drawn else 'no'}")
    for line in [l for l in txt.splitlines() if l.strip()][:8]:
        print("   |", line)

    t.send_keys("Down")
    t.wait_idle(0.6)
    print(f"   after Down : {prompt_line()}")

    t.send_keys("Enter")
    t.wait_idle(0.8)
    txt2 = t.screen.text()
    ran = txt2.count("PS>") >= 2
    print(f"   after Enter: {'RAN the command' if ran else 'accepted (no run)'}"
          f" | {prompt_line()}")

    t.send_keys("C-u", "C-g")
    t.wait_idle(0.3)

print("=== real _spacue_complete (re-source)")
t.send(f"source {PLUGIN}\n")
t.wait_idle(0.5)
t.send("clear\n")
t.wait_idle(0.3)
mark = len(t.raw)
t.send("cd ")
t.wait_idle(1.2)
txt = t.screen.text()
print(f"   list={'YES' if re.search(r'\\.\\./\\s+alpha', txt) else 'no'}")
for line in [l for l in txt.splitlines() if l.strip()][:8]:
    print("   |", line)
print("   raw since trigger:", repr(t.raw[mark:][:400]))

t.send_keys("Down")
t.wait_idle(0.5)
print(f"   after Down : {prompt_line()}")
t.send_keys("Enter")
t.wait_idle(0.8)
txt2 = t.screen.text()
print(f"   after Enter: {'RAN the command' if txt2.count('PS>') >= 2 else 'accepted (no run)'}"
      f" | {prompt_line()}")
t.close()
