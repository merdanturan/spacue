"""Tab accepts the menu selection (stock binding restored after), and usage
ranking: accepted candidates climb by a local TSV counter, per directory."""
import os, shutil, sys, time
sys.path.insert(0, os.path.dirname(__file__))
from pterm import Term

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "spacue.zsh"))
BASE = "/tmp/spacue-tstats"
STATS = BASE + "/stats.tsv"
REPO = BASE + "/repo"

RESULTS = []


def check(label, cond, extra=""):
    RESULTS.append((label, bool(cond)))
    mark = "OK  " if cond else "FAIL"
    print(f"  [{mark}] {label}{(' -- ' + extra) if extra else ''}")


# ------------------------------------------------------------- fixtures ---
shutil.rmtree(BASE, ignore_errors=True)
for d in ("alpha", "beta", "gamma", "repo"):
    os.makedirs(os.path.join(BASE, d), exist_ok=True)
with open(BASE + "/package.json", "w") as f:
    f.write('{"name":"demo","scripts":{"dev":"vite --port 3000","rebuild":"./rebuild.sh","meta-build":"./meta.sh","test":"vitest"}}\n')
subprocess_run = __import__("subprocess").run
subprocess_run(["git", "init", "-q", "-b", "main"], cwd=REPO, check=True)
subprocess_run(["git", "-C", REPO, "config", "user.email", "t@e.dev"], check=False)
subprocess_run(["git", "-C", REPO, "config", "user.name", "T"], check=False)
open(REPO + "/tracked.txt", "w").write("one\n")
subprocess_run(["git", "-C", REPO, "add", "."], check=True)
subprocess_run(["git", "-C", REPO, "commit", "-qm", "init"], check=True)
subprocess_run(["git", "-C", REPO, "branch", "feature-x"], check=True)


def seed(text):
    with open(STATS, "w") as f:
        f.write(text)


def content():
    with open(STATS) as f:
        return f.read()


def rows():
    return [l.strip() for l in t.screen.text().splitlines()]


def prompt_row():
    r = [l.strip() for l in rows() if "PS>" in l]
    return r[-1] if r else "<none>"


def pos(needle):
    """(row, col) of the first `needle` occurrence on the screen."""
    for i, l in enumerate(t.screen.text().splitlines()):
        j = l.find(needle)
        if j >= 0:
            return i, j
    return (9e9, 9e9)


def order_ok(above, below):
    """`above` must be printed before `below` (menus print candidates as
    columns on one row, so compare screen coordinates)."""
    a, b = pos(above), pos(below)
    return a < b, f"{above}{a} vs {below}{b}"


def clearline():
    t.send("\x01\x0b")  # C-a C-u... use C-a then C-u
    t.wait_idle(0.25)
    t.send("\x15")
    t.wait_idle(0.25)


def run_line():
    """Run the accepted line; the usage-count flush happens in precmd BEFORE
    the new prompt is drawn, so wait for the bare prompt (a plain
    wait_for("PS>") races -- the accepted line itself already shows PS>)."""
    t.send_keys("Enter")
    deadline = time.time() + 8
    while time.time() < deadline:
        t.wait_idle(0.1, 0.3)
        if prompt_row() == "PS>":
            time.sleep(0.35)
            return
    raise AssertionError("accepted command did not return to the prompt")


# -------------------------------------------------------------- session ---
t = Term(["zsh", "-f", "-i"], cols=110, rows=40, cwd=BASE,
         env={"SPACUE_STATS_FILE": STATS})
t.wait_idle(0.6, 6)
t.send("PS1='PS> '\n")
t.wait_for("PS>", 5)
t.send("unsetopt banghist 2>/dev/null\n")
t.wait_idle(0.2)
t.send("autoload -Uz compinit; compinit -u -C -d /tmp/spacue-zcompdump16\n")
t.wait_idle(1.0)
t.send(f"source {PLUGIN}\n")
t.wait_idle(0.6)
t.send("builtin cd " + BASE + "\n")
t.wait_idle(0.4)
t.send("clear\n")
t.wait_idle(0.3)

