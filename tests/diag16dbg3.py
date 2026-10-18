"""Trace the git-checkout Tab-accept flow: why does a stale completion run
insert tracked.txt after the accepted branch?  Instruments a /tmp copy of
the plugin and replays the S3 sequence with a full event log."""
import os, shutil, subprocess, sys
sys.path.insert(0, os.path.dirname(__file__))
from pterm import Term

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "spacue.zsh"))
BASE = "/tmp/spacue-tstats"
REPO = BASE + "/repo"
STATS = BASE + "/stats.tsv"
TRACE = "/tmp/trace16s3"
DBG = "/tmp/dbg16-s3.zsh"

shutil.rmtree(BASE, ignore_errors=True)
for d in ("alpha", "beta", "gamma", "repo"):
    os.makedirs(os.path.join(BASE, d), exist_ok=True)
with open(BASE + "/package.json", "w") as f:
    f.write('{"name":"demo","scripts":{"dev":"vite --port 3000","rebuild":"./rebuild.sh","meta-build":"./meta.sh","test":"vitest"}}\n')
subprocess.run(["git", "init", "-q", "-b", "main"], cwd=REPO, check=True)
subprocess.run(["git", "-C", REPO, "config", "user.email", "t@e.dev"], check=True)
subprocess.run(["git", "-C", REPO, "config", "user.name", "T"], check=True)
open(REPO + "/tracked.txt", "w").write("one\n")
subprocess.run(["git", "-C", REPO, "add", "."], check=True)
subprocess.run(["git", "-C", REPO, "commit", "-qm", "init"], check=True)
subprocess.run(["git", "-C", REPO, "branch", "feature-x"], check=True)

with open(PLUGIN) as f:
    src = f.read()

ANCH_COLL = "_spacue_collect_from_buffer() {\n  emulate -L zsh\n"
src = src.replace(ANCH_COLL, ANCH_COLL.replace(
    "emulate -L zsh\n",
    "emulate -L zsh\n  print -r -- \"COLL left=<${LBUFFER:-}> buf=<${BUFFER:-}>\" >> " + TRACE + "\n", 1))

ANCH_CMP = "_spacue_completer() {  # runs inside the completion system while pending\n"
src = src.replace(ANCH_CMP, ANCH_CMP +
    '  print -r -- "CMP buf=<${BUFFER:-}> tok=<${_spacue_token:-}> on=<${_spacue_on:-}> '
    'pend=<${_spacue_pending:-}> items=<${(j:,:)_spacue_items_list:-}>" >> ' + TRACE + "\n", 1)

ANCH_FIRE = "_spacue_fire() {  # one completion attempt per invocation\n  local before=$BUFFER\n"
src = src.replace(ANCH_FIRE, ANCH_FIRE.replace(
    "  local before=$BUFFER\n",
    "  local before=$BUFFER\n  print -r -- \"FIRE#n=$((_spacue_fires + 1)) buf=<$BUFFER>\" >> " + TRACE + "\n", 1))

ANCH_AL = "_spacue_accept_line() {\n"
src = src.replace(ANCH_AL, ANCH_AL +
    '  print -r -- "ALINE buf=<${BUFFER:-}> on=<${_spacue_on:-}>\" >> ' + TRACE + "\n", 1)

src = src.replace(
    '    _spacue_pending=""\n    if [[ $BUFFER != $before ]]; then\n',
    '    _spacue_pending=""\n'
    '    print -r -- "FIRE-FIN buf=<$BUFFER> before=<$before> q=${KEYS_QUEUED_COUNT:-0}" >> ' + TRACE + '\n'
    '    if [[ $BUFFER != $before ]]; then\n', 1)

with open(DBG, "w") as f:
    f.write(src)

open(TRACE, "w").close()
t = Term(["zsh", "-f", "-i"], cols=110, rows=40, cwd=REPO,
         env={"SPACUE_STATS_FILE": STATS})
t.wait_idle(0.6, 6)
t.send("PS1='PS> '\n")
t.wait_for("PS>", 5)
t.send("autoload -Uz compinit; compinit -u -C -d /tmp/spacue-zcompdbg3\n")
t.wait_idle(1.0)
t.send(f"source {DBG}\n")
t.wait_idle(0.6)
t.send("clear\n")
t.wait_idle(0.3)
t.send("git checkout ")
t.wait_idle(1.5)
print("menu:", [l.strip() for l in t.screen.text().splitlines()][-3:])
t.send_keys("Tab")
t.wait_idle(0.9)
print("post-Tab:", [l.strip() for l in t.screen.text().splitlines() if "PS>" in l or "read\\|main" in l][-2:])
t.send("\n")     # run it
t.wait_for("PS>", 5)
print("post-Enter:", [l.strip() for l in t.screen.text().splitlines() if "PS>" in l][-1:])
print("== trace ==")
for l in open(TRACE).read().splitlines():
    print(" ", l)
t.close()
