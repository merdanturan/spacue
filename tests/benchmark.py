"""Repeatable warm completion microbenchmark; Python stdlib + zsh only.

Usage: python3 tests/benchmark.py [--plugin /path/to/spacue.zsh]
No timing assertion: filesystem, hardware and installed completion setups vary.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile


SCRIPT = r'''
zmodload zsh/datetime
SPACUE_COMPINIT=0
source "$1"
bench_iterations=$3
for bench_case in package large_directory; do
  _spacue_cleanup_state
  if [[ $bench_case == package ]]; then
    LBUFFER='npm '; bench_prefix='npm build'
  else
    LBUFFER='cd '; bench_prefix='cd dir0'
  fi
  _spacue_collect_from_buffer
  # Model a live menu without invoking ZLE's blocking key-reading loop.
  _spacue_on=1; _spacue_state=preview
  bench_samples=()
  for (( bench_i = 1; bench_i <= bench_iterations; bench_i++ )); do
    bench_start=$EPOCHREALTIME
    for bench_suffix in '' 0 00 000; do
      LBUFFER="$bench_prefix$bench_suffix"
      _spacue_collect_from_buffer
    done
    bench_samples+=("$(( (EPOCHREALTIME - bench_start) * 1000 / 4 ))")
  done
  print -r -- "$bench_case ${(j: :)bench_samples}"
done
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plugin", type=Path, default=Path(__file__).resolve().parents[1] / "spacue.zsh")
    parser.add_argument("--iterations", type=int, default=20)
    args = parser.parse_args()
    if args.iterations < 1:
        parser.error("iterations must be positive")
    with tempfile.TemporaryDirectory(prefix="spacue-bench-") as folder:
        base = Path(folder)
        (base / "package.json").write_text(json.dumps({"scripts": {
            f"build{i:04}": f"echo {i}" for i in range(200)}}))
        for i in range(5000):
            (base / f"dir{i:05}").mkdir()
        stats = base / "stats.tsv"
        stats.write_text("".join(f"other:item{i}\t1\t\n" for i in range(8000)))
        env = dict(os.environ, ZDOTDIR=str(base), SPACUE_STATS_FILE=str(stats))
        startup_script = '''zmodload zsh/datetime; SPACUE_COMPINIT=0
bench_start=$EPOCHREALTIME; source "$1"
print -r -- $(( (EPOCHREALTIME - bench_start) * 1000 ))'''
        startup = []
        for _ in range(12):
            measured = subprocess.run(
                ["zsh", "-fic", startup_script, "startup", str(args.plugin.resolve())],
                cwd=base, env=env, text=True, capture_output=True, timeout=15, check=True)
            if measured.stderr:
                raise RuntimeError(measured.stderr)
            startup.append(float(measured.stdout.strip()))
        result = subprocess.run(
            ["zsh", "-fic", SCRIPT, "benchmark", str(args.plugin.resolve()), str(base), str(args.iterations)],
            cwd=base, env=env, text=True, capture_output=True, timeout=180, check=True)
        if result.stderr:
            raise RuntimeError(result.stderr)
        startup.sort()
        metrics = {"load_ms": {"median_ms": round((startup[5] + startup[6]) / 2, 3),
                               "p95_ms": round(startup[-1], 3), "samples": 12}}
        for line in result.stdout.splitlines():
            name, *samples = line.split()
            numbers = sorted(float(value) for value in samples)
            metrics[name] = {"median_ms": round(numbers[len(numbers) // 2], 3),
                             "p95_ms": round(numbers[min(len(numbers) - 1, int(len(numbers) * .95))], 3)}
        print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
