#!/usr/bin/env python3
"""Collect files from a folder tree and nested ZIP archives into one directory."""

from __future__ import annotations

import argparse
import os
import re
import stat
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO


__version__ = "1.0.0"
CHUNK_SIZE = 1024 * 1024
SPOOL_MEMORY_LIMIT = 8 * 1024 * 1024
GIB = 1024 ** 3


@dataclass
class Totals:
    folder_files: int = 0
    archive_files: int = 0
    zip_archives: int = 0
    warnings: int = 0
    unpacked_bytes: int = 0

    @property
    def collected(self) -> int:
        return self.folder_files + self.archive_files


class ArchiveLimitError(Exception):
    """An archive exceeds the configured extraction limits."""


class Collector:
    def __init__(
        self,
        destination: Path,
        *,
        dry_run: bool,
        verbose: bool,
        keep_zips: bool,
        max_depth: int,
        max_entry_bytes: int,
        max_total_bytes: int,
    ) -> None:
        self.destination = destination
        self.dry_run = dry_run
        self.verbose = verbose
        self.keep_zips = keep_zips
        self.max_depth = max_depth
        self.max_entry_bytes = max_entry_bytes
        self.max_total_bytes = max_total_bytes
        self.totals = Totals()
        self.used_names: set[str] = set()

        if destination.exists():
            self.used_names.update(item.name.casefold() for item in destination.iterdir())
        elif not dry_run:
            destination.mkdir(parents=True, exist_ok=True)

    def warn(self, source: str, message: str) -> None:
        self.totals.warnings += 1
        print(f"[WARNING] {source!r}: {message}", file=sys.stderr)

    @staticmethod
    def safe_name(value: str) -> str | None:
        # Flatten both POSIX and Windows paths stored in archive members.
        name = value.replace("\\", "/").rsplit("/", 1)[-1]
        name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).rstrip(" .")
        if not name or name in {".", ".."}:
            return None

        # Windows treats these names as reserved even when they have extensions.
        if re.match(r"^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)", name, re.I):
            name = f"_{name}"

        suffix = Path(name).suffix
        stem = name[: -len(suffix)] if suffix else name
        max_stem_bytes = max(1, 180 - len(suffix.encode("utf-8")))
        stem = stem.encode("utf-8")[:max_stem_bytes].decode("utf-8", "ignore")
        return f"{stem}{suffix}"

    def target_for(self, name: str) -> Path | None:
        clean = self.safe_name(name)
        if clean is None:
            return None

        extension = Path(clean).suffix
        stem = clean[: -len(extension)] if extension else clean
        candidate = clean
        sequence = 2

        while (
            candidate.casefold() in self.used_names
            or (self.destination / candidate).exists()
        ):
            candidate = f"{stem}_{sequence}{extension}"
            sequence += 1

        self.used_names.add(candidate.casefold())
        return self.destination / candidate

    def transfer(
        self,
        source: BinaryIO,
        target: BinaryIO,
        *,
        from_zip: bool,
    ) -> None:
        entry_bytes = 0
        while True:
            data = source.read(CHUNK_SIZE)
            if not data:
                break

            if from_zip:
                entry_bytes += len(data)
                if entry_bytes > self.max_entry_bytes:
                    raise ArchiveLimitError("ZIP entry exceeds the per-file size limit")
                if self.totals.unpacked_bytes + len(data) > self.max_total_bytes:
                    raise ArchiveLimitError("ZIP contents exceed the total extraction limit")
                self.totals.unpacked_bytes += len(data)

            target.write(data)

    def collect_stream(
        self,
        stream: BinaryIO | None,
        name: str,
        source_label: str,
        *,
        from_zip: bool,
        size_hint: int = 0,
        precharged: bool = False,
    ) -> None:
        if from_zip and not precharged:
            if size_hint > self.max_entry_bytes:
                self.warn(source_label, "ZIP entry exceeds the per-file size limit")
                return
            if self.totals.unpacked_bytes + size_hint > self.max_total_bytes:
                self.warn(source_label, "ZIP entry would exceed the total extraction limit")
                return

        target = self.target_for(name)
        if target is None:
            self.warn(source_label, "File has no usable name")
            return

        if self.dry_run:
            if from_zip and not precharged:
                self.totals.unpacked_bytes += size_hint
            self.record(target, source_label, from_zip)
            return

        created = False
        try:
            if stream is None:
                raise OSError("Input stream is missing")
            with target.open("xb") as output:
                created = True
                self.transfer(stream, output, from_zip=from_zip and not precharged)
        except (OSError, ValueError, RuntimeError, zipfile.BadZipFile, ArchiveLimitError, EOFError) as exc:
            if created:
                target.unlink(missing_ok=True)
            self.warn(source_label, str(exc))
            return

        self.record(target, source_label, from_zip)

    def record(self, target: Path, source_label: str, from_zip: bool) -> None:
        if from_zip:
            self.totals.archive_files += 1
        else:
            self.totals.folder_files += 1

        if self.dry_run or self.verbose:
            action = "PLAN" if self.dry_run else "COPY"
            print(f"[{action}] {source_label!r} -> {str(target)!r}")
        elif self.totals.collected % 250 == 0:
            print(f"Collected {self.totals.collected:,} files...")

    def process_regular_file(self, path: Path) -> None:
        label = str(path)
        if self.dry_run:
            self.collect_stream(None, path.name, label, from_zip=False)
            return

        try:
            with path.open("rb") as source:
                self.collect_stream(source, path.name, label, from_zip=False)
        except OSError as exc:
            self.warn(label, str(exc))

    def process_zip(self, archive: zipfile.ZipFile, label: str, depth: int) -> None:
        self.totals.zip_archives += 1
        for member in archive.infolist():
            if member.is_dir():
                continue

            entry_label = f"{label}!{member.filename}"
            if member.create_system == 3 and stat.S_ISLNK(member.external_attr >> 16):
                self.warn(entry_label, "ZIP symbolic link was skipped")
                continue

            name = self.safe_name(member.filename)
            if name is None:
                self.warn(entry_label, "ZIP entry has no usable filename")
                continue

            is_nested_zip = name.lower().endswith(".zip")
            if not is_nested_zip:
                if self.dry_run:
                    self.collect_stream(
                        None, name, entry_label, from_zip=True, size_hint=member.file_size
                    )
                else:
                    try:
                        with archive.open(member) as source:
                            self.collect_stream(
                                source,
                                name,
                                entry_label,
                                from_zip=True,
                                size_hint=member.file_size,
                            )
                    except (OSError, RuntimeError, ValueError, NotImplementedError, zipfile.BadZipFile, EOFError) as exc:
                        self.warn(entry_label, str(exc))
                continue

            if depth >= self.max_depth:
                self.warn(entry_label, "Maximum nested ZIP depth reached")
                continue
            if member.file_size > self.max_entry_bytes:
                self.warn(entry_label, "Nested ZIP exceeds the per-file size limit")
                continue
            if self.totals.unpacked_bytes + member.file_size > self.max_total_bytes:
                self.warn(entry_label, "Nested ZIP would exceed the total extraction limit")
                continue

            try:
                # Stage nested archives in memory until 8 MiB, then use a temp file.
                with tempfile.SpooledTemporaryFile(max_size=SPOOL_MEMORY_LIMIT) as staged:
                    with archive.open(member) as source:
                        self.transfer(source, staged, from_zip=True)

                    if self.keep_zips:
                        staged.seek(0)
                        self.collect_stream(
                            staged, name, entry_label, from_zip=True, precharged=True
                        )

                    staged.seek(0)
                    with zipfile.ZipFile(staged) as nested:
                        self.process_zip(nested, entry_label, depth + 1)
            except (OSError, RuntimeError, ValueError, NotImplementedError, zipfile.BadZipFile, ArchiveLimitError, EOFError) as exc:
                self.warn(entry_label, str(exc))

    def process_zip_file(self, path: Path) -> None:
        label = str(path)
        if self.keep_zips:
            self.process_regular_file(path)

        try:
            with zipfile.ZipFile(path) as archive:
                self.process_zip(archive, label, depth=1)
        except (OSError, RuntimeError, ValueError, zipfile.BadZipFile, EOFError) as exc:
            self.warn(label, str(exc))

    def run(self, source: Path) -> Totals:
        def walk_error(error: OSError) -> None:
            self.warn(error.filename or str(source), str(error))

        for root, directories, filenames in os.walk(source, followlinks=False, onerror=walk_error):
            root_path = Path(root)
            directories[:] = sorted(
                directory
                for directory in directories
                if not (root_path / directory).is_symlink()
                and (root_path / directory).resolve() != self.destination
            )

            for filename in sorted(filenames):
                path = root_path / filename
                if path.is_symlink():
                    self.warn(str(path), "Symbolic link was skipped")
                    continue
                if path.suffix.lower() == ".zip":
                    self.process_zip_file(path)
                else:
                    self.process_regular_file(path)

        return self.totals


