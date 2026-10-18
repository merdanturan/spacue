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
        self.t.send("PS1='PS> '; bindkey -e; source " + shlex.quote(str(PLUGIN)) + "\n")
        self.t.wait_idle(0.15)
        # Local function records argv without launching a package manager.
        self.t.send("npm() { print -r -- \"$#:${(j:,:)@}\" > argv; }; clear\n")
        self.t.wait_idle(0.1)

    def send(self, text):
        self.t.send(text)
        self.t.wait_idle(0.15)

    def key(self, name):
        self.t.send_keys(name)
        self.t.wait_idle(0.15)

    def row(self):
        return [r.strip() for r in self.t.screen.text().splitlines() if "PS>" in r][-1]

    def test_filtered_single_enter_accepts_then_runs(self):
        self.send("npm ")
        self.send("dev")
        self.assertEqual(self.row(), "PS> npm run dev")
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
