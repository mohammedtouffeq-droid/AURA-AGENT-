"""Offline tests for explicit, non-networking submodule setup behavior."""
from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from engine_auditor import PROJECT_ROOT, load_engine_specs
from setup_engines import main


REGISTRY = """[submodule "sample"]
    path = engines/sample
    url = https://github.com/example/sample.git

[submodule "other"]
    path = engines/other
    url = https://github.com/example/other.git
"""


class SetupTests(unittest.TestCase):
    def make_root(self, *, git: bool = False) -> Path:
        temp = tempfile.TemporaryDirectory(dir=PROJECT_ROOT)
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        (root / ".gitmodules").write_text(REGISTRY, encoding="utf-8")
        if git:
            (root / ".git").mkdir()
        return root

    def test_default_list_does_not_call_git(self) -> None:
        root = self.make_root()
        output = io.StringIO()
        with patch("setup_engines.subprocess.run") as run:
            with contextlib.redirect_stdout(output):
                code = main(["--root", str(root), "--list"])
        self.assertEqual(code, 0)
        run.assert_not_called()
        self.assertIn("2 configured entries", output.getvalue())

    def test_selected_init_passes_only_requested_path(self) -> None:
        root = self.make_root(git=True)
        with patch(
            "setup_engines.subprocess.run",
            return_value=SimpleNamespace(returncode=0, stdout="", stderr=""),
        ) as run:
            with contextlib.redirect_stdout(io.StringIO()):
                code = main(["--root", str(root), "--init", "sample"])
        self.assertEqual(code, 0)
        command = run.call_args.args[0]
        self.assertEqual(command[-1], "engines/sample")
        self.assertNotIn("engines/other", command)
        self.assertFalse(run.call_args.kwargs["shell"])

    def test_all_is_explicit_and_includes_each_registry_path(self) -> None:
        root = self.make_root(git=True)
        with patch(
            "setup_engines.subprocess.run",
            return_value=SimpleNamespace(returncode=0, stdout="", stderr=""),
        ) as run:
            with contextlib.redirect_stdout(io.StringIO()):
                code = main(["--root", str(root), "--all"])
        self.assertEqual(code, 0)
        command = run.call_args.args[0]
        self.assertIn("engines/sample", command)
        self.assertIn("engines/other", command)

    def test_project_registry_is_parseable(self) -> None:
        specs = load_engine_specs(PROJECT_ROOT)
        self.assertEqual(len(specs), 32)
        self.assertEqual(len({spec.path for spec in specs}), 32)


if __name__ == "__main__":
    unittest.main()
