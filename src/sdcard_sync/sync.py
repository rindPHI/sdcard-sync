# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Dominic Steinhöfel
"""Vergleichs- und Planungslogik, unabhängig von adb und vom Dateisystem."""

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
    """Eine lokale Datei mit ihrem Zielpfad relativ zur Quelle."""

    rel: str
    size: int
    path: Path


@dataclass(frozen=True)
class Batch:
    """Eine Gruppe von Dateien, die in einem adb-Aufruf übertragen wird."""

    dest: str
    files: tuple[FileEntry, ...]

    @property
    def size(self) -> int:
        return sum(file.size for file in self.files)


def scan_local(root: Path, skip_names: Iterable[str] = SKIP_NAMES) -> list[FileEntry]:
    """Liest alle regulären Dateien unter *root* ein.

    Verzeichnisse in *skip_names* werden komplett übersprungen, symbolische
    Links und nicht lesbare Dateien ignoriert.
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
    """Dateien, die auf dem Ziel fehlen oder eine andere Größe haben."""
    return [entry for entry in local_entries if remote_sizes.get(entry.rel) != entry.size]


def plan_batches(
    entries: Sequence[FileEntry],
    max_files: int = BATCH_FILES,
    max_bytes: int = BATCH_BYTES,
) -> list[Batch]:
    """Gruppiert Dateien nach Zielordner und zerlegt sie in handliche Pakete."""
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
