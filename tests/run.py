"""Maintained release checks. PTY suites share fixtures: run sequentially."""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SUITES = ("regression.py", "test_install.py", "test_ui.py", "test_native.py", "diag12.py",
          "diag13.py", "diag14.py", "diag15.py", "diag16.py")

failed = []
for suite in SUITES:
    print(f"\n=== {suite} ===", flush=True)
    result = subprocess.run([sys.executable, "-u", str(ROOT / "tests" / suite)], cwd=ROOT)
    if result.returncode:
        failed.append(suite)

print(f"\n{len(SUITES) - len(failed)}/{len(SUITES)} suites passed.")
if failed:
    print("Failed:", ", ".join(failed))
sys.exit(bool(failed))
