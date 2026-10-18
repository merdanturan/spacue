"""diag16-S1-mini with behavior-neutral logs on note / precmd-flush / write."""
import os, shutil, sys, time
sys.path.insert(0, os.path.dirname(__file__))
from pterm import Term

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "spacue.zsh"))
BASE = "/tmp/spacue-s1dbg"
STATS = BASE + "/stats.tsv"
TRACE = "/tmp/trace-s1dbg"

shutil.rmtree(BASE, ignore_errors=True)
os.makedirs(BASE, exist_ok=True)
with open(BASE + "/package.json", "w") as f:
    f.write('{"name":"demo","scripts":{"dev":"vite --port 3000","rebuild":"./rebuild.sh","meta-build":"./meta.sh","test":"vitest"}}\n')
with open(PLUGIN) as f:
    src = f.read()

NOTE_ANCH = "  _spacue_stats_pending+="
NOTED = '  print -r -- NOTED ins=$ins cmd=$_spacue_stats_cmd >> ' + TRACE + "\n"
src = src.replace(NOTE_ANCH, NOTED + NOTE_ANCH, 1)

FLUSH_ANCH = "    _spacue_stats_write \""
FLUSHED = '    print -r -- FLUSH pend=$_spacue_stats_pending >> ' + TRACE + "\n"
src = src.replace(FLUSH_ANCH, FLUSHED + FLUSH_ANCH, 1)

DBG = "/tmp/dbg-s1.zsh"
open(DBG, "w").write(src)

open(TRACE, "w").close()
t = Term(["zsh", "-f", "-i"], cols=110, rows=40, cwd=BASE,
         env={"SPACUE_STATS_FILE": STATS})
t.wait_idle(0.6, 6)
t.send("PS1='PS> '\n")
t.wait_for("PS>", 5)
t.send("autoload -Uz compinit; compinit -u -C -d /tmp/spzdump-s1\n")
t.wait_idle(1.0)
t.send(f"source {DBG}\n")
t.wait_idle(0.6)
t.send("clear\n")
t.wait_idle(0.3)

open(STATS, "w").write('npm:test\t3\t' + BASE + '\nnpm:run test\t3\t\nnpm:dev\t1\t\n')
t.send("\n")  # refresh sig (mtime keyed)
t.wait_idle(0.4)

t.send("npm run ")
t.wait_idle(1.3)
for l in t.screen.text().splitlines():
    if l.strip():
        print("ROW:", l)
t.send_keys("Tab")
t.wait_idle(0.9)
print("post-Tab:", [l.strip() for l in t.screen.text().splitlines() if "PS>" in l][-1])
t.send("\n")
t.wait_for("PS>", 8)
time.sleep(0.4)
print("file:", open(STATS).read().replace("\n", " | "))
print("== trace ==")
for l in open(TRACE).read().splitlines():
    print(" ", l)
t.close()