def select_folder(title: str) -> str:
    try:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        try:
            return filedialog.askdirectory(title=title, parent=root)
        finally:
            root.destroy()
    except Exception as exc:
        raise RuntimeError("Folder picker is unavailable. Use folder paths instead.") from exc


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Collect files from subfolders and nested ZIPs into one folder."
    )
    parser.add_argument("source", nargs="?", help="Folder to search")
    parser.add_argument("destination", nargs="?", help="Folder to collect files into")
    parser.add_argument("--gui", action="store_true", help="Select folders using dialogs")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing files")
    parser.add_argument("--keep-zips", action="store_true", help="Copy ZIP containers as well as their contents")
    parser.add_argument("--verbose", action="store_true", help="Print each collected file")
    parser.add_argument("--max-depth", type=int, default=6, help="Nested ZIP depth limit (default: 6)")
    parser.add_argument("--max-entry-gb", type=float, default=2.0, help="Largest uncompressed ZIP entry in GiB (default: 2)")
    parser.add_argument("--max-total-gb", type=float, default=10.0, help="Total ZIP extraction limit in GiB (default: 10)")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    arguments = parser.parse_args()

    if arguments.max_depth < 1 or arguments.max_entry_gb <= 0 or arguments.max_total_gb <= 0:
        parser.error("Archive depth and size limits must be greater than zero")

    try:
        if arguments.source:
            source_raw = arguments.source
        elif arguments.gui:
            source_raw = select_folder("Select the folder to collect")
        else:
            source_raw = input("Source folder: ").strip().strip('"')

        if not source_raw:
            parser.error("A source folder is required")

        source = Path(source_raw).expanduser().resolve()
        if not source.is_dir():
            parser.error(f"Source is not a folder: {source}")

        default_destination = source.parent / f"{source.name}_flattened"
        if arguments.destination:
            destination_raw = arguments.destination
        elif arguments.gui:
            destination_raw = select_folder("Select the destination folder")
        else:
            destination_raw = str(default_destination)

        if not destination_raw:
            parser.error("A destination folder is required")

        destination = Path(destination_raw).expanduser().resolve()
        if destination == source:
            parser.error("Source and destination must be different folders")
        if destination.exists() and not destination.is_dir():
            parser.error(f"Destination is not a folder: {destination}")

        print(f"Version: {__version__}")
        print(f"Source: {source}")
        print(f"Destination: {destination}")
        print(f"Mode: {'PREVIEW' if arguments.dry_run else 'COPY'}")
        print()

        collector = Collector(
            destination,
            dry_run=arguments.dry_run,
            verbose=arguments.verbose,
            keep_zips=arguments.keep_zips,
            max_depth=arguments.max_depth,
            max_entry_bytes=int(arguments.max_entry_gb * GIB),
            max_total_bytes=int(arguments.max_total_gb * GIB),
        )
        result = collector.run(source)
        print("\nSummary")
        print(f"Files from folders: {result.folder_files:,}")
        print(f"Files from ZIPs:    {result.archive_files:,}")
        print(f"Total files:        {result.collected:,}")
        print(f"ZIPs processed:     {result.zip_archives:,}")
        print(f"Warnings:           {result.warnings:,}")
        if arguments.dry_run:
            print("Preview only. No files were written.")
        elif result.warnings:
            print("Completed with warnings. Review skipped files above.")
        else:
            print("Completed. Original files were not changed.")
        return 0 if result.warnings == 0 else 1
    except (EOFError, KeyboardInterrupt):
        print("\nCanceled.", file=sys.stderr)
        return 130
    except (OSError, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
