"""PTY regressions for acceptance, quoting and ranking provenance."""
import json
import os
from pathlib import Path
import shlex
import tempfile
import unittest

from pterm import Term

PLUGIN = Path(__file__).resolve().parents[1] / "spacue.zsh"


class MenuTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="spacue-ui-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        for name in ("alpha", "beta", "space dir"):
            (self.base / name).mkdir()
        (self.base / "package.json").write_text(json.dumps({"scripts": {
            "dev": "vite", "test all; unsafe": "echo test", "test other": "echo other"}}))
        self.stats = self.base / "stats.tsv"
        self.t = Term(["zsh", "-f", "-i"], cols=120, rows=30, cwd=str(self.base),
                      env={"ZDOTDIR": str(self.base), "SPACUE_STATS_FILE": str(self.stats)})
        self.addCleanup(self.t.close)
        self.t.wait_idle(0.1)
        self.t.send("PS1='PS> '; bindkey -e; source " + shlex.quote(str(PLUGIN)) +
                    "; print -r -- STARTED$((1+1))\n")
        self.assertTrue(self.t.wait_for("STARTED2", 15), self.t.screen.text())
        # Local function records argv without launching a package manager.
        self.t.send("npm() { print -r -- \"$#:${(j:,:)@}\" > argv; }; clear\n")
        self.t.wait_idle(0.1)

    def send(self, text):
        self.t.send(text)
        self.t.wait_idle(0.15)

    def key(self, name):
        self.t.send_keys(name)
        self.t.wait_idle(0.6 if name == "Esc" else 0.15)

    def row(self):
        return [r.strip() for r in self.t.screen.text().splitlines() if "PS>" in r][-1]

    def test_open_keeps_input_until_first_down_selects_first_item(self):
        self.send("npm ")
        self.assertEqual(self.row(), "PS> npm")
        self.assertIn("run dev", self.t.screen.text())
        self.assertFalse(self.stats.exists())
        self.key("Down")
        self.assertEqual(self.row(), r"PS> npm run\ dev")
        self.key("Tab")
        self.assertFalse((self.base / "argv").exists())
        self.key("Enter")
        self.assertEqual((self.base / "argv").read_text().strip(), "2:run,dev")

    def test_filter_keeps_typed_input_until_selection(self):
        self.send("npm ")
        self.send("dev")
        self.assertEqual(self.row(), "PS> npm dev")
        self.key("Down")
        self.assertEqual(self.row(), r"PS> npm run\ dev")
        self.key("Esc")
        self.assertEqual(self.row(), "PS> npm dev")
        self.assertFalse(self.stats.exists())

    def test_single_candidate_is_not_inserted_on_space(self):
        self.send("_one() { spacue_add only; }; spacue_register one _one\n")
        self.send("one ")
        self.assertEqual(self.row(), "PS> one")
        self.assertIn("only", self.t.screen.text())
        self.key("Tab")
        self.assertEqual(self.row(), "PS> one only")

    def test_large_list_does_not_consume_typing_as_listing_confirmation(self):
        self.send("LISTMAX=2\n")
        self.send("npm ")
        self.send("dev")
        self.assertEqual(self.row(), "PS> npm dev")
        self.key("Tab")
        self.assertEqual(self.row(), "PS> npm run dev")

    def test_list_taller_than_terminal_keeps_prompt_and_typing_visible(self):
        self.send('_many() { local i; for i in {1..200}; do spacue_add "command$i" "a long description that fills the terminal width"; done; }; spacue_register many _many\n')
        self.send("clear\n")
        self.send("many ")
        self.assertEqual(self.row(), "PS> many")
        self.assertIn("200 suggestions", self.t.screen.text())
        self.key("Down")
        self.assertEqual(self.row(), "PS> many command1")
        self.key("Esc")
        self.send("command199")
        self.assertEqual(self.row(), "PS> many command199")

    def test_common_prefix_and_backspace_preserve_typed_input(self):
        self.send("npm run ")
        self.send("te")
        self.assertEqual(self.row(), "PS> npm run te")
        self.key("Down")
        self.assertIn(r"PS> npm run test\ all\;\ unsafe", self.row())
        self.key("BS")
        self.assertEqual(self.row(), "PS> npm run t")
        self.key("C-g")
        self.assertEqual(self.row(), "PS> npm run t")
        self.assertFalse(self.stats.exists())

    def test_clearing_unselected_input_does_not_restore_old_command(self):
        self.send("npm ")
        self.key("C-u")
        self.send("literal")
        self.assertEqual(self.row(), "PS> literal")

    def test_cursor_editing_unselected_input_does_not_restore_old_command(self):
        self.send("npm ")
        self.key("Left")
        self.send("x")
        self.assertEqual(self.row(), "PS> npmx")

    def test_first_up_selects_last_item_and_restores_arrow_bindings(self):
        self.send("bindkey '^[[B' beginning-of-line; bindkey '^[[A' end-of-line\n")
        self.send("_two() { spacue_add first; spacue_add last; }; spacue_register two _two\n")
        self.send("two ")
        self.assertEqual(self.row(), "PS> two")
        self.key("Up")
        self.assertEqual(self.row(), "PS> two last")
        self.key("Esc")
        self.assertEqual(self.row(), "PS> two")
        self.key("C-c")
        self.send("bindkey '^[[B'; bindkey '^[[A'\n")
        self.assertIn('"^[[B" beginning-of-line', self.t.screen.text())
        self.assertIn('"^[[A" end-of-line', self.t.screen.text())

    def test_filtered_single_enter_accepts_then_runs(self):
        self.send("npm ")
        self.send("dev")
        self.assertEqual(self.row(), "PS> npm dev")
        self.key("Enter")
        self.assertFalse((self.base / "argv").exists(), "first Enter ran the command")
        self.key("Enter")
        self.assertEqual((self.base / "argv").read_text().strip(), "2:run,dev")

    def test_filtered_single_tab_accepts_then_runs(self):
        self.send("npm ")
        self.send("dev")
        self.key("Tab")
        self.assertEqual(self.row(), "PS> npm run dev")
        self.assertFalse((self.base / "argv").exists())
        self.key("Enter")
        self.assertEqual((self.base / "argv").read_text().strip(), "2:run,dev")

    def test_script_spaces_and_metacharacters_stay_in_one_argument(self):
        self.send("npm ")
        self.send("test")
        self.key("Tab")
        self.key("Enter")
        self.assertEqual((self.base / "argv").read_text().strip(), "2:run,test all; unsafe")

    def test_single_script_in_run_context_is_one_argument(self):
        (self.base / "package.json").write_text(json.dumps({"scripts": {"test all; unsafe": "echo test"}}))
        self.send("npm run ")
        self.send("test")
        self.assertEqual(self.row(), "PS> npm run test")
        self.key("Tab")
        self.key("Enter")
        self.assertEqual((self.base / "argv").read_text().strip(), "2:run,test all; unsafe")

    def test_nested_escaped_paths_are_completed_as_one_argument(self):
        for name, typed in (("space dir", r"space\ dir/ch"), ("it's here", r"it\'s\ here/ch")):
            with self.subTest(name=name):
                target = self.base / name / "child"
                target.mkdir(parents=True)
                self.send("builtin cd " + shlex.quote(str(self.base)) + "\n")
                self.send("cd " + typed)
                self.assertEqual(self.row(), "PS> cd " + typed)
                self.key("Tab")
                self.key("Enter")
                self.send("pwd > location\n")
                self.assertEqual((target / "location").read_text().strip(), str(target))

    def test_dismissed_preview_does_not_affect_ranking(self):
        self.send("npm ")
        self.send("test")
        self.key("Esc")
        self.key("C-c")
        self.assertFalse(self.stats.exists(), self.stats.read_text() if self.stats.exists() else "")

    def test_path_with_spaces_is_ranked_using_its_raw_name(self):
        self.send("cd ")
        self.send("space")
        self.key("Enter")
        self.assertIn(f"cd:space dir/\t1\t{self.base}", self.stats.read_text())
        self.key("Enter")
        self.send("pwd > location\n")
        self.assertEqual((self.base / "space dir" / "location").read_text().strip(), str(self.base / "space dir"))


if __name__ == "__main__":
    unittest.main()