# S1: seeded ranking lifts "test" above alpha order; Tab accepts it
print("S1: ranking lifts used scripts; Tab accepts")
seed(f'npm:test\t3\t{BASE}\nnpm:run test\t3\t\nnpm:dev\t1\t\n')
t.send("npm run ")
t.wait_idle(1.3)
ok, extra = order_ok("vitest", "vite --port")
check("ranked order: test before dev", ok, extra)
t.send_keys("Tab")
t.wait_idle(0.8)
check("Tab accepts selection", prompt_row() == "PS> npm run test", prompt_row())
run_line()
c = content()
check("accept counted: dir 3->4", "npm:test\t4\t" + BASE in c, repr(c.splitlines()[:3]))
check("accept counted: global 0->1", "npm:test\t1\t\n" in c, repr(c.splitlines()[:3]))
clearline()

# S2: "run test" climbs the bare "npm " menu via the run-alias
print("S2: run-alias lifts the spaced candidate too")
t.send("npm ")
t.wait_idle(1.3)
ok, extra = order_ok("run test", "run dev")
check("'npm ' menu: run test before run dev", ok, extra)
t.send_keys("Tab")
t.wait_idle(0.8)
# word-kind lines are unescaped right at accept cleanup now (clean display)
check("Tab accept inserts clean text", prompt_row() == "PS> npm run test", prompt_row())
run_line()
c = content()
check("spaced accept counted", "npm:run test\t1\t" + BASE in c and "npm:test\t5\t" + BASE in c,
      repr([l for l in c.splitlines() if "npm:" in l][:4]))
clearline()

# S3: per-directory ranking in the repo
print("S3: per-directory ranking")
seed('git:main\t4\t' + REPO + '\n')
t.send("builtin cd " + REPO + "\n")
t.wait_idle(0.4)
t.send("clear\n")
t.wait_idle(0.3)
t.send("git checkout ")
t.wait_idle(1.4)
ok, extra = order_ok("main", "feature-x")
check("repo dir: main ranked above feature-x", ok, extra)
t.send_keys("Tab")
t.wait_idle(0.8)
check("Tab accept on branch", prompt_row() == "PS> git checkout main", prompt_row())
run_line()
c = content()
check("branch accept counted (dir 4->5)", "git:main\t5\t" + REPO in c, repr([l for l in c.splitlines() if "git:" in l][:2]))
clearline()

# S4: SPACUE_STATS=0 -- no ranking reorder, no writes
print("S4: SPACUE_STATS=0 disables everything")
seed('npm:test\t9\t' + REPO + '\n')
t.send("SPACUE_STATS=0\n")
t.wait_idle(0.3)
t.send("npm run ")
t.wait_idle(1.3)
ok, extra = order_ok("vite --port", "vitest")
check("disabled: natural alpha order back", ok, extra)
t.send_keys("Tab")
t.wait_idle(0.8)
# rank off -> alpha order; Tab accepts the highlighted first item (dev)
check("disabled: Tab still accepts", prompt_row() == "PS> npm run dev", prompt_row())
t.send_keys("Enter")
t.wait_for("PS>", 8)
c = content()
check("disabled: file untouched", c == 'npm:test\t9\t' + REPO + '\n', repr(c))
clearline()
t.send("SPACUE_STATS=1\n")
t.wait_idle(0.3)

# S5: cd path-kind Tab accept
print("S5: path-kind Tab accept")
t.send("builtin cd " + BASE + "\n")
t.wait_idle(0.4)
t.send("clear\n")
t.wait_idle(0.3)
t.send("cd ")
t.wait_idle(1.3)
t.send_keys("Down")
t.wait_idle(0.5)
t.send_keys("Down")
t.wait_idle(0.5)
t.send_keys("Tab")
t.wait_idle(0.8)
check("Tab accept inserts path", prompt_row() == "PS> cd beta/", prompt_row())
t.send_keys("Esc")
t.wait_idle(0.6)

# S6: menuselect Tab binding is restored to stock after the menu closes
print("S6: stock Tab binding restored")
t.send_keys("C-c")
t.wait_idle(0.3)
t.send('print "TBIND=$(bindkey -M menuselect \'\\t\')"\n')
t.wait_idle(0.6)
bline = [l for l in t.screen.text().splitlines() if "TBIND" in l][-1]
check("menuselect Tab back to stock", "complete-word" in bline, bline.strip())

t.close()

print()
fails = [l for l, ok in RESULTS if not ok]
print(f"RESULT: {len(RESULTS) - len(fails)}/{len(RESULTS)} passed")
for f in fails:
    print("  FAILED:", f)
sys.exit(1 if fails else 0)
