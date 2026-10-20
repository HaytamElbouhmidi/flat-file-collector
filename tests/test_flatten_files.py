"""Tests for Flat File Collector 1.0.0."""

from __future__ import annotations

import io
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "flatten_files.py"


class FileCollectorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = self.root / "source"
        self.destination = self.root / "output"
        self.source.mkdir()

    def run_script(self, *options: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), str(self.source), str(self.destination), *options],
            capture_output=True,
            text=True,
            check=False,
        )

    def test_folders_duplicate_names_and_case(self) -> None:
        (self.source / "alpha").mkdir()
        (self.source / "beta").mkdir()
        (self.source / "alpha" / "report.txt").write_text("A")
        (self.source / "beta" / "report.txt").write_text("B")
        (self.source / "REPORT.TXT").write_text("C")
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(list(self.destination.iterdir())), 3)
        self.assertEqual({p.read_text() for p in self.destination.iterdir()}, {"A", "B", "C"})

    def test_nested_archives_and_zip_paths(self) -> None:
        staged = io.BytesIO()
        with zipfile.ZipFile(staged, "w") as inside:
            inside.writestr("nested/data.csv", "1,2,3")
        with zipfile.ZipFile(self.source / "outer.zip", "w") as outer:
            outer.writestr("manual.pdf", b"PDF")
            outer.writestr("folder/inner.zip", staged.getvalue())
            outer.writestr("../../escape.txt", "SAFE")
            outer.writestr(r"windows\subfolder\test.txt", "WINDOWS")
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            {p.name for p in self.destination.iterdir()},
            {"manual.pdf", "data.csv", "escape.txt", "test.txt"},
        )
        self.assertEqual((self.destination / "escape.txt").read_text(), "SAFE")
        self.assertFalse((self.root / "escape.txt").exists())

    def test_preview_writes_nothing(self) -> None:
        (self.source / "data.bin").write_bytes(b"payload")
        result = self.run_script("--dry-run")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Preview only", result.stdout)
        self.assertFalse(self.destination.exists())

    def test_existing_output_untouched(self) -> None:
        (self.source / "example.txt").write_text("NEW")
        self.destination.mkdir()
        (self.destination / "example.txt").write_text("ORIGINAL")
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.destination / "example.txt").read_text(), "ORIGINAL")
        self.assertEqual((self.destination / "example_2.txt").read_text(), "NEW")

    def test_output_inside_source_is_not_scanned(self) -> None:
        self.destination = self.source / "collected"
        self.destination.mkdir()
        (self.destination / "existing.txt").write_text("KEEP")
        (self.source / "new.txt").write_text("NEW")
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual({p.name for p in self.destination.iterdir()}, {"existing.txt", "new.txt"})

    def test_keep_zip_containers(self) -> None:
        with zipfile.ZipFile(self.source / "parts.zip", "w") as archive:
            archive.writestr("part.txt", "part")
        result = self.run_script("--keep-zips")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual({p.name for p in self.destination.iterdir()}, {"parts.zip", "part.txt"})

    def test_entry_limit_skips_oversized_member(self) -> None:
        with zipfile.ZipFile(self.source / "large.zip", "w") as archive:
            archive.writestr("big.bin", b"a" * 2048)
            archive.writestr("tiny.txt", b"yes")
        result = self.run_script("--max-entry-gb", "0.000001")
        self.assertEqual(result.returncode, 1)
        self.assertEqual({p.name for p in self.destination.iterdir()}, {"tiny.txt"})

    def test_nested_archive_preview_does_not_write_files(self) -> None:
        staged = io.BytesIO()
        with zipfile.ZipFile(staged, "w") as inner:
            inner.writestr("inner.txt", "payload")
        with zipfile.ZipFile(self.source / "outer.zip", "w") as outer:
            outer.writestr("nested.zip", staged.getvalue())
        result = self.run_script("--dry-run")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Files from ZIPs:    1", result.stdout)
        self.assertFalse(self.destination.exists())

    def test_keep_nested_zip_containers(self) -> None:
        staged = io.BytesIO()
        with zipfile.ZipFile(staged, "w") as inner:
            inner.writestr("inner.txt", "payload")
        with zipfile.ZipFile(self.source / "outer.zip", "w") as outer:
            outer.writestr("nested.zip", staged.getvalue())
        result = self.run_script("--keep-zips")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            {p.name for p in self.destination.iterdir()},
            {"outer.zip", "nested.zip", "inner.txt"},
        )

    def test_corrupt_zip_does_not_stop_other_files(self) -> None:
        (self.source / "bad.zip").write_bytes(b"not an archive")
        (self.source / "good.txt").write_text("GOOD")
        result = self.run_script()
        self.assertEqual(result.returncode, 1)
        self.assertEqual((self.destination / "good.txt").read_text(), "GOOD")


if __name__ == "__main__":
    unittest.main()
