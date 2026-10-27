# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Dominic Steinhöfel
"""Command line interface for sdcard-sync."""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from pathlib import Path
from typing import Sequence

from .adb import Adb, AdbError
from .sync import (
    BATCH_BYTES,
    BATCH_FILES,
    Batch,
    missing_files,
    plan_batches,
    scan_local,
    total_size,
)

LOG_PATH = Path.home() / "Library" / "Logs" / "sdcard-sync.log"
LOGGER = logging.getLogger("sdcard_sync")


def configure_logging() -> None:
    LOGGER.setLevel(logging.INFO)
    LOGGER.handlers.clear()
    formatter = logging.Formatter("[%(asctime)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

    stream = logging.StreamHandler(sys.stdout)
    stream.setFormatter(formatter)
    LOGGER.addHandler(stream)

    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(LOG_PATH, encoding="utf-8")
        file_handler.setFormatter(formatter)
        LOGGER.addHandler(file_handler)
    except OSError:
        pass


def log(message: str = "") -> None:
    LOGGER.info(message)


def confirm(question: str, auto_yes: bool = False, stream=None) -> bool:
    """Ask for an explicit yes or no answer."""
    if auto_yes:
        log("Confirmed (--yes).")
        return True
    stream = stream or sys.stdin
    if not stream.isatty():
        raise AdbError("No interactive input available. Pass --yes to confirm explicitly.")
    while True:
        answer = input(question).strip().lower()
        if answer in ("y", "yes", "j", "ja"):
            return True
        if answer in ("", "n", "no", "nein"):
            return False
        print("Please answer yes or no.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sdcard-sync",
        description="Synchronize a local directory with the SD card of an Android device.",
    )
    parser.add_argument(
        "--source",
        required=True,
        help="source directory (required), for example a phone backup",
    )
    parser.add_argument(
        "--remote",
        help="target path on the device (default: detected SD card)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="show what would be transferred without writing",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="skip the confirmation prompt (automation only)",
    )
    parser.add_argument(
        "--batch-files",
        type=int,
        default=BATCH_FILES,
        help=f"maximum files per adb call (default: {BATCH_FILES})",
    )
    parser.add_argument(
        "--batch-mb",
        type=int,
        default=BATCH_BYTES // (1024 * 1024),
        help=f"maximum batch size in MB (default: {BATCH_BYTES // (1024 * 1024)})",
    )
    return parser


def upload(
    adb: Adb,
    remote: str,
    batches: Sequence[Batch],
    total_bytes: int,
    total_files: int,
) -> tuple[int, int, list[Batch]]:
    """Push all batches and return (files, bytes, failed batches)."""
    done_files = 0
    done_bytes = 0
    failed: list[Batch] = []
    started = time.time()

    for index, batch in enumerate(batches, 1):
        dest = os.path.join(remote, batch.dest) if batch.dest else remote
        success = False
        for attempt in range(1, 4):
            try:
                adb.push([str(file.path) for file in batch.files], dest)
                success = True
                break
            except AdbError as exc:
                log(f"  Batch {index} failed (attempt {attempt}): {exc}")
                time.sleep(3)
                adb.wait_for_device()

        if success:
            done_files += len(batch.files)
            done_bytes += batch.size
        else:
            failed.append(batch)

        if index % 5 == 0 or index == len(batches):
            elapsed = max(time.time() - started, 0.001)
            speed = done_bytes / elapsed
            remaining = (total_bytes - done_bytes) / speed / 60 if speed else 0
            log(
                f"  {done_bytes / 1e9:.2f}/{total_bytes / 1e9:.1f} GB | "
                f"{speed / 1e6:.1f} MB/s | {done_files}/{total_files} files | "
                f"ETA {remaining:.0f} min"
            )

    return done_files, done_bytes, failed


def run(args: argparse.Namespace, adb: Adb | None = None) -> int:
    adb = adb or Adb()
    source = Path(os.path.expanduser(args.source))
    if not source.is_dir():
        log(f"Source directory not found: {source}")
        return 2

    adb.require_device()
    remote = args.remote or adb.detect_external_storage()
    log(f"Source: {source}")
    log(f"Target: {remote}")

    log("Reading SD card ...")
    remote_sizes = adb.list_files(remote)
    log(f"SD card: {len(remote_sizes)} files, {sum(remote_sizes.values()) / 1e9:.2f} GB")

    local_entries = scan_local(source)
    log(f"Local: {len(local_entries)} files, {total_size(local_entries) / 1e9:.2f} GB")

    missing = missing_files(local_entries, remote_sizes)
    missing_bytes = total_size(missing)
    log(
        f"Up to date: {len(local_entries) - len(missing)} | "
        f"to transfer: {len(missing)} files / {missing_bytes / 1e9:.2f} GB"
    )

    if not missing:
        log("Everything is in sync.")
        return 0

    if args.dry_run:
        for entry in missing[:40]:
            log(f"  {entry.size / 1e6:9.2f} MB  {entry.rel}")
        if len(missing) > 40:
            log(f"  ... and {len(missing) - 40} more")
        log("Dry run: nothing was written.")
        return 0

    free = adb.free_space(remote)
    log("")
    log("=== Target check ===")
    log(f"  Device:      {adb.device_label() or 'unknown'}")
    log(f"  Target:      {remote}")
    log(f"  Free space:  {'%.1f GB' % (free / 1e9) if free is not None else 'unknown'}")
    log(f"  To write:    {len(missing)} files / {missing_bytes / 1e9:.2f} GB")
    log("  Note:        existing files with the same size are left untouched.")

    if free is not None and missing_bytes > free:
        log(f"Aborted: {missing_bytes / 1e9:.1f} GB required, {free / 1e9:.1f} GB available.")
        return 3

    if not confirm("\nWrite to this target? [yes/no] ", auto_yes=args.yes):
        log("Aborted. Nothing was written.")
        return 0

    need_dirs = sorted(
        {os.path.dirname(entry.rel) for entry in missing if os.path.dirname(entry.rel)},
        key=lambda path: (path.count("/"), path),
    )
    existing_dirs = adb.list_dirs(remote)
    new_dirs = [directory for directory in need_dirs if directory not in existing_dirs]
    log(f"Creating {len(new_dirs)} directories ...")
    if new_dirs:
        adb.make_dirs(remote, new_dirs)

    batches = plan_batches(
        missing,
        max_files=args.batch_files,
        max_bytes=args.batch_mb * 1024 * 1024,
    )
    log(f"Starting upload: {len(batches)} batches")

    done_files, done_bytes, failed = upload(adb, remote, batches, missing_bytes, len(missing))
    log(f"Transferred: {done_files}/{len(missing)} files, {done_bytes / 1e9:.1f} GB")
    if failed:
        log(f"Failed batches: {len(failed)}. Run the command again to retry them.")

    log("Verifying ...")
    remote_after = adb.list_files(remote)
    still_missing = [entry for entry in local_entries if remote_after.get(entry.rel) != entry.size]
    log(
        f"Remaining: {len(still_missing)} files / "
        f"{total_size(still_missing) / 1e9:.2f} GB"
    )
    return 0 if not still_missing else 1


def main(argv: Sequence[str] | None = None) -> int:
    configure_logging()
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return run(args)
    except AdbError as exc:
        log(str(exc))
        return 2
    except KeyboardInterrupt:
        log("Cancelled by user.")
        return 130


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
