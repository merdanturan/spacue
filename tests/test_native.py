"""Native compdef fallback through real ZLE, with no external CLI dependencies."""
import json
import os
from pathlib import Path
import shlex
import tempfile
import time
import unittest

from pterm import Term

PLUGIN = Path(__file__).resolve().parents[1] / "spacue.zsh"


class NativeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="spacue-native-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        for name in ("fallback.txt", "other.txt"):
            (self.base / name).touch()
        (self.base / "package.json").write_text(json.dumps({"scripts": {"dev": "vite", "test": "vitest"}}))
        self.t = Term(["zsh", "-f", "-i"], cols=120, rows=30, cwd=str(self.base),
                      env={"ZDOTDIR": str(self.base), "SPACUE_NATIVE": "1",
                           "SPACUE_STATS_FILE": str(self.base / "stats.tsv")})
        self.addCleanup(self.t.close)
        self.t.wait_idle(0.1)
        self.t.send("PS1='PS> '; bindkey -e; source " + shlex.quote(str(PLUGIN)) + "\n")
        self.t.send(r'''
_native_acme() {
  print invoked >> native-calls
  case $words[2] in
    (single) compadd -S '' -- 'space name; literal' ;;
    (none) return 1 ;;
    (fail) return 42 ;;
    (flags) compadd -- --alpha --beta ;;
    (paths) compadd -S / -- child nested ;;
    (*) compadd -- alpha beta gamma ;;
  esac
}
compdef _native_acme acme
acme() { print -r -- "$#:${(j:,:)@}" > argv; }
print -r -- STARTED$((40+2))
''')
        self.assertTrue(self.t.wait_for("STARTED42", 20), self.t.screen.text())
        self.send("clear\n")

    def send(self, text):
        self.t.send(text)
        self.t.wait_idle(0.2)

    def key(self, name):
        self.t.send_keys(name)
        self.t.wait_idle(0.2)

    def row(self):
        rows = [r.strip() for r in self.t.screen.text().splitlines() if "PS>" in r]
        return rows[-1] if rows else ""

    def expect_row(self, value):
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            self.t.pump(0.05)
            if self.row() == value:
                return
        self.assertEqual(self.row(), value, self.t.screen.text())

    def argv(self):
        target = self.base / "argv"
        deadline = time.monotonic() + 8
        while not target.exists() and time.monotonic() < deadline:
            self.t.pump(0.05)
        return target.read_text().strip()

    def test_arrows_enter_accept_then_execute(self):
        self.send("acme ")
        self.expect_row("PS> acme")
        self.key("Down")
        self.expect_row("PS> acme alpha")
        self.key("Down")
        self.expect_row("PS> acme beta")
        self.key("Enter")
        self.expect_row("PS> acme beta")
        self.assertFalse((self.base / "argv").exists())
        self.key("Enter")
        self.assertEqual(self.argv(), "1:beta")
        self.assertFalse((self.base / "stats.tsv").exists(), "native ordering is not usage-ranked")

    def test_single_native_match_keeps_quoting_and_requires_acceptance(self):
        self.send("acme single ")
        self.expect_row("PS> acme single")
        self.key("Tab")
        self.assertFalse((self.base / "argv").exists())
        self.key("Enter")
        self.assertEqual(self.argv(), "2:single,space name; literal")

    def test_native_flags_are_offered(self):
        self.send("acme flags ")
        self.send("--")
        self.expect_row("PS> acme flags --")
        self.key("Tab")
        self.key("Enter")
        self.assertEqual(self.argv(), "2:flags,--alpha")

    def test_native_suffix_is_kept(self):
        self.send("acme paths ")
        self.expect_row("PS> acme paths")
        self.key("Tab")
        self.key("Enter")
        self.assertEqual(self.argv(), "2:paths,child/")

    def test_zero_matches_fall_back_to_files(self):
        self.send("acme none ")
        self.expect_row("PS> acme none")
        self.key("Tab")
        self.key("Enter")
        self.assertEqual(self.argv(), "2:none,fallback.txt")

    def test_failed_native_completion_falls_back_cleanly(self):
        self.send("acme fail ")
        self.expect_row("PS> acme fail")
        self.key("Esc")
        self.expect_row("PS> acme fail")

    def test_typing_and_backspace_use_native_context(self):
        self.send("acme ")
        self.send("be")
        self.expect_row("PS> acme be")
        self.key("BS")
        self.expect_row("PS> acme b")
        self.key("Esc")
        self.expect_row("PS> acme b")

    def test_opt_out_keeps_existing_file_suggestions(self):
        self.send("SPACUE_NATIVE=0\n")
        self.send("acme ")
        self.expect_row("PS> acme")
        self.key("Tab")
        self.expect_row("PS> acme fallback.txt")
        self.assertFalse((self.base / "native-calls").exists())

    def test_registered_provider_keeps_precedence(self):
        self.send("_custom() { spacue_add own-a; spacue_add own-b; }; spacue_register acme _custom\n")
        self.send("acme ")
        self.expect_row("PS> acme")
        self.key("Tab")
        self.expect_row("PS> acme own-a")
        self.assertFalse((self.base / "native-calls").exists())

    def test_builtin_provider_keeps_precedence(self):
        self.send("compdef _native_acme npm\n")
        self.send("npm ")
        self.key("Tab")
        self.expect_row("PS> npm run dev")
        self.assertFalse((self.base / "native-calls").exists())

    def test_no_matches_without_generic_fallback_restores_typed_line(self):
        self.send("SPACUE_GENERIC=0\n")
        self.send("acme none ")
        self.expect_row("PS> acme none")
        self.key("Enter")
        self.assertEqual(self.argv(), "1:none")

    def test_autoloaded_completion_is_resolved(self):
        (self.base / "_lazy_spec").write_text("#autoload\ncompadd -- lazy-a lazy-b\n")
        self.send('fpath=("$PWD" $fpath); autoload -Uz _lazy_spec; compdef _lazy_spec lazytool\n')
        self.send("lazytool ")
        self.expect_row("PS> lazytool")
        self.key("Tab")
        self.expect_row("PS> lazytool lazy-a")

    def test_vi_mode_native_menu_accepts_without_executing(self):
        self.send("bindkey -v\n")
        self.send("acme ")
        self.expect_row("PS> acme")
        self.key("Down")
        self.key("Down")
        self.key("Tab")
        self.expect_row("PS> acme beta")
        self.assertFalse((self.base / "argv").exists())
        self.key("Enter")
        self.assertEqual(self.argv(), "1:beta")


if __name__ == "__main__":
    unittest.main()
