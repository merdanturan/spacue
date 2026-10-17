import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from pterm import Term

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "spacue.zsh"))
LOG = "/tmp/spacue-debug.log"

try: os.unlink(LOG)
except OSError: pass

t = Term(["zsh", "-f", "-i"], cols=100, rows=30)
t.wait_idle(0.5, 5)
t.send("PS1='PS> '\n")
t.wait_for("PS>", 5)
t.send(f"source {PLUGIN}\n")
t.wait_idle(0.8)

t.send("print -- WIDGETS: ${+widgets[_spacue_ins]} ${+widgets[_spacue_bdel]} ${+widgets[_spacue_accept]} ${+widgets[_spacue_sbreak]} ${widgets[self-insert]}\n")
t.wait_idle(0.5)
print(t.screen.text())

# instrument the wrapper
t.send(f"_spacue_self_insert() {{ print -r -- \"SI key=[$KEYS] on=[$_spacue_on] buf=[$BUFFER]\" >> {LOG}; zle _spacue_ins; }}\n")
t.wait_idle(0.3)

t.send("cd ")
t.wait_idle(0.6)
# manual trigger test
t.send("print -r -- '--- manual ---' >> %s\n" % LOG)
t.send_keys("C-u", "C-g")
t.wait_idle(0.3)
t.send("cd ")
t.wait_idle(0.3)
print("=== screen after cd+space (instrumented) ===")
print(t.screen.text())
t.close()

print("=== debug log ===")
try:
    print(open(LOG).read())
except OSError as e:
    print("no log:", e)
