"""Verify v2 finalize logic against the unmodified plugin:
S1 Tab-accept stays exactly the selection (no stock re-completion),
S2 burst typing still lands on the narrowed candidate,
S3 git-checkout Tab-accept leaves just the branch (tracked.txt bug gone)."""
import os, shutil, subprocess, sys
sys.path.insert(0, os.path.dirname(__file__))
from pterm import Term

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "spacue.zsh"))
BASE = "/tmp/spacue-peek2"
REPO = BASE + "/repo"
STATS = BASE + "/stats.tsv"

shutil.rmtree(BASE, ignore_errors=True)
for d in ("alpha", "beta", "gamma", "repo"):
    os.makedirs(os.path.join(BASE, d), exist_ok=True)
with open(STATS, "w") as f:
    f.write(f'git:main\t2\t{REPO}\n')
subprocess.run(["git", "init", "-q", "-b", "main"], cwd=REPO, check=True)
subprocess.run(["git", "-C", REPO, "config", "user.email", "t@e.dev"], check=True)
subprocess.run(["git", "-C", REPO, "config", "user.name", "T"], check=True)
open(REPO + "/tracked.txt", "w").write("one\n")
subprocess.run(["git", "-C", REPO, "add", "."], check=True)
subprocess.run(["git", "-C", REPO, "commit", "-qm", "init"], check=True)
subprocess.run(["git", "-C", REPO, "branch", "feature-x"], check=True)

t = Term(["zsh", "-f", "-i"], cols=110, rows=40, cwd=BASE,
         env={"SPACUE_STATS_FILE": STATS})
t.wait_idle(0.6, 6)
t.send("PS1='PS> '\n")
t.wait_for("PS>", 5)
t.send("autoload -Uz compinit; compinit -u -C -d /tmp/spzdump-peek2\n")
t.wait_idle(1.0)
t.send(f"source {PLUGIN}\n")
t.wait_idle(0.6)
t.send("cd '\n") if False else None
t.send("clear\n")
t.wait_idle(0.3)

def pr():
    return [l.strip() for l in t.screen.text().splitlines() if "PS>" in l][-1]

# S1: menu -> Tab accept; then continue typing x -- state must be DEAD (no wipe)
t.send("cd ")
t.wait_idle(1.3)
t.send_keys("Tab")
t.wait_idle(0.8)
print("S1 post-Tab   :", pr())
t.send_keys("Esc")            # cleanup check: Esc should do nothing weird now
t.wait_idle(0.5)
t.send("x")
t.wait_idle(0.5)
print("S1 post-Esc+x :", pr(), "(want 'cd beta x' err... just watch)")
t.send("\x15")                # C-u clear line
t.wait_idle(0.3)

# S2: burst typing cd bet
t.send("cd ")
t.wait_idle(1.3)
t.send("bet")
t.wait_idle(1.6)
print("S2 burst      :", pr(), "(want 'PS> cd beta/')")
t.send("\x15")
t.wait_idle(0.3)

# S3: git checkout Tab-accept in repo
t.send("builtin cd " + REPO + "\n")
t.wait_idle(0.4)
t.send("clear\n")
t.wait_idle(0.3)
t.send("git checkout ")
t.wait_idle(1.4)
print("S3 menu       :", [l.strip() for l in t.screen.text().splitlines()][-2:])
t.send_keys("Tab")
t.wait_idle(0.9)
print("S3 post-Tab   :", pr(), "(want 'PS> git checkout main')")
t.close()
