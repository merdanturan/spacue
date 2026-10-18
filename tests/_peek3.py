"""Log-only observation of the v2 finalize during three scenes:
S1 Tab-accept (swallow+cleanup expected), S2 burst typing (pushback, no
cleanup expected), S3 git-checkout Tab-accept (tracked.txt bug check)."""
import os, shutil, subprocess, sys
sys.path.insert(0, os.path.dirname(__file__))
from pterm import Term

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "spacue.zsh"))
BASE = "/tmp/spacue-peek3"
REPO = BASE + "/repo"
TRACE = "/tmp/trace-peek3"

shutil.rmtree(BASE, ignore_errors=True)
for d in ("alpha", "beta", "gamma", "repo"):
    os.makedirs(os.path.join(BASE, d), exist_ok=True)
subprocess.run(["git", "init", "-q", "-b", "main"], cwd=REPO, check=True)
subprocess.run(["git", "-C", REPO, "config", "user.email", "t@e.dev"], check=True)
subprocess.run(["git", "-C", REPO, "config", "user.name", "T"], check=True)
open(REPO + "/tracked.txt", "w").write("one\n")
subprocess.run(["git", "-C", REPO, "add", "."], check=True)
subprocess.run(["git", "-C", REPO, "commit", "-qm", "init"], check=True)
subprocess.run(["git", "-C", REPO, "branch", "feature-x"], check=True)

with open(PLUGIN) as f:
    src = f.read()

HOOK = "      _spacue_stats_note   # count the accepted candidate (written at the next prompt)\n"
FIN = '      print -r -- "FIN buf=<$BUFFER> q=${KEYS_QUEUED_COUNT:-0}" >> ' + TRACE + "\n"
TABLOG = '            print -r -- "SWALLOW-TAB cleanup" >> ' + TRACE + "\n"
BACKLOG = '            print -r -- "PUSHBACK non-tab" >> ' + TRACE + "\n"

src = src.replace(HOOK, HOOK + FIN, 1)
src = src.replace(
    "          if [[ $_spacue_qk == $'\\t' ]]; then\n            _spacue_cleanup_state\n",
    "          if [[ $_spacue_qk == $'\\t' ]]; then\n" + TABLOG +
    "            _spacue_cleanup_state\n", 1)
src = src.replace(
    "          else\n            zle -U \"$_spacue_qk\"\n",
    "          else\n" + BACKLOG + "            zle -U \"$_spacue_qk\"\n", 1)
DBG = "/tmp/dbg-peek3.zsh"
open(DBG, "w").write(src)

open(TRACE, "w").close()
t = Term(["zsh", "-f", "-i"], cols=110, rows=40, cwd=BASE)
t.wait_idle(0.6, 6)
t.send("PS1='PS> '\n")
t.wait_for("PS>", 5)
t.send("autoload -Uz compinit; compinit -u -C -d /tmp/spzdump-peek3\n")
t.wait_idle(1.0)
t.send(f"source {DBG}\n")
t.wait_idle(0.6)
t.send("clear\n")
t.wait_idle(0.3)

def pr():
    return [l.strip() for l in t.screen.text().splitlines() if "PS>" in l][-1]

# S1: cd menu -> Tab accept
t.send("cd ")
t.wait_idle(1.4)
t.send_keys("Tab")
t.wait_idle(0.9)
s1 = pr()
print("S1 post-Tab  :", s1, "(want 'PS> cd ../')")

# S2: fresh menu + burst typing
t.send("\x15")                 # kill S1 leftover line
t.wait_idle(0.3)
t.send("cd ")
t.wait_idle(1.4)
t.send("bet")
t.wait_idle(1.8)
s2 = pr()
print("S2 burst     :", s2, "(want 'PS> cd beta/')")
t.send("\n")   # run it -> state dead via accept-line survivor
t.wait_for("PS>", 5)

# S3: git checkout Tab-accept in repo
t.send("\x15")                 # kill leftover line
t.wait_idle(0.3)
t.send("builtin cd " + REPO + "\n")
t.wait_idle(0.5)
t.send("clear\n")
t.wait_idle(0.3)
t.send("git checkout ")
t.wait_idle(1.5)
t.send_keys("Tab")
t.wait_idle(1.0)
s3 = pr()
print("S3 post-Tab  :", s3, "(want 'PS> git checkout main')")

print("== trace ==")
for l in open(TRACE).read().splitlines():
    print(" ", l)
t.close()
