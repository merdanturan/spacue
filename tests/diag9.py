import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from pterm import Term

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "spacue.zsh"))

VARIANTS = {
  "VB-realcollect-fixed-items": (
    "_spacue_complete() { _spacue_collect_from_buffer; compadd alpha beta gamma }"
  ),
  "VC-nocollect-realitems": (
    "_spacue_complete() { local -a items=('../' 'alpha/' 'beta/' 'Documents/' 'gamma/') descs=('' '' '' '' ''); compadd -U -V spacue -d descs -a items }"
  ),
  "VA-realcollect-realitems-copy": (
    "_spacue_complete() { _spacue_collect_from_buffer; local -a items=(\"${_spacue_items_list[@]}\") descs=(\"${_spacue_descs_list[@]}\"); compadd -U -V spacue -d descs -a items }"
  ),
}

t = Term(["zsh", "-f", "-i"], cols=100, rows=30)
t.wait_idle(0.5, 5)
t.send("PS1='PS> '\n")
t.wait_for("PS>", 5)
t.send(f"source {PLUGIN}\n")
t.wait_idle(0.5)
t.send("cd /tmp/spacue-demo\n")
t.wait_idle(0.4)

for name, body in VARIANTS.items():
    t.send(body + "\n")
    t.wait_idle(0.3)
    t.send("cd ")
    t.wait_idle(0.9)
    scr = t.screen.text()
    lines = scr.splitlines()[-5:]
    print(f"--- {name}")
    for line in lines: print("   |", line)
    t.send_keys("Down")
    t.wait_idle(0.4)
    t.send_keys("Enter")
    t.wait_idle(0.5)
    after = t.screen.text().splitlines()[-2:]
    print("   after Down+Enter:")
    for line in after: print("   >", line)
    t.send_keys("C-u", "C-g")
    t.wait_idle(0.3)
t.close()
