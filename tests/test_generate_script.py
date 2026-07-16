import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class GenerateScriptTests(unittest.TestCase):
    def test_script_runs_from_repo_root(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(dir=repo_root) as tmpdir:
            env = os.environ.copy()
            env["PYTHONPATH"] = str(repo_root)
            env["OUTPUT_DIR"] = tmpdir
            completed = subprocess.run(
                [sys.executable, "scripts/generate.py"],
                cwd=repo_root,
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(completed.returncode, 0, msg=completed.stderr or completed.stdout)
            output_file = Path(tmpdir) / "generated_data.csv"
            self.assertTrue(output_file.exists(), msg="expected generated CSV output")


if __name__ == "__main__":
    unittest.main()
