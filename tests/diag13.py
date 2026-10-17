"""Spacue in a bare zsh: no compinit has been run, so the plugin loads the
completion system itself (SPACUE_COMPINIT=1, the default).  A full
menu/accept/run cycle must work.  With SPACUE_COMPINIT=0 the plugin must
stay out and never break the shell."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from pterm import Term

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "spacue.zsh"))

RESULTS = []


def check(label, cond, extra=""):
    RESULTS.append((label, bool(cond)))
    mark = "OK  " if cond else "FAIL"
    print(f"  [{mark}] {label}{(' -- ' + extra) if extra else ''}")


def prompt_row(t):
    r = [l.strip() for l in t.screen.text().splitlines() if "PS>" in l]
    return r[-1] if r else "<none>"


def boot(extra=""):
    t = Term(["zsh", "-f", "-i"], cols=110, rows=34)
    t.wait_idle(0.5, 5)
    t.send("PS1='PS> '\n")
    t.wait_for("PS>", 5)
    t.send("export HOME=/tmp/spacue-demo/home && mkdir -p $HOME\n")
    t.wait_idle(0.3)
    if extra:
        t.send(extra + "\n")
        t.wait_idle(0.3)
    return t


os.system("rm -rf /tmp/spacue-demo && mkdir -p /tmp/spacue-demo/alpha /tmp/spacue-demo/beta /tmp/spacue-demo/gamma /tmp/spacue-demo/home")

print("S1: default SPACUE_COMPINIT=1 loads the completion system itself")
t = boot()
t.send(f"source {PLUGIN}\n")
t.wait_idle(0.8)
t.send("(( $+functions[_main_complete] )) && echo MAIN_OK || echo MAIN_NO\n")
t.wait_idle(0.4)
check("compinit auto-loaded", "MAIN_OK" in t.screen.text())

t.send("cd /tmp/spacue-demo\n")
t.wait_idle(0.4)
t.send("clear\n")
t.wait_idle(0.3)
t.send("cd ")
t.wait_idle(1.3)
check("menu opens with no user compinit", "beta/" in t.screen.text())
t.send_keys("Down")
t.wait_idle(0.4)
t.send_keys("Enter")
t.wait_idle(0.9)
check("Down+Enter accepts 'cd alpha/'", prompt_row(t) == "PS> cd alpha/", prompt_row(t))
t.send_keys("Enter")
t.wait_idle(0.6)
t.send("pwd\n")
t.wait_idle(0.5)
check("second Enter runs it", "/tmp/spacue-demo/alpha" in t.screen.text())
t.send("builtin cd /tmp/spacue-demo\n")
t.wait_idle(0.4)
t.send("cd ")
t.wait_idle(1.3)
t.send_keys("C-g")
t.wait_idle(0.9)
check("C-g dismisses cleanly", not [l for l in t.screen.text().splitlines() if "beta/" in l] and prompt_row(t) in ("PS> cd", "PS> cd "), prompt_row(t))
t.send("\x01\x0b\x01\x0b")
t.send('echo DING$(( 1 + 1 ))\n')
t.wait_idle(0.5)
check("typing works after all that", "DING2" in t.screen.text())
t.close()

print("S2: SPACUE_COMPINIT=0 stays out")
t = boot("(( $+functions[_main_complete] )) && echo MAIN_OK || echo MAIN_NO")
check("compinit really absent before source", "MAIN_NO" in t.screen.text())
t.send(f"SPACUE_COMPINIT=0; source {PLUGIN}\n")
t.wait_idle(0.8)
t.send("(( $+functions[_main_complete] )) && echo MAIN_OK || echo MAIN_NO\n")
t.wait_idle(0.4)
check("plugin did not auto-load compinit", "MAIN_NO" in t.screen.text())
t.send("cd /tmp/spacue-demo\n")
t.wait_idle(0.4)
t.send("\x01\x0b")
t.send("cd ")
t.wait_idle(1.2)
print("    [debug] row after 'cd ' + space:", prompt_row(t))
check("space stays a plain space (no completion fired)", prompt_row(t) in ("PS> cd", "PS> cd "), prompt_row(t))
t.send("\x01\x0b\x01\x0b")
t.send('echo DING$(( 1 + 1 ))\n')
t.wait_idle(0.5)
check("shell still usable", "DING2" in t.screen.text())
t.close()

print()
fails = [l for l, ok in RESULTS if not ok]
print(f"RESULT: {len(RESULTS) - len(fails)}/{len(RESULTS)} passed")
for f in fails:
    print("  FAILED:", f)
sys.exit(1 if fails else 0)
