"""vi mode: Spacue menus in viins, accept/run, C-g and Esc dismissals
(Esc goes through the vi-cmd-mode wrapper), progressive typing, stock
menuselect bindings untouched, and no shield leaks after use."""
import sys, os, shutil
sys.path.insert(0, os.path.dirname(__file__))
from pterm import Term

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "spacue.zsh"))
BASE = "/tmp/spacue-demo"

# deterministic menus: own EMPTY stats file; ranking counts nothing
os.makedirs("/tmp/spacue-suite-stats", exist_ok=True)
STATS = "/tmp/spacue-suite-stats/diag14.tsv"
open(STATS, "w").close()
os.environ["SPACUE_STATS_FILE"] = STATS

RESULTS = []


def check(label, cond, extra=""):
    RESULTS.append((label, bool(cond)))
    mark = "OK  " if cond else "FAIL"
    print(f"  [{mark}] {label}{(' -- ' + extra) if extra else ''}")


# ------------------------------------------------------------- fixture ---
shutil.rmtree(BASE, ignore_errors=True)
for d in ("alpha", "beta", "gamma"):
    os.makedirs(os.path.join(BASE, d), exist_ok=True)
with open(BASE + "/package.json", "w") as f:
    f.write('{"name":"demo","scripts":{"dev":"vite --port 3000","build":"tsc -b","test":"vitest"}}\n')

# -------------------------------------------------------------- session ---
t = Term(["zsh", "-f", "-i"], cols=110, rows=34)
t.wait_idle(0.5, 5)
t.send("PS1='PS> '\n")
t.wait_for("PS>", 5)
t.send("autoload -Uz compinit; compinit -u -C -d /tmp/spacue-zcompdump\n")
t.wait_idle(1.0)
t.send("bindkey -v\n")
t.wait_idle(0.3)
t.send(f"source {PLUGIN}\n")
t.wait_idle(0.8)
t.send(f"builtin cd {BASE}\n")
t.wait_idle(0.5)
t.send("clear\n")
t.wait_idle(0.4)


def screen():
    return t.screen.text()


def rows_with(needle):
    return [l for l in screen().splitlines() if needle in l]


def prompt_row():
    r = [l.strip() for l in screen().splitlines() if "PS>" in l]
    return r[-1] if r else "<none>"


def clearline():
    # Deterministic reset to an empty insert-mode line in vi: Esc is
    # idempotent in vicmd, dd kills the line without leaving vicmd, and i
    # enters insert. (Ctrl-U and cc both behave differently per mode.)
    t.send_keys("Esc")
    t.wait_idle(0.3)
    t.send("dd")
    t.wait_idle(0.3)
    t.send("i")
    t.wait_idle(0.3)


def ding():
    clearline()
    t.send('echo DING$(( 1 + 1 ))\n')
    t.wait_idle(0.5)
    return "DING2" in screen()


def bind_state():
    """(menuselect Esc, menuselect C-g, emacs Esc, viins Tab) as printed by
    bindkey; single shell round-trip, read from the file so screen wrapping
    of the echoed command line cannot produce false matches."""
    binds = "/tmp/spacue-binds.txt"
    try:
        os.remove(binds)
    except FileNotFoundError:
        pass
    t.send(f"bindkey -M menuselect '^[' > {binds}; "
           f"bindkey -M menuselect '^G' >> {binds}; "
           f"bindkey -M emacs '^[' >> {binds}; "
           f"bindkey -M viins '^I' >> {binds}\n")
    t.wait_idle(0.8)
    with open(binds) as f:
        out = [l.strip() for l in f if l.strip()]
    return out[-4:]


def clear():
    t.send("clear\n")
    t.wait_idle(0.3)


