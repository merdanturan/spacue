"""Fast behavioral regressions; standard Python + the installed zsh only."""
import concurrent.futures
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class RegressionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="spacue-tests-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.env = dict(os.environ, SPACUE_STATS_FILE=str(self.base / "stats.tsv"),
                        SPACUE_COMPINIT="0", ZDOTDIR=str(self.base))

    def shell(self, script):
        result = subprocess.run(
            ["zsh", "-fic", 'source "$1"; ' + script, "test", str(ROOT / "spacue.zsh")],
            cwd=self.base, env=self.env, text=True, capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        return result.stdout.strip()

    def test_package_cache_refreshes_after_edit(self):
        (self.base / "package.json").write_text('{"scripts":{"before":"echo before"}}')
        output = self.shell('''
          _spacue_prov_pkgmgr npm ''; print -rl -- $_spacue_items_list
          print -r -- '{"scripts":{"after":"echo after"}}' > package.json
          touch -t 202001010000 package.json
          _spacue_items_list=(); _spacue_prov_pkgmgr npm ''
          print -r -- SECOND; print -rl -- $_spacue_items_list
        ''')
        self.assertIn("run after", output.split("SECOND\n")[1])
        self.assertNotIn("run before", output.split("SECOND\n")[1])

    def test_package_reader_is_cached_between_menus(self):
        (self.base / "package.json").write_text('{"scripts":{"dev":"vite"}}')
        # Corrupt the input without changing its cache stamp: the second menu
        # must use its parsed snapshot instead of invoking a parser again.
        self.assertEqual(self.shell('''
          _spacue_dispatch npm ''
          touch -r package.json stamp
          print invalid > package.json; touch -r stamp package.json
          _spacue_dispatch npm ''; print -r -- $_spacue_items_list[1]
        '''), "run dev")

    def test_git_cache_avoids_running_git_twice(self):
        output = self.shell('''
          _spacue_git_raw_branches() { print called >> calls; print main; }
          _spacue_dispatch git '' checkout
          _spacue_dispatch git '' checkout
          print -r -- "$(<calls)"
        ''')
        self.assertEqual(output, "called")

    def test_single_script_name_is_one_argument(self):
        (self.base / "package.json").write_text('{"scripts":{"test all; unsafe":"echo test"}}')
        output = self.shell('''
          BUFFER='npm run test'; LBUFFER=$BUFFER
          _spacue_collect_from_buffer; _spacue_open_here
          npm() { print -r -- "$#:${(j:,:)@}"; }
          eval "$BUFFER"
        ''')
        self.assertEqual(output, "2:run,test all; unsafe")

    def test_rank_ignores_invalid_and_handles_decimal_counts(self):
        (self.base / "stats.tsv").write_text(
            "npm:run alpha\tnot-a-number\t\n"
            "npm:run beta\t0008\t\n"
            "npm:run gamma\t999999999999999999999999999\t\n")
        (self.base / "package.json").write_text('{"scripts":{"alpha":"a","beta":"b"}}')
        self.assertEqual(self.shell('_spacue_dispatch npm ""; print -r -- $_spacue_items_list[1]'), "run beta")

    def test_stats_refreshes_after_own_write(self):
        (self.base / "stats.tsv").write_text("cd:alpha/\t1\t\n")
        (self.base / "alpha").mkdir()
        (self.base / "beta").mkdir()
        output = self.shell('''
          _spacue_dispatch cd ''; _spacue_stats_write cd:beta/; _spacue_stats_write cd:beta/
          _spacue_dispatch cd ''; print -r -- $_spacue_items_list[1]
        ''')
        self.assertEqual(output, "beta/")

    def test_selection_is_counted_in_source_directory(self):
        (self.base / "target").mkdir()
        self.shell('''
          _spacue_stats_cmd=cd; _spacue_pre='cd '; SPACUE_KIND=paths
          BUFFER='cd target/'; _spacue_stats_note
          builtin cd target; _spacue_precmd
        ''')
        rows = (self.base / "stats.tsv").read_text().splitlines()
        self.assertIn(f"cd:target/\t1\t{self.base}", rows)
        self.assertNotIn(f"cd:target/\t1\t{self.base}/target", rows)

    def test_concurrent_shells_preserve_counts(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(lambda _: self.shell('_spacue_stats_write cd:target/'), range(24)))
        rows = (self.base / "stats.tsv").read_text().splitlines()
        self.assertIn("cd:target/\t24\t", rows)
        self.assertIn(f"cd:target/\t24\t{self.base}", rows)
        self.assertEqual(os.stat(self.base / "stats.tsv").st_mode & 0o777, 0o600)

    def test_single_path_is_inserted_as_one_shell_argument(self):
        (self.base / "space dir").mkdir()
        output = self.shell('''
          BUFFER='cd space'; LBUFFER=$BUFFER
          _spacue_collect_from_buffer; _spacue_open_here
          print -r -- "$BUFFER"
          eval "$BUFFER"; print -r -- "${PWD:t}"
        ''')
        self.assertEqual(output.splitlines(), [r"cd space\ dir/", "space dir"])

    def test_nested_escaped_path_is_completed(self):
        (self.base / "space dir" / "child").mkdir(parents=True)
        output = self.shell(r'''
          BUFFER='cd space\ dir/ch'; LBUFFER=$BUFFER
          _spacue_collect_from_buffer; _spacue_open_here
          eval "$BUFFER"; print -r -- "${PWD:t}"
        ''')
        self.assertEqual(output, "child")

    def test_escaped_quote_in_path_is_completed(self):
        (self.base / "it's here" / "child").mkdir(parents=True)
        output = self.shell(r'''
          BUFFER="cd it\\'s\\ here/ch"; LBUFFER=$BUFFER
          _spacue_collect_from_buffer; _spacue_open_here
          eval "$BUFFER"; print -r -- "${PWD:t}"
        ''')
        self.assertEqual(output, "child")

    def test_unknown_command_completes_later_arguments(self):
        (self.base / "file.txt").touch()
        self.assertIn("file.txt", self.shell('_spacue_dispatch example "" first; print -rl -- $_spacue_items_list').splitlines())

    def test_last_command_in_pipeline_owns_completion(self):
        (self.base / "package.json").write_text('{"scripts":{"dev":"vite"}}')
        output = self.shell("LBUFFER='echo ok && npm run '; _spacue_collect_from_buffer; print -rl -- $_spacue_items_list")
        self.assertEqual(output, "dev")

    def test_disabled_provider_is_not_called(self):
        self.assertNotIn("run", self.shell("_spacue_disabled_arr=(npm); _spacue_dispatch npm ''; print -rl -- $_spacue_items_list").splitlines())

    def test_ranking_does_not_change_shell_umask(self):
        self.assertEqual(self.shell('umask 022; _spacue_stats_write cd:a; umask'), "022")

    def test_stats_write_does_not_follow_a_predictable_temp_symlink(self):
        output = self.shell('''
          print -r -- valuable > keep
          ln -s "$PWD/keep" "$SPACUE_STATS_FILE.$$"
          _spacue_stats_write cd:a
          print -r -- "$(<keep)"
        ''')
        self.assertEqual(output, "valuable")

    def test_unload_restores_custom_bindings_and_allows_reload(self):
        output = self.shell('''
          bindkey -M menuselect '^G' backward-char
          bindkey -M menuselect '^[' forward-char
          _spacue_shields_on; _spacue_shields_off
          bindkey -M menuselect '^G'; bindkey -M menuselect '^['
          spacue_uninstall; source "$1"
          print -r -- ${widgets[self-insert]}
        ''')
        self.assertEqual(output.splitlines(), ['"^G" backward-char', '"^[" forward-char', 'user:_spacue_self_insert'])


if __name__ == "__main__":
    unittest.main()
