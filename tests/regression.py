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
        # An unchanged warm menu must not select/invoke a JSON decoder again.
        self.assertEqual(self.shell('''
          functions[_original_has]=$functions[_spacue_has]
          reader_probes=0
          _spacue_has() { (( reader_probes += 1 )); _original_has "$@"; }
          _spacue_dispatch npm ''
          first_probes=$reader_probes
          _spacue_dispatch npm ''
          (( first_probes > 0 && first_probes == reader_probes )) && print cached
          print -r -- $_spacue_items_list[1]
        '''), "cached\nrun dev")

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

    def test_active_package_menu_reuses_full_candidates_before_cap(self):
        (self.base / "package.json").write_text('{"scripts":{"alpha":"a","beta":"b","gamma":"g"}}')
        output = self.shell('''
          functions[_original_pkg]=$functions[_spacue_prov_pkgmgr]
          _spacue_prov_pkgmgr() { print call >> calls; _original_pkg "$@"; }
          SPACUE_MAX=2; LBUFFER='npm '; _spacue_collect_from_buffer
          _spacue_on=1; _spacue_state=preview
          LBUFFER='npm g'; _spacue_collect_from_buffer
          print -r -- $_spacue_items_list[1]
          LBUFFER='npm b'; _spacue_collect_from_buffer
          print -r -- $_spacue_items_list[1]
          print -r -- "$(<calls)"
        ''')
        self.assertEqual(output.splitlines(), ["run gamma", "run beta", "call"])

    def test_custom_provider_is_called_for_every_filter(self):
        output = self.shell('''
          _dynamic() { print "$2" >> calls; spacue_add "$2-result"; }
          spacue_register example _dynamic
          LBUFFER='example a'; _spacue_collect_from_buffer
          _spacue_on=1; _spacue_state=preview
          LBUFFER='example b'; _spacue_collect_from_buffer
          print -r -- $_spacue_items_list[1]; print -r -- "$(<calls)"
        ''')
        self.assertEqual(output.splitlines(), ["b-result", "a", "b"])

    def test_menu_snapshot_refreshes_after_package_change_and_close(self):
        (self.base / "package.json").write_text('{"scripts":{"alpha":"a","beta":"b"}}')
        output = self.shell('''
          LBUFFER='npm '; _spacue_collect_from_buffer
          _spacue_on=1; _spacue_state=preview
          print -r -- '{"scripts":{"gamma":"g"}}' > package.json
          touch -t 202001010000 package.json
          LBUFFER='npm g'; _spacue_collect_from_buffer
          print -r -- $_spacue_items_list[1]
          _spacue_cleanup_state
          print -r -- '{"scripts":{"delta":"d"}}' > package.json
          touch -t 202101010000 package.json
          LBUFFER='npm d'; _spacue_collect_from_buffer
          print -r -- $_spacue_items_list[1]
        ''')
        self.assertEqual(output.splitlines(), ["run gamma", "run delta"])

    def test_directory_snapshot_keeps_hidden_and_child_directory_contexts(self):
        for name in ("alpha", "beta", ".hidden", "alpha/child"):
            (self.base / name).mkdir(parents=True, exist_ok=True)
        output = self.shell('''
          LBUFFER='cd '; _spacue_collect_from_buffer
          _spacue_on=1; _spacue_state=preview
          LBUFFER='cd .h'; _spacue_collect_from_buffer
          print -r -- $_spacue_items_list[1]
          LBUFFER='cd alpha/ch'; _spacue_collect_from_buffer
          print -r -- $_spacue_items_list[1]
          _spacue_cleanup_state; mkdir fresh
          LBUFFER='cd f'; _spacue_collect_from_buffer
          print -r -- $_spacue_items_list[1]
        ''')
        self.assertEqual(output.splitlines(), [".hidden/", "alpha/child/", "fresh/"])

    def test_stats_cache_tracks_atomic_replacement_removal_and_configured_path(self):
        output = self.shell('''
          print -r -- $'npm:test\t1\t' > "$SPACUE_STATS_FILE"
          _spacue_stats_load
          print -r -- $'npm:test\t9\t' > replacement
          mv replacement "$SPACUE_STATS_FILE"
          _spacue_stats_load; print -r -- ${_spacue_statG[npm:test]}
          rm "$SPACUE_STATS_FILE"
          _spacue_stats_load; print -r -- ${_spacue_statG[npm:test]-missing}
          SPACUE_STATS_FILE="$PWD/other.tsv"
          print -r -- $'npm:test\t4\t' > "$SPACUE_STATS_FILE"
          _spacue_stats_load; print -r -- ${_spacue_statG[npm:test]}
        ''')
        self.assertEqual(output.splitlines(), ["9", "missing", "4"])

    def test_stats_cache_changes_with_directory_and_refreshes_at_prompt(self):
        (self.base / "child").mkdir()
        output = self.shell('''
          print -r -- "npm:test"$'\t2\t'"$PWD" > "$SPACUE_STATS_FILE"
          print -r -- "npm:test"$'\t7\t'"$PWD/child" >> "$SPACUE_STATS_FILE"
          _spacue_stats_load; print -r -- ${_spacue_statD[npm:test]}
          builtin cd child
          _spacue_stats_load; print -r -- ${_spacue_statD[npm:test]}
          # An editor may rewrite in place without changing second-level mtime.
          print -r -- "npm:test"$'\t8\t'"$PWD" > "$SPACUE_STATS_FILE"
          _spacue_precmd; _spacue_stats_load
          print -r -- ${_spacue_statD[npm:test]}
        ''')
        self.assertEqual(output.splitlines(), ["2", "7", "8"])

    def test_unchanged_stats_are_parsed_once_per_prompt(self):
        output = self.shell('''
          functions[_original_parse]=$functions[_spacue_stats_parse]
          _spacue_stats_parse() { print parsed >> reads; _original_parse "$@"; }
          print -r -- $'npm:test\t1\t' > "$SPACUE_STATS_FILE"
          _spacue_stats_load; _spacue_stats_load; _spacue_stats_load
          print -r -- "$(<reads)"; print -r -- ${_spacue_statG[npm:test]}
        ''')
        self.assertEqual(output.splitlines(), ["parsed", "1"])

    def test_dynamic_completion_styles_keep_evaluating_after_menu(self):
        output = self.shell('''
          counter=1
          zstyle -e ':completion:*' menu 'reply=(select=$counter)'
          zstyle -e ':completion:*' completer 'reply=(_complete value-$counter)'
          _spacue_style_on; _spacue_style_off
          counter=2
          zstyle -a ':completion:*' menu reply; print -r -- "$reply"
          zstyle -a ':completion:*' completer reply; print -r -- "$reply"
        ''')
        self.assertEqual(output.splitlines(), ["select=2", "_complete value-2"])

    def test_path_filter_keeps_literal_glob_characters_and_empty_descriptions(self):
        for name in ("a[1]", "a*literal", "-flaglike", "ordinary"):
            (self.base / name).touch()
        output = self.shell('''
          _spacue_dispatch cat 'a['
          print -r -- "$#_spacue_items_list:$#_spacue_descs_list:$_spacue_items_list[1]"
          _spacue_dispatch cat 'a*'
          print -r -- $_spacue_items_list[1]
          _spacue_dispatch cat ''
          print -r -- ${(j:,:)_spacue_items_list}
        ''')
        lines = output.splitlines()
        self.assertEqual(lines[:2], ["1:1:a[1]", "a*literal"])
        self.assertEqual(len(lines), 3)
        # zsh orders punctuation differently across locales; test membership
        # and multiplicity without imposing C collation on the user's shell.
        self.assertCountEqual(lines[2].split(","), ["a*literal", "a[1]", "ordinary"])

    def test_stats_parser_consumes_the_supplied_snapshot(self):
        (self.base / "stats.tsv").write_text("npm:test\t9\t\n")
        self.assertEqual(self.shell("_spacue_stats_parse $'npm:test\t3\t'; print -r -- ${_spacue_statG[npm:test]}"), "3")

    def test_stats_remain_readable_with_restrictive_user_umask(self):
        output = self.shell('''
          umask 777
          _spacue_stats_write cd:a
          umask
          _spacue_stats_load; print -r -- ${_spacue_statG[cd:a]-missing}
        ''')
        self.assertEqual(output.splitlines(), ["0777", "1"])

    def test_package_cache_detects_atomic_replacement_with_identical_mtime(self):
        (self.base / "package.json").write_text('{"scripts":{"old":"echo old"}}')
        output = self.shell('''
          _spacue_dispatch npm ''
          print -r -- '{"scripts":{"new":"echo new"}}' > replacement
          touch -r package.json replacement; mv replacement package.json
          _spacue_dispatch npm ''; print -r -- $_spacue_items_list[1]
        ''')
        self.assertEqual(output, "run new")

    def test_make_cache_detects_atomic_replacement_with_identical_mtime(self):
        (self.base / "Makefile").write_text("old: ## old target\n")
        output = self.shell('''
          _spacue_dispatch make ''
          print -r -- 'new: ## new target' > replacement
          touch -r Makefile replacement; mv replacement Makefile
          _spacue_dispatch make ''; print -r -- $_spacue_items_list[1]
        ''')
        self.assertEqual(output, "new")

    def test_prompt_refreshes_file_data_when_metadata_is_coarse(self):
        (self.base / "package.json").write_text('{"scripts":{"old":"echo old"}}')
        output = self.shell('''
          _spacue_file_stamp() { REPLY=coarse-metadata; }
          _spacue_dispatch npm ''
          touch -r package.json timestamp
          print -r -- '{"scripts":{"new":"echo new"}}' > package.json
          touch -r timestamp package.json
          _spacue_precmd
          _spacue_dispatch npm ''; print -r -- $_spacue_items_list[1]
        ''')
        self.assertEqual(output, "run new")

    def test_package_decodes_fresh_if_content_stamp_is_unavailable(self):
        (self.base / "package.json").write_text('{"scripts":{"old":"echo old"}}')
        output = self.shell('''
          _spacue_source_stamp() { REPLY=''; return 1; }
          _spacue_dispatch npm ''
          print -r -- '{"scripts":{"new":"echo new"}}' > package.json
          _spacue_dispatch npm ''; print -r -- $_spacue_items_list[1]
        ''')
        self.assertEqual(output, "run new")


if __name__ == "__main__":
    unittest.main()
