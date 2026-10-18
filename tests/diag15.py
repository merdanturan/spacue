"""Per-command providers: git branches/changed files, make targets with
comment hints, ssh hosts from ~/.ssh/config, kill PIDs from ps, sudo
command names, and the npm fuzzy menu (non-prefix matches via -U)."""
import sys, os, shutil, subprocess
sys.path.insert(0, os.path.dirname(__file__))
from pterm import Term

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "spacue.zsh"))
BASE = "/tmp/spacue-demo"

# deterministic menus: own EMPTY stats file; ranking counts nothing
# (seeding happens per-scenario below)
os.makedirs("/tmp/spacue-suite-stats", exist_ok=True)
STATS = "/tmp/spacue-suite-stats/diag15.tsv"
open(STATS, "w").close()
os.environ["SPACUE_STATS_FILE"] = STATS

RESULTS = []


def check(label, cond, extra=""):
    RESULTS.append((label, bool(cond)))
    mark = "OK  " if cond else "FAIL"
    print(f"  [{mark}] {label}{(' -- ' + extra) if extra else ''}")


# ------------------------------------------------------------- fixtures ---
shutil.rmtree(BASE, ignore_errors=True)
for d in ("alpha", "beta", "gamma", "home/.ssh", "repo"):
    os.makedirs(os.path.join(BASE, d), exist_ok=True)
with open(BASE + "/package.json", "w") as f:
    f.write('{"name":"demo","scripts":{"dev":"vite --port 3000","rebuild":"./rebuild.sh","meta-build":"./meta.sh","test":"vitest"}}\n')
with open(BASE + "/Makefile", "w") as f:
    f.write("build:\n\t@echo building\n\ntest: ## run the tests\n\t@echo testing\n\ndeploy: ## ship it\n\t@echo deploying\n\n.PHONY: build test deploy\n")
with open(BASE + "/home/.ssh/config", "w") as f:
    f.write("Host prodbox\n  HostName 10.0.0.1\n\nHost stagebox\n  HostName 10.0.0.2\n")
repo = BASE + "/repo"
subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo)
subprocess.run(["git", "config", "user.name", "Test"], cwd=repo)
with open(repo + "/tracked.txt", "w") as f:
    f.write("one\n")
subprocess.run(["git", "add", "."], cwd=repo, check=True)
subprocess.run(["git", "commit", "-qm", "init"], cwd=repo, check=True)
subprocess.run(["git", "branch", "feature-x"], cwd=repo, check=True)
with open(repo + "/tracked.txt", "a") as f:
    f.write("two\n")

# -------------------------------------------------------------- session ---
t = Term(["zsh", "-f", "-i"], cols=110, rows=34)
t.wait_idle(0.5, 5)
t.send("PS1='PS> '\n")
t.wait_for("PS>", 5)
t.send("unsetopt banghist 2>/dev/null\n")   # '!' in test strings must stay literal
t.wait_idle(0.2)
t.send(f"export HOME={BASE}/home\n")
t.wait_idle(0.3)
t.send("autoload -Uz compinit; compinit -u -C -d /tmp/spacue-zcompdump\n")
t.wait_idle(1.0)
t.send(f"source {PLUGIN}\n")
t.wait_idle(0.6)
t.send(f"builtin cd {BASE}\n")
t.wait_idle(0.4)
t.send("clear\n")
t.wait_idle(0.3)


def screen():
    return t.screen.text()


def rows_with(needle):
    return [l for l in screen().splitlines() if needle in l]


def prompt_row():
    r = [l.strip() for l in screen().splitlines() if "PS>" in l]
    return r[-1] if r else "<none>"


def clearline():
    t.send("\x01\x0b\x01\x0b")
    t.wait_idle(0.2)


print("S1: git checkout lists branches")
t.send(f"builtin cd {BASE}/repo\n")
t.wait_idle(0.4)
t.send("clear\n")
t.wait_idle(0.3)
t.send("git checkout ")
t.wait_idle(1.4)
check("branch feature-x listed", bool(rows_with("feature-x")), str(rows_with("feature-x")[:2]))
t.send_keys("Esc")
t.wait_idle(0.8)

