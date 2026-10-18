"""Probe: can a zle widget peek the byte queue during `read -t 0 -k`?
Scenes:
  S1 menu -> Tab-accept: is the single queued byte the TAB (0x09)? pop only it.
  S2 menu + burst typing (cd bet): peek bytes must be the typed keys, and
     pushing them back must not disturb the flow.
"""
import os, shutil, sys
sys.path.insert(0, os.path.dirname(__file__))
from pterm import Term

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "spacue.zsh"))
BASE = "/tmp/spacue-peek"
TRACE = "/tmp/trace-peek"

shutil.rmtree(BASE, ignore_errors=True)
for d in ("alpha", "beta", "gamma"):
    os.makedirs(BASE + "/" + d, exist_ok=True)

PROBE = r'''
zmodload zsh/complist 2>/dev/null
_typeset_g() {
  for w in "$@"; do typeset -g $w 2>/dev/null; done
}
# patch: wrap the real _spacue_cleanup_state's finalize check by overriding
# KEYS_QUEUED_COUNT handling with the peek. Simplest: hook via the plugin:
# we prepend a source with our own _spacue_fire override AFTER the plugin.
_pk() {
  # pop up to 1 pending byte and report it
  local c=""
  if read -t 0 -k c 2>/dev/null; then
    print -r -- "PEEK byte=$(printf %02x "'$c")" >> TRACEPATH
    zle -U "$c"
  else
    print -r -- "PEEK none" >> TRACEPATH
  fi
}
zle -N _pk
clean() { unfunction _pk 2>/dev/null; }
'''
PROBE = PROBE.replace("TRACEPATH", TRACE)

open("/tmp/sp-peek-early.zsh", "w").write(PROBE)

# plugin override of the finalize branch: patch the plugin copy
with open(PLUGIN) as f:
    src = f.read()
OLD = '''      if [[ ${KEYS_QUEUED_COUNT:-0} -eq 0 ]]; then
        _spacue_cleanup_state
      fi
'''
NEW = '''      print -r -- "FIN buf=<$BUFFER> q=${KEYS_QUEUED_COUNT:-0}" >> /tmp/trace-peek
      local _pkc=""
      if (( ${KEYS_QUEUED_COUNT:-0} == 1 )) && read -t 0 -k _pkc 2>/dev/null; then
        print -r -- "PK byte=$(printf %02x "'$_pkc")" >> /tmp/trace-peek
        if [[ $_pkc == $'\\t' ]]; then
          _spacue_cleanup_state      # Tab-accept: swallow the Tab, clean state
        else
          _spacue_cleanup_state      # typed single byte (space-trigger flow's own space)
          zle -U "$_pkc"
        fi
      elif [[ ${KEYS_QUEUED_COUNT:-0} -eq 0 ]]; then
        _spacue_cleanup_state
      fi
'''
assert OLD in src
src = src.replace(OLD, NEW, 1)
DBG = "/tmp/dbg-peek.zsh"
open(DBG, "w").write(src)

open(TRACE, "w").close()

t = Term(["zsh", "-f", "-i"], cols=110, rows=40, cwd=BASE,
         env={"SPACUE_STATS_FILE": "/dev/null"})
t.wait_idle(0.6, 6)
t.send("PS1='PS> '\n")
t.wait_for("PS>", 5)
t.send("autoload -Uz compinit; compinit -u -C -d /tmp/spzdump-peek\n")
t.wait_idle(1.0)
t.send(f"source {DBG}\n")
t.wait_idle(0.6)
t.send("clear\n")
t.wait_idle(0.3)

# Scene 1: menu -> Tab accept
t.send("cd ")
t.wait_idle(1.3)
t.send_keys("Tab")
t.wait_idle(0.8)
r1 = [l.strip() for l in t.screen.text().splitlines() if "PS>" in l][-1]
t.send("\n")      # run it -> precmd
t.wait_for("PS>", 5)

# Scene 2: menu + burst typing
t.send("cd ")
t.wait_idle(1.3)
t.send("bet")
t.wait_idle(1.5)
r2 = [l.strip() for l in t.screen.text().splitlines() if "PS>" in l][-1]
t.send("\x0c")
t.wait_idle(0.4)
t.send("\n")   # run cd beta/
t.wait_for("PS>", 5)
r2b = [l.strip() for l in t.screen.text().splitlines()][-3:]

print("S1 post-Tab line :", r1)
print("S2 burst line    :", r2)
print("S2 after refresh :", r2b)
print("== trace ==")
for l in open(TRACE).read().splitlines():
    print(" ", l)
t.close()
