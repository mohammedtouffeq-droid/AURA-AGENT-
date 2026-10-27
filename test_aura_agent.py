"""Focused offline tests for Aura's registry and audit helpers."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from engine_auditor import PROJECT_ROOT, audit_engines, load_engine_specs, parse_submodule_status


VALID_REGISTRY = """[submodule "engines/sample"]
    path = engines/sample
    url = https://github.com/example/sample.git
"""


class RegistryTests(unittest.TestCase):
    def write_registry(self, root: Path, content: str = VALID_REGISTRY) -> None:
        (root / ".gitmodules").write_text(content, encoding="utf-8")

    def test_project_registry_is_parseable_and_unique(self) -> None:
        specs = load_engine_specs(PROJECT_ROOT)
        self.assertGreater(len(specs), 0)
        self.assertEqual(len({spec.path for spec in specs}), len(specs))

    def test_parses_registry_entry(self) -> None:
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT) as directory:
            root = Path(directory)
            self.write_registry(root)
            specs = load_engine_specs(root)
        self.assertEqual(len(specs), 1)
        self.assertEqual(specs[0].name, "engines/sample")
        self.assertEqual(specs[0].path, "engines/sample")
        self.assertEqual(specs[0].url, "https://github.com/example/sample.git")

    def test_rejects_path_traversal(self) -> None:
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT) as directory:
            root = Path(directory)
            self.write_registry(root, VALID_REGISTRY.replace("engines/sample", "engines/../outside"))
            with self.assertRaises(ValueError):
                load_engine_specs(root)

    def test_rejects_non_github_url(self) -> None:
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT) as directory:
            root = Path(directory)
            self.write_registry(root, VALID_REGISTRY.replace("https://github.com", "https://evil.example"))
            with self.assertRaises(ValueError):
                load_engine_specs(root)

    def test_parses_git_status_markers(self) -> None:
        commit = "a" * 40
        status = parse_submodule_status(
            f" {commit} engines/ready (heads/main)\n"
            f"-{'b' * 40} engines/missing\n"
            f"+{'c' * 40} engines/mismatch (heads/other)\n"
            f"U{'d' * 40} engines/conflict\n"
        )
        self.assertEqual(status["engines/ready"], ("initialized_at_pinned_commit", commit))
        self.assertEqual(status["engines/missing"][0], "not_initialized")
        self.assertEqual(status["engines/mismatch"][0], "commit_mismatch")
        self.assertEqual(status["engines/conflict"][0], "merge_conflict")

    def test_audit_does_not_inherit_parent_git_checkout(self) -> None:
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT) as directory:
            root = Path(directory)
            self.write_registry(root)
            report = audit_engines(root)
        self.assertFalse(report["git_status_available"])
        self.assertEqual(report["engines"][0]["state"], "unverifiable")


if __name__ == "__main__":
    unittest.main()
