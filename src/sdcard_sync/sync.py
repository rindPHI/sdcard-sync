# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Dominic Steinhöfel
"""Comparison and planning logic, independent of adb and of the filesystem."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

SKIP_NAMES = frozenset({".DS_Store", ".Trashes"})
BATCH_FILES = 120
BATCH_BYTES = 2 * 1024**3


@dataclass(frozen=True)
class FileEntry:
    """A local file together with its path relative to the source directory."""

    rel: str
    size: int
    path: Path


@dataclass(frozen=True)
class Batch:
    """Files that are transferred in a single adb call."""

    dest: str
    files: tuple[FileEntry, ...]

    @property
    def size(self) -> int:
        return sum(file.size for file in self.files)


def scan_local(root: Path, skip_names: Iterable[str] = SKIP_NAMES) -> list[FileEntry]:
    """Collect all regular files below *root*.

    Directories listed in *skip_names* are skipped entirely. Symbolic links and
    unreadable files are ignored.
    """
    skip = set(skip_names)
    root = Path(root)
    entries: list[FileEntry] = []

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [name for name in dirnames if name not in skip]
        relative_dir = os.path.relpath(dirpath, root)
        for filename in filenames:
            if filename in skip:
                continue
            path = Path(dirpath) / filename
            if path.is_symlink():
                continue
            try:
                stat = path.stat()
            except OSError:
                continue
            rel = filename if relative_dir == "." else os.path.join(relative_dir, filename)
            entries.append(FileEntry(rel.replace(os.sep, "/"), stat.st_size, path))

    entries.sort(key=lambda entry: entry.rel)
    return entries


def missing_files(
    local_entries: Sequence[FileEntry],
    remote_sizes: dict[str, int],
) -> list[FileEntry]:
    """Files that are absent on the target or have a different size."""
    return [entry for entry in local_entries if remote_sizes.get(entry.rel) != entry.size]


def plan_batches(
    entries: Sequence[FileEntry],
    max_files: int = BATCH_FILES,
    max_bytes: int = BATCH_BYTES,
) -> list[Batch]:
    """Group files by target directory and split them into transferable batches."""
    grouped: dict[str, list[FileEntry]] = {}
    for entry in entries:
        grouped.setdefault(os.path.dirname(entry.rel), []).append(entry)

    batches: list[Batch] = []
    for dest, files in grouped.items():
        files.sort(key=lambda entry: entry.rel)
        current: list[FileEntry] = []
        current_bytes = 0
        for file in files:
            if current and (len(current) >= max_files or current_bytes + file.size > max_bytes):
                batches.append(Batch(dest, tuple(current)))
                current, current_bytes = [], 0
            current.append(file)
            current_bytes += file.size
        if current:
            batches.append(Batch(dest, tuple(current)))

    batches.sort(key=lambda batch: batch.files[0].rel)
    return batches


def total_size(entries: Iterable[FileEntry]) -> int:
    return sum(entry.size for entry in entries)
