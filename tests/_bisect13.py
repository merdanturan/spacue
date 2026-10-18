"""Bisect diag12-S13's regression: which edit broke the Down+Enter flow when
the user has set `zstyle ':completion:*' menu select` themselves?

Copies of baseline plugin with isolated pieces:
  A: stats rank/note hooks in dispatch only
  B: shields menuselect-Tab bind/restore only
  C: v2 finalize (note + peek-swallow) only
Runs the mini S13 scene against baseline, A, B, C.
"""
import os, subprocess, sys
sys.path.insert(0, os.path.dirname(__file__))
from pterm import Term

BASELINE = subprocess.run(["git", "-C", os.path.join(os.path.dirname(__file__), ".."),
                           "show", "HEAD:spacue.zsh"], capture_output=True, text=True).stdout
BASE = "/tmp/spacue-bisect"
os.makedirs(BASE + "/alpha/deep1", exist_ok=True)
os.makedirs(BASE + "/beta", exist_ok=True)
os.makedirs(BASE + "/gamma", exist_ok=True)

with open("/tmp/bisect-base.zsh", "w") as f:
    f.write(BASELINE)

# piece A: stats hooks in dispatch (rank + cmd) -- needs the stats block loaded
A = BASELINE.replace("  local rc=1\n  _spacue_dispatch \"$cmd\" \"$token\" \"${sargs[@]}\"; rc=$?\n",
                     "  local rc=1\n", 1)  # no-op safety: keep original
# simpler: rank depends on typesets; emulate by calling a trivial shell instead
A = BASELINE
A = A.replace("SPACUE_KIND=\"\"\n  _spacue_stats_cmd=$cmd\n", "")  # only if present

def patch_text(src, old, new, tag):
    assert old in src, "anchor missing for " + tag
    return src.replace(old, new, 1)

# Piece C (v2 finalize) from current work:
C_OLD = """    if [[ $BUFFER != $before && ${KEYS_QUEUED_COUNT:-0} -eq 0 ]]; then
      _spacue_cleanup_state
    fi
"""
C_NEW = """    if [[ $BUFFER != $before ]]; then
      if (( ${KEYS_QUEUED_COUNT:-0} == 1 )); then
        local _spacue_qk=""
        if read -t 0 -k _spacue_qk 2>/dev/null; then
          if [[ $_spacue_qk == $'\\t' ]]; then
            _spacue_cleanup_state
          else
            zle -U "$_spacue_qk"
          fi
        fi
      fi
      if [[ ${KEYS_QUEUED_COUNT:-0} -eq 0 ]]; then
        _spacue_cleanup_state
      fi
    fi
"""

# Piece B (shields menuselect Tab bind/restore) -- lifted from v3
with open("/tmp/spacue-v3.zsh") as f:
    v3 = f.read()
B_ON_OLD = "  _spacue_shields_on"
B_ON_NEW = """  local prevtab=$(bindkey -M menuselect '\\t' 2>/dev/null)
  _spacue_prev_tab="${prevtab##* }"
  bindkey -M menuselect '\\t' accept 2>/dev/null
  _spacue_shields_on"""
B_OFF_OLD = "  _spacue_shields_off"
B_OFF_NEW = """  if [[ -n ${_spacue_prev_tab-} ]]; then
    if [[ -n $_spacue_prev_tab ]]; then
      bindkey -M menuselect '\\t' "$_spacue_prev_tab" 2>/dev/null
    else
      bindkey -M menuselect -r '\\t' 2>/dev/null
    fi
    _spacue_prev_tab=""
  fi
  _spacue_shields_off"""

B = patch_text(BASELINE, B_ON_OLD, B_ON_NEW, "B-on")
B = patch_text(B, B_OFF_OLD, B_OFF_NEW, "B-off")
C = patch_text(BASELINE, C_OLD, C_NEW, "C")

need_typeset = "typeset -g _spacue_shields_up _spacue_esc_taken _spacue_beep_saved _spacue_prev_tab"
B = B.replace("typeset -g _spacue_shields_up _spacue_esc_taken _spacue_beep_saved",
              need_typeset, 1)

variants = {"base": BASELINE, "A": A, "B": B, "C": C}
for name, text in variants.items():
    with open(f"/tmp/bisect-{name}.zsh", "w") as f:
        f.write(text)

STATS = "/tmp/spacue-bisect/stats.tsv"


def run(name):
    os.makedirs(os.path.dirname(STATS), exist_ok=True)
    open(STATS, "w").close()
    t = Term(["zsh", "-f", "-i"], cols=110, rows=34, cwd=BASE,
             env={"SPACUE_STATS_FILE": STATS})
    t.wait_idle(0.6, 6)
    t.send("PS1='PS> '\n")
    t.wait_for("PS>", 5)
    t.send("autoload -Uz compinit; compinit -u -C -d /tmp/spzdump-bisect\n")
    t.wait_idle(1.0)
    t.send("source /tmp/bisect-%s.zsh\n" % name)
    t.wait_idle(0.6)
    t.send("zstyle ':completion:*' menu select\n")
    t.wait_idle(0.3)
    t.send("cd ")
    t.wait_idle(1.2)
    t.send_keys("Down")
    t.wait_idle(0.4)
    t.send_keys("Enter")
    t.wait_idle(0.9)
    line = [l.strip() for l in t.screen.text().splitlines() if "PS>" in l][-1]
    t.close()
    return line


for name in ("base", "A", "B", "C"):
    line = run(name)
    ok = (line == "PS> cd alpha/")
    print(f"{name:>4}: {'OK ' if ok else 'FAIL'}  {line}")