print("S2: git commit lists changed files")
clearline()
t.send("git commit ")
t.wait_idle(1.2)
check("changed file tracked.txt listed", bool(rows_with("tracked.txt")), str(rows_with("tracked.txt")[:2]))
t.send_keys("Esc")
t.wait_idle(0.8)

print("S3: make lists targets with comment hints")
clearline()
t.send(f"builtin cd {BASE}\n")
t.wait_idle(0.4)
t.send("clear\n")
t.wait_idle(0.3)
t.send("make ")
t.wait_idle(1.2)
check("targets listed", "build" in screen() and "deploy" in screen())
check("hint from ## comment", "run the tests" in screen(), str([l for l in screen().splitlines() if "tests" in l][:1]))
t.send_keys("Esc")
t.wait_idle(0.8)

print("S4: ssh lists hosts from ~/.ssh/config")
clearline()
t.send("ssh ")
t.wait_idle(1.2)
check("prodbox + stagebox listed", "prodbox" in screen() and "stagebox" in screen())
t.send_keys("Esc")
t.wait_idle(0.8)

print("S5: kill lists running PIDs")
clearline()
t.send('sleep 987 & echo "SPID=$!"\n')
t.wait_idle(0.5)
m = [l for l in screen().splitlines() if "SPID=" in l and "PS>" not in l and "$!" not in l]
spid = m[-1].split("SPID=")[-1].strip() if m else "???"
clearline()
t.send("clear\n")
t.wait_idle(0.3)
t.send("kill ")                        # fresh space: the pid menu opens
t.wait_idle(1.4)
check("menu shows fresh pid with sleep hint",
      any(spid in l and "sleep" in l for l in screen().splitlines()),
      f"pid={spid}; matches={[l for l in screen().splitlines() if spid in l or 'sleep' in l]}")
t.send(spid)                           # chunk typed into the open menu
t.wait_idle(1.4)
check("pid inserted by typing", prompt_row() == f"PS> kill {spid}", prompt_row())
t.send_keys("Esc")
t.wait_idle(0.8)
clearline()
t.send("kill %1 2>/dev/null\n")
t.wait_idle(0.3)

print("S6: sudo lists command names")
clearline()
t.send("clear\n")
t.wait_idle(0.3)
t.send("sudo ")                        # fresh space: the command menu opens
t.wait_idle(1.4)
t.send("autol")                        # chunk typed into the open menu
t.wait_idle(1.4)
check("commands filtered by prefix", prompt_row() == "PS> sudo autoload", prompt_row())
t.send_keys("Esc")
t.wait_idle(0.8)

print("S7: npm fuzzy menu (non-prefix matches via -U)")
clearline()
t.send("npm ")
t.wait_idle(1.3)
t.send("run il")                # ends in a two-match fuzzy menu: rebuild + meta-build
t.wait_idle(1.4)
row1 = prompt_row()
check("fuzzy menu shows both scripts", "rebuild" in screen() and "meta-build" in screen())
check("first preview is one of them", row1 in ("PS> npm run rebuild", "PS> npm run meta-build"), row1)
t.send_keys("Down")
t.wait_idle(0.5)
row2 = prompt_row()
check("Down moved to the other one", row2 in ("PS> npm run rebuild", "PS> npm run meta-build") and row2 != row1, row2)
t.send_keys("Enter")
t.wait_idle(0.8)
check("Enter accepts the selected one", prompt_row() == row2, prompt_row())
clearline()

t.send("clear\n")
t.wait_idle(0.3)
t.send('echo DING$(( 1 + 1 ))\n')
t.wait_idle(0.5)
check("typing still works", "DING2" in screen())
t.close()

print()
fails = [l for l, ok in RESULTS if not ok]
print(f"RESULT: {len(RESULTS) - len(fails)}/{len(RESULTS)} passed")
for f in fails:
    print("  FAILED:", f)
sys.exit(1 if fails else 0)