print("S1: initial bindings untouched (no spacue state)")
mn_esc, mn_g, em_esc, vi_tab = bind_state()
check("viins Tab is stock expand-or-complete", "expand-or-complete" in vi_tab, vi_tab)
check("menuselect Esc stock (undefined-key)", "undefined-key" in mn_esc, mn_esc)
check("menuselect C-g stock (undefined-key)", "undefined-key" in mn_g, mn_g)
clear()

print("S2: spacue menu opens in viins; Down + Enter accepts; Enter runs")
t.send("cd ")
t.wait_idle(1.3)
check("menu open in vi mode", bool(rows_with("beta/")) and bool(rows_with("gamma/")))
t.send_keys("Down")
t.wait_idle(0.45)
check("Down moves selection", prompt_row() == "PS> cd alpha/", prompt_row())
t.send_keys("Enter")
t.wait_idle(0.9)
check("Enter accepts alpha/", prompt_row() == "PS> cd alpha/", prompt_row())
t.send_keys("Enter")
t.wait_idle(0.6)
t.send("pwd\n")
t.wait_idle(0.5)
check("second Enter ran cd", any("spacue-demo/alpha" in l for l in screen().splitlines()))
clearline()
t.send(f"builtin cd {BASE}\n")
t.wait_idle(0.4)
clear()

print("S3: C-g dismisses the menu and keeps the typed line")
t.send("cd ")
t.wait_idle(1.3)
check("menu open", bool(rows_with("beta/")))
t.send_keys("C-g")
t.wait_idle(0.9)
check("menu gone", not rows_with("beta/"))
check("line kept", prompt_row() in ("PS> cd", "PS> cd "), prompt_row())
check("typing works after C-g", ding())

print("S4: Esc dismissal goes through vi-cmd-mode (line kept, insert recovers)")
t.send("cd ")
t.wait_idle(1.3)
check("menu open", bool(rows_with("beta/")))
t.send_keys("Esc")
t.wait_idle(1.0)
check("menu gone after Esc", not rows_with("beta/"))
check("line kept after Esc", prompt_row() in ("PS> cd", "PS> cd "), prompt_row())
t.send("i")
t.wait_idle(0.3)
check("typing works after Esc+i", ding())

print("S5: typing mid-menu narrows to a single match (viins)")
t.send("cd ")
t.wait_idle(1.3)
t.send("g")
t.wait_idle(1.0)
check("auto-completed to 'cd gamma/'", prompt_row() == "PS> cd gamma/", prompt_row())
clearline()
t.send(f"builtin cd {BASE}\n")
t.wait_idle(0.4)
clear()

print("S6: stock native menu after a dismiss; Esc is stock; no shield leaks")
t.send("cd ")
t.wait_idle(1.3)
t.send_keys("C-g")
t.wait_idle(0.8)
t.send_keys("Tab")
t.wait_idle(0.9)
t.send_keys("Tab")
t.wait_idle(1.2)
check("stock menu opens (native unaffected)", bool(rows_with("beta/")), prompt_row())
t.send_keys("Esc")
t.wait_idle(1.0)
clearline()
mn_esc, mn_g, em_esc, vi_tab = bind_state()
check("menuselect Esc back to stock (undefined-key)", "undefined-key" in mn_esc, mn_esc)
check("menuselect C-g back to stock (undefined-key)", "undefined-key" in mn_g, mn_g)
check("emacs Esc back to stock (undefined-key)", "undefined-key" in em_esc, em_esc)
check("typing works after everything", ding())
clear()

print("S7: npm menu in viins still fuzzy-completes")
t.send("npm ")
t.wait_idle(1.3)
t.send("b")
t.wait_idle(1.0)
check("fuzzy completed 'npm run build'", prompt_row() == "PS> npm run build", prompt_row())
clearline()

t.send("clear\n")
t.wait_idle(0.3)
t.close()

print()
fails = [l for l, ok in RESULTS if not ok]
print(f"RESULT: {len(RESULTS) - len(fails)}/{len(RESULTS)} passed")
for f in fails:
    print("  FAILED:", f)
sys.exit(1 if fails else 0)
