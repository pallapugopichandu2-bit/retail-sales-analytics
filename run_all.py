"""Run the whole project in one command.

Usage: python run_all.py <dataset .xlsx or .csv>
Results are saved in a folder called "output" next to this file.
"""
import subprocess
import sys
from pathlib import Path

here = Path(__file__).parent
out = here / "output"

if len(sys.argv) != 2:
    sys.exit(__doc__)

for script, args in [("01_clean.py", [sys.argv[1], str(out)]),
                     ("02_build_db.py", [str(out)]),
                     ("04_analysis.py", [str(out)])]:
    print(f"\n=== {script} ===")
    subprocess.run([sys.executable, str(here / script), *args], check=True)

print(f"\nDone. Open the folder: {out}")
print("Send findings.md and cleaning_log.csv to get your README results and resume bullets.")
