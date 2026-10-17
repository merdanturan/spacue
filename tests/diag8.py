import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from pterm import Term

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "spacue.zsh"))

VARIANTS = [
    ("plain",        "compadd alpha beta gamma"),
    ("-U",           "compadd -U alpha beta gamma"),
    ("-V",           "compadd -V spacue alpha beta gamma"),
    ("-d -a",        "compadd -V spacue -d descs -a items"),
    ("-U -V -d -a",  "compadd -U -V spacue -d descs -a items"),
]

t = Term(["zsh", "-f", "-i"], cols=100, rows=30)
t.wait_idle(0.5, 5)
t.send("PS1='PS> '\n")
t.wait_for("PS>", 5)
t.send(f"source {PLUGIN}\n")
t.wait_idle(0.5)
t.send("cd /tmp/spacue-demo\n")
t.wait_idle(0.4)

for name, body in VARIANTS:
    setup = ("_spacue_complete() { local -a descs=('' '' '') items=(alpha beta gamma); "
             + body + " }")
    # single define to avoid multiline prompt echo noise
    t.send(setup + "\n")
    t.wait_idle(0.3)
    t.send("cd ")
    t.wait_idle(0.9)
    scr = t.screen.text()
    tail = scr.splitlines()[-6:]
    print(f"--- {name!r}: {body}")
    for line in tail: print("   |", line)
    print("   listing found:", "alpha" in scr)
    t.send_keys("C-u", "C-g")
    t.wait_idle(0.3)
t.close()
