# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Dominic Steinhöfel
import pytest

from sdcard_sync.cli import build_parser, confirm


class _Tty:
    def isatty(self) -> bool:
        return True


class _NoTty:
    def isatty(self) -> bool:
        return False


def test_source_ist_pflicht():
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args([])

    args = parser.parse_args(["--source", "/tmp/irgendwas"])
    assert args.source == "/tmp/irgendwas"
    assert args.dry_run is False
    assert args.yes is False


@pytest.mark.parametrize("answer", ["ja", "j", "yes", "y", "JA"])
def test_confirm_akzeptiert_ja(monkeypatch, answer):
    monkeypatch.setattr("builtins.input", lambda _: answer)
    assert confirm("weiter? ", stream=_Tty()) is True


@pytest.mark.parametrize("answer", ["nein", "n", "no", ""])
def test_confirm_lehnt_ab(monkeypatch, answer):
    monkeypatch.setattr("builtins.input", lambda _: answer)
    assert confirm("weiter? ", stream=_Tty()) is False


def test_confirm_ohne_tty_verweigert():
    from sdcard_sync.adb import AdbError

    with pytest.raises(AdbError):
        confirm("weiter? ", stream=_NoTty())


def test_confirm_mit_auto_yes():
    assert confirm("weiter? ", auto_yes=True, stream=_NoTty()) is True
