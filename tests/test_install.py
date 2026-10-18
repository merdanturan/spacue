"""Installer lifecycle in isolated homes; never touches the user's shell."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="spacue-install-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.home = self.base / "home"
        self.home.mkdir()
        self.dotdir = self.base / "zsh"
        self.dotdir.mkdir()
        self.env = dict(os.environ, HOME=str(self.home), ZDOTDIR=str(self.dotdir))

    def run_script(self, path, success=True):
        result = subprocess.run(["sh", str(path)], env=self.env, cwd=self.base,
                                capture_output=True, text=True, timeout=10)
        if success:
            self.assertEqual(result.returncode, 0, result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0)
        return result

    def test_install_is_idempotent_and_uninstall_preserves_other_config(self):
        rc = self.dotdir / ".zshrc"
        rc.write_text("# my shell config\n")
        for _ in range(2):
            self.run_script(ROOT / "install.sh")
        self.assertEqual(rc.read_text().count("# >>> spacue >>>"), 1)
        self.assertFalse((self.home / ".zshrc").exists())
        self.assertEqual((self.home / ".spacue/spacue.zsh").read_bytes(), (ROOT / "spacue.zsh").read_bytes())
        self.run_script(ROOT / "uninstall.sh")
        self.assertEqual(rc.read_text().strip(), "# my shell config")
        self.assertFalse((self.home / ".spacue").exists())

    def test_failed_update_preserves_working_plugin(self):
        self.run_script(ROOT / "install.sh")
        old = (self.home / ".spacue/spacue.zsh").read_bytes()
        bad = self.base / "bad"
        bad.mkdir()
        shutil.copyfile(ROOT / "install.sh", bad / "install.sh")
        (bad / "spacue.zsh").write_text("invalid download\n")
        self.run_script(bad / "install.sh", success=False)
        self.assertEqual((self.home / ".spacue/spacue.zsh").read_bytes(), old)


if __name__ == "__main__":
    unittest.main()
