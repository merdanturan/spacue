import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from pterm import Term

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "spacue.zsh"))
LOG = "/tmp/spacue-debug.log"
try: os.unlink(LOG)
except OSError: pass

t = Term(["zsh", "-f", "-i"], cols=100, rows=30)
t.wait_idle(0.5, 5)
t.send("PS1='PS> '\n")
t.wait_for("PS>", 5)
t.send(f"source {PLUGIN}\n")
t.wait_idle(0.5)
t.send("cd /tmp/spacue-demo\n")
t.wait_idle(0.4)

setup = f'''
functions[spacue_orig_comp]=$functions[_spacue_complete]
_spacue_complete() {{
  print -r -- "COMPLETE enter CURRENT=$CURRENT word=[${{words[$CURRENT]}}]" >> {LOG}
  spacue_orig_comp "$@"
  local rc=$?
  print -r -- "COMPLETE done rc=$rc n=${{#_spacue_items_list}}" >> {LOG}
  return $rc
}}
_spacue_show_menu() {{
  _spacue_on=1
  _spacue_style_on
  print -r -- "menu style=[$(zstyle -s ':completion:*' menu REPLY; print -r -- $REPLY)]" >> {LOG}
  {{ zle spacue-complete; print -r -- "call1 rc=$? on=$_spacue_on" >> {LOG} }} 2>>{LOG}
  {{ zle spacue-complete; print -r -- "call2 rc=$? on=$_spacue_on" >> {LOG} }} 2>>{LOG}
}}
'''
t.send(setup)
t.wait_idle(0.5)

t.send("cd ")
t.wait_idle(0.8)
print("=== screen ===")
print(t.screen.text())
t.close()

print("=== log ===")
try: print(open(LOG).read())
except OSError as e: print("no log", e)
