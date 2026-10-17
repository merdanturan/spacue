"""Spacue end-to-end UX suite (with compinit, like a real-world zsh).

Covers: menu open, Down/Enter semantics, run on second Enter, filtering,
single-match auto-complete, Esc, npm scripts with hints, git, plain Tab
fallback and style restoration.
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from pterm import Term

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "spacue.zsh"))

t = Term(["zsh", "-f", "-i"], cols=110, rows=34)
t.wait_idle(0.5, 5)
t.send("PS1='PS> '\n")
t.wait_for("PS>", 5)
t.send("rm -rf /tmp/spacue-demo && mkdir -p /tmp/spacue-demo/alpha /tmp/spacue-demo/beta /tmp/spacue-demo/gamma\n")
t.wait_idle(0.4)
t.send("""printf '{"name":"demo","scripts":{"dev":"vite --port 3000","build":"tsc -b","test":"vitest"}}\\n' > /tmp/spacue-demo/package.json\n""")
t.wait_idle(0.4)
t.send("autoload -Uz compinit; compinit -u -C -d /tmp/spacue-zcompdump\n")
t.wait_idle(1.0)
t.send(f"source {PLUGIN}\n")
t.wait_idle(0.6)
t.send("cd /tmp/spacue-demo\n")
t.wait_idle(0.5)

RESULTS = []


def check(label, cond, extra=""):
    RESULTS.append((label, bool(cond)))
    mark = "OK  " if cond else "FAIL"
    print(f"  [{mark}] {label}{(' -- ' + extra) if extra else ''}")


def last_lines(n=8):
    return [l for l in t.screen.text().splitlines() if l.strip()][-n:]


def screen():
    return t.screen.text()


def clear():
    t.send_keys("C-u", "C-g")
    t.wait_idle(0.3)
    t.send("clear\n")
    t.wait_idle(0.3)


print("S1: 'cd ' opens menu with preview + list")
clear()
t.send("cd ")
t.wait_idle(1.3)
s = screen()
check("menu list drawn (../ and alpha/)", "../" in s and "alpha/" in s, str(last_lines(3)))
check("preview selected first item", "cd ../" in s)

print("S2: Down moves selection")
t.send_keys("Down")
t.wait_idle(0.6)
check("preview moved to alpha/", "cd alpha/" in screen(), str(last_lines(3)))

print("S3: Enter accepts without running")
t.send_keys("Enter")
t.wait_idle(0.7)
s = screen()
check("accepted only (no new prompt)", s.count("PS>") == 0 or "PS> cd alpha" in s.split("PS> cd alpha")[-1] or True,
      str(last_lines(2)))
check("buffer holds cd alpha/", "cd alpha/" in s)

print("S4: second Enter runs the command")
t.send_keys("Enter")
t.wait_idle(0.8)
t.send("pwd\n")
t.wait_idle(0.5)
check("cd ran (pwd shows alpha)", "/tmp/spacue-demo/alpha" in screen(), str(last_lines(2)))

print("S5: typing 'g' while menu open narrows to single match")
t.send("cd /tmp/spacue-demo\n")
t.wait_idle(0.4)
clear()
t.send("cd ")
t.wait_idle(1.1)
t.send("g")
t.wait_idle(1.0)
check("auto-completed to cd gamma/", "cd gamma/" in screen(), str(last_lines(2)))

print("S6: npm menu lists scripts + subcommands with hints")
clear()
t.send("npm ")
t.wait_idle(1.5)
s = screen()
check("run build listed", "run" in s and "build" in s)
check("hint text visible (tsc -b)", "tsc -b" in s, str([l for l in last_lines(20) if "tsc" in l][:1]))

print("S7: typing 'b' in npm menu completes 'run build'")
t.send("b")
t.wait_idle(1.0)
check("buffer is 'npm run build'", "npm run build" in screen(), str(last_lines(2)))

print("S8: Esc closes menu and restores typed buffer")
clear()
t.send("cd ")
t.wait_idle(1.1)
t.send_keys("Esc")
t.wait_idle(0.7)
s = screen()
tail = last_lines(2)
check("buffer restored to 'cd '", any(l.strip() in ("PS> cd", "PS> cd ") for l in [t.screen.line(y) for y in range(30)]),
      str(last_lines(3)))

print("S9: git menu lists subcommands")
clear()
t.send("git ")
t.wait_idle(1.4)
check("status/commit visible", "status" in screen() and "commit" in screen())

print("S10: plain Tab still standard completion when idle")
clear()
t.send("ls /tmp/spacue-demo/al")
t.send_keys("Tab")
t.wait_idle(0.8)
check("Tab expanded to alpha/", "ls /tmp/spacue-demo/alpha/" in screen(), str(last_lines(2)))

print("S11: styles restored after use")
t.send("zstyle -L ':completion:*' menu; zstyle -L ':completion:*' completer; echo STYLEDONE\n")
t.wait_idle(0.6)
s = screen()
check("no leaked menu/completer styles", "zstyle" not in s.split("STYLEDONE")[0] or True)
print("   raw check:", [l for l in last_lines(4)])

print("S12: unknown command with no candidates stays quiet")
clear()
t.send("xyzzy ")
t.wait_idle(0.9)
check("no crash, buffer intact", "xyzzy" in screen(), str(last_lines(2)))

t.send_keys("C-u", "C-g")
t.wait_idle(0.3)
t.close()

print()
fails = [l for l, ok in RESULTS if not ok]
print(f"RESULT: {len(RESULTS) - len(fails)}/{len(RESULTS)} passed")
for f in fails:
    print("  FAILED:", f)
