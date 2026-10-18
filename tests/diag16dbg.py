"""Try-to-catch the pushed-back byte: bind main Tab to a logger; after
Tab-accept, see whether the logger fires with a Tab and when."""
import os, shutil, sys
sys.path.insert(0, os.path.dirname(__file__))
from pterm import Term

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "spacue.zsh"))
BASE = "/tmp/spacue-tstats"
STATS = BASE + "/stats.tsv"
TRACE = "/tmp/trace16"

shutil.rmtree(BASE, ignore_errors=True)
os.makedirs(BASE, exist_ok=True)
with open(BASE + "/package.json", "w") as f:
    f.write('{"name":"demo","scripts":{"dev":"vite --port 3000","rebuild":"./rebuild.sh","meta-build":"./meta.sh","test":"vitest"}}\n')
with open(STATS, "w") as f:
    f.write(f'npm:test\t3\t{BASE}\n')

open(TRACE, "w").close()
setup = rf'''
source {PLUGIN}
export SPACUE_STATS_FILE={STATS}
autoload -Uz compinit && compinit -u -C -d /tmp/spacue-zcompdbg2
_spacue_tab_log() {{ print -r -- "MAINTAB keys=on=${{_spacue_on:-off}}" >> {TRACE}; zle _spacue_cw; }}
zle -N _spacue_tab_log
bindkey -M emacs '\t' _spacue_tab_log
'''
with open("/tmp/sp16setup.zsh", "w") as f:
    f.write(setup)

t = Term(["zsh", "-f", "-i"], cols=110, rows=40, cwd=BASE, env={"SPACUE_STATS_FILE": STATS})
t.wait_idle(0.6, 6)
t.send("PS1='PS> '\n")
t.wait_for("PS>", 5)
t.send("source /tmp/sp16setup.zsh\n")
t.wait_idle(0.6)
t.send("clear\n")
t.wait_idle(0.3)
t.send("npm run ")
t.wait_idle(1.3)
t.send_keys("Tab")
t.wait_idle(0.9)
print("post-Tab:", [l.strip() for l in t.screen.text().splitlines() if "PS>" in l or "npm" in l][-2:])
t.send("y")        # a follow-up keystroke -- does the queued byte precede it?
t.wait_idle(0.7)
print("post-y:", [l.strip() for l in t.screen.text().splitlines() if "PS>" in l or "npm" in l][-2:])
print("== trace ==")
for l in open(TRACE).read().splitlines():
    print(" ", l)
t.close()
