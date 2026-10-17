"""Spacue end-to-end UX suite (with compinit, like a real-world zsh).

Covers: menu open + preview, Down/Enter accept semantics (no trailing
space), run on second Enter, prefix filtering, progressive typing
(including type-ahead), Esc/C-g dismissal, npm scripts with hints, git
subcommands, plain-Tab fallback, style restoration, generic file
fallback, stock completion after accept.
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from pterm import Term

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "spacue.zsh"))

t = Term(["zsh", "-f", "-i"], cols=110, rows=34)
t.wait_idle(0.5, 5)
t.send("PS1='PS> '\n")
t.wait_for("PS>", 5)
t.send("rm -rf /tmp/spacue-demo && mkdir -p /tmp/spacue-demo/alpha/deep1 /tmp/spacue-demo/alpha/deep2 /tmp/spacue-demo/beta /tmp/spacue-demo/gamma\n")
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


def screen():
    return t.screen.text()


def last_lines(n=8):
    return [l for l in screen().splitlines() if l.strip()][-n:]


def rows_with(needle):
    return [l for l in screen().splitlines() if needle in l]


def prompt_row():
    r = [l.strip() for l in screen().splitlines() if "PS>" in l]
    return r[-1] if r else "<none>"


def ps_rows():
    return [l for l in screen().splitlines() if "PS>" in l]


def clearline():
    # C-a C-k twice: safe even if a stray Esc prefix byte is pending
    t.send("\x01\x0b\x01\x0b")
    t.wait_idle(0.2)


def clear():
    clearline()
    t.send("clear\n")
    t.wait_idle(0.3)


def ding():
    clear()
    t.send('echo DING$(( 1 + 1 ))\n')
    t.wait_idle(0.5)
    return "DING2" in screen()


print("S1: 'cd ' opens menu with preview + full listing")
clear()
t.send("cd ")
t.wait_idle(1.3)
s = screen()
check("listing has ../ alpha/ beta/ gamma/", all(x in s for x in ("../", "alpha/", "beta/", "gamma/")), str(last_lines(3)))
check("preview shows first item (cd ../)", prompt_row() == "PS> cd ../", prompt_row())

print("S2: Down moves selection")
t.send_keys("Down")
t.wait_idle(0.6)
check("preview moved to alpha/", prompt_row() == "PS> cd alpha/", prompt_row())

print("S3: Enter accepts without running (no trailing space)")
t.send_keys("Enter")
t.wait_idle(0.7)
check("buffer is exactly 'cd alpha/'", prompt_row() == "PS> cd alpha/", prompt_row())
check("still one prompt (nothing ran)", len(ps_rows()) == 1, str(len(ps_rows())))

print("S4: second Enter runs the command")
t.send_keys("Enter")
t.wait_idle(0.8)
t.send("pwd\n")
t.wait_idle(0.5)
check("cd ran (pwd shows alpha)", "/tmp/spacue-demo/alpha" in screen(), str(last_lines(2)))

print("S5: typing 'g' while menu open narrows to single match")
t.send("builtin cd /tmp/spacue-demo\n")
t.wait_idle(0.4)
clear()
t.send("cd ")
t.wait_idle(1.2)
t.send("g")
t.wait_idle(1.0)
check("auto-completed to exactly 'cd gamma/'", prompt_row() == "PS> cd gamma/", prompt_row())

print("S6: npm menu lists scripts + subcommands with hints")
clear()
t.send("npm ")
t.wait_idle(1.5)
s = screen()
check("scripts and subcommands listed", "run build" in s and "run test" in s and "publish" in s)
check("hint text visible (tsc -b)", "tsc -b" in s, str([l for l in last_lines(20) if "tsc" in l][:1]))

print("S7: typing 'b' in npm menu completes 'run build'")
t.send("b")
t.wait_idle(1.0)
check("buffer is exactly 'npm run build'", prompt_row() == "PS> npm run build", prompt_row())

print("S8: Esc: live state keeps the line; open menu closes, keeps typed text")
n0 = len(t.raw)
t.send_keys("Esc")
t.wait_idle(0.9)
check("filtered line survives Esc", prompt_row() == "PS> npm run build", prompt_row())
check("no BEL from accept/Esc", t.raw[n0:].count(b"\x07") == 0, str(t.raw[n0:].count(b"\x07")))
clear()
t.send("cd ")
t.wait_idle(1.2)
t.send_keys("Esc")
t.wait_idle(1.1)
check("menu closed, buffer back to 'cd'", prompt_row() in ("PS> cd", "PS> cd "), prompt_row())
check("listing gone", not rows_with("gamma/"))
check("typing still works", ding())

print("S9: git menu lists subcommands")
clear()
t.send("git ")
t.wait_idle(1.4)
check("status/commit/checkout visible", all(x in screen() for x in ("status", "commit", "checkout")))
t.send_keys("Esc")
t.wait_idle(0.9)

print("S10: plain Tab still standard completion when idle")
clear()
t.send("ls /tmp/spacue-demo/al")
t.send_keys("Tab")
t.wait_idle(0.8)
check("Tab expanded to alpha/", prompt_row() == "PS> ls /tmp/spacue-demo/alpha/", prompt_row())
t.send_keys("Enter")
t.wait_idle(0.8)
check("expanded line runs (new prompt below)", len(ps_rows()) == 2, str(len(ps_rows())))

print("S11: no leaked zstyles after use")
clear()
t.send("zstyle -L ':completion:*' menu; zstyle -L ':completion:*' completer; zstyle -L ':completion:*' verbose; echo STYLE_RC=$?; echo STYLE_END\n")
t.wait_idle(0.6)
leaked = [l for l in screen().splitlines() if l.strip().startswith("zstyle ")]
check("no leaked styles, plain env restored", not leaked and "STYLE_RC=1" in screen(), str(leaked[:2]))

print("S12: unknown command falls back to file candidates")
clear()
t.send("xyzzy ")
t.wait_idle(1.0)
s = screen()
check("cwd entries listed", all(x in s for x in ("alpha/", "beta/", "gamma/", "package.json")))
t.send_keys("Esc")
t.wait_idle(0.9)
check("Esc restores typed line", prompt_row() in ("PS> xyzzy", "PS> xyzzy "), prompt_row())

print("S13: after accept, stock completion works (no stale spacue items)")
clear()
t.send("zstyle ':completion:*' menu select\n")
t.wait_idle(0.3)
t.send("cd ")
t.wait_idle(1.2)
t.send_keys("Down")
t.wait_idle(0.4)
t.send_keys("Enter")
t.wait_idle(0.9)
check("accepted 'cd alpha/'", prompt_row() == "PS> cd alpha/", prompt_row())
t.send("\x0c")                     # Ctrl-L: wipe listing, keep buffer
t.wait_idle(0.5)
# stock menu-select needs: Tab -> common prefix, Tab -> list, Tab -> menu
for _ in range(3):
    if "deep1/" in prompt_row():
        break
    t.send_keys("Tab")
    t.wait_idle(1.0)
check("stock menu previews alpha/deep1/", prompt_row() == "PS> cd alpha/deep1/", prompt_row())
check("deep children listed", bool(rows_with("deep1/") and rows_with("deep2/")))
check("no stale spacue candidates (beta/ absent)", not rows_with("beta/"))
t.send_keys("C-g")
t.wait_idle(1.0)
check("C-g restores stock line 'cd alpha/deep'", prompt_row() == "PS> cd alpha/deep", prompt_row())
clearline()
t.send("zstyle -d ':completion:*' menu\n")
t.wait_idle(0.3)

print("S14: typing mid-menu filters live; typed text is the base")
clear()
t.send("cd ")
t.wait_idle(1.2)
t.send("b")
t.wait_idle(0.9)
check("'b' narrows to 'cd beta/'", prompt_row() == "PS> cd beta/", prompt_row())
t.send("x")
t.wait_idle(0.9)
check("'x' restarts from typed text ('cd bx')", prompt_row() == "PS> cd bx", prompt_row())
check("stale listing dropped", not rows_with("gamma/"))
check("typing still works", ding())

print("S15: type-ahead chunks are lossless (fast typing / paste)")
clear()
t.send("cd ")
t.wait_idle(1.2)
t.send("bet")                      # one burst: b, e, t
t.wait_idle(1.0)
check("burst lands on 'cd beta/'", prompt_row() == "PS> cd beta/", prompt_row())
clear()
t.send("npm ")
t.wait_idle(1.3)
t.send("ild")                      # fuzzy burst: must not leak native npm completion
t.wait_idle(1.2)
check("burst fuzzy-completes 'npm run build'", prompt_row() == "PS> npm run build", prompt_row())
check("no native npm listing leaked in", not rows_with("access"))

t.send_keys("C-u", "C-g")
t.wait_idle(0.3)
t.close()

print()
fails = [l for l, ok in RESULTS if not ok]
print(f"RESULT: {len(RESULTS) - len(fails)}/{len(RESULTS)} passed")
for f in fails:
    print("  FAILED:", f)
sys.exit(1 if fails else 0)
