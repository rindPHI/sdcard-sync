# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Dominic Steinhöfel
from pathlib import Path

from sdcard_sync.sync import (
    FileEntry,
    missing_files,
    plan_batches,
    scan_local,
    total_size,
)


def _entry(rel: str, size: int) -> FileEntry:
    return FileEntry(rel=rel, size=size, path=Path("/lokal") / rel)


def test_scan_local_findet_verschachtelte_dateien_und_ignoriert_junk(tmp_path):
    (tmp_path / "DCIM" / "Camera").mkdir(parents=True)
    (tmp_path / "DCIM" / "Camera" / "foto.jpg").write_bytes(b"12345")
    (tmp_path / "notiz.txt").write_bytes(b"abc")
    (tmp_path / ".DS_Store").write_bytes(b"x")
    (tmp_path / "DCIM" / ".DS_Store").write_bytes(b"x")

    entries = scan_local(tmp_path)

    assert [entry.rel for entry in entries] == ["DCIM/Camera/foto.jpg", "notiz.txt"]
    assert total_size(entries) == 8
    assert entries[0].path == tmp_path / "DCIM" / "Camera" / "foto.jpg"


def test_missing_files_erkennt_fehlende_und_abweichende_dateien():
    local = [_entry("a.jpg", 10), _entry("b.jpg", 20), _entry("c.jpg", 30)]
    remote = {"a.jpg": 10, "b.jpg": 99}

    assert [entry.rel for entry in missing_files(local, remote)] == ["b.jpg", "c.jpg"]


def test_missing_files_ist_bei_gleichstand_leer():
    local = [_entry("a.jpg", 10)]
    assert missing_files(local, {"a.jpg": 10}) == []


def test_plan_batches_gruppiert_nach_zielordner():
    entries = [
        _entry("B/2.jpg", 10),
        _entry("A/1.jpg", 10),
        _entry("A/3.jpg", 10),
    ]

    batches = plan_batches(entries, max_files=10, max_bytes=10_000)

    assert [batch.dest for batch in batches] == ["A", "B"]
    assert [file.rel for file in batches[0].files] == ["A/1.jpg", "A/3.jpg"]


def test_plan_batches_beachtet_dateianzahl():
    entries = [_entry("A/f{}.jpg".format(i), 1) for i in range(5)]

    batches = plan_batches(entries, max_files=2, max_bytes=1000)

    assert [len(batch.files) for batch in batches] == [2, 2, 1]


def test_plan_batches_beachtet_groesse():
    entries = [_entry("A/gross.jpg", 600), _entry("A/klein.jpg", 100)]

    batches = plan_batches(entries, max_files=10, max_bytes=1000)

    assert [len(batch.files) for batch in batches] == [2]


def test_plan_batches_zerlegt_bei_zu_grossem_paket():
    entries = [_entry("A/1.jpg", 600), _entry("A/2.jpg", 600)]

    batches = plan_batches(entries, max_files=10, max_bytes=1000)

    assert [batch.size for batch in batches] == [600, 600]
