# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Dominic Steinhöfel
"""Dünne Hülle um die adb-Kommandozeile.

Die Klasse :class:`Adb` kapselt alle Aufrufe des Android Debug Bridge, damit
der Rest des Programms ohne ``subprocess``-Details arbeiten kann.
"""

from __future__ import annotations

import shlex
import subprocess

NO_DEVICE_HINT = (
    "Kein Android-Gerät gefunden.\n"
    "  1. Handy entsperren\n"
    "  2. USB-Modus 'Dateien übertragen' wählen\n"
    "  3. USB-Debugging aktivieren (Entwickleroptionen)\n"
    "  4. 'USB-Debugging zulassen?' am Handy bestätigen\n"
    "Danach: adb devices"
)


class AdbError(RuntimeError):
    """Fehler bei der Kommunikation mit adb oder dem Gerät."""


class Adb:
    """Kapselt adb-Aufrufe für ein einzelnes Gerät."""

    def __init__(self, executable: str = "adb", default_timeout: int = 7200) -> None:
        self.executable = executable
        self.default_timeout = default_timeout

    def run(
        self,
        *args: str,
        timeout: int | None = None,
        check: bool = True,
    ) -> subprocess.CompletedProcess:
        cmd = [self.executable, *args]
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout or self.default_timeout,
            )
        except FileNotFoundError as exc:
            raise AdbError(
                "adb nicht gefunden. Installation: brew install --cask android-platform-tools"
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise AdbError(f"adb {' '.join(args[:2])}: Zeitüberschreitung") from exc

        if check and proc.returncode != 0:
            message = proc.stderr.strip() or proc.stdout.strip()
            raise AdbError(f"adb {' '.join(args[:2])} fehlgeschlagen: {message}")
        return proc

    def require_device(self) -> None:
        """Bricht mit verständlicher Meldung ab, wenn kein Gerät bereit ist."""
        output = self.run("devices", check=False).stdout
        if "\tdevice" not in output:
            raise AdbError(NO_DEVICE_HINT)

    def device_label(self) -> str:
        """Menschenlesbare Gerätebezeichnung, z. B. ``Fairphone FP5``."""
        parts = self.run(
            "shell", "getprop ro.product.manufacturer; getprop ro.product.model", check=False
        ).stdout.splitlines()
        return " ".join(part.strip() for part in parts if part.strip())

    def detect_external_storage(self) -> str:
        """Ermittelt den Einhängepunkt der externen SD-Karte."""
        names = self.run("shell", "ls /storage").stdout.split()
        for name in names:
            if name not in ("emulated", "self"):
                return "/storage/" + name
        raise AdbError("Keine echte SD-Karte gefunden (nur interner Speicher).")

    def free_space(self, remote_path: str) -> int | None:
        """Freier Speicher in Bytes, ``None`` wenn nicht ermittelbar."""
        proc = self.run("shell", f"df -k {shlex.quote(remote_path)} | tail -1", check=False)
        fields = proc.stdout.split()
        try:
            return int(fields[3]) * 1024
        except (IndexError, ValueError):
            return None

    def list_files(self, remote_path: str) -> dict[str, int]:
        """Alle Dateien unterhalb von *remote_path* als ``{relativer Pfad: Größe}``."""
        cmd = (
            f"cd {shlex.quote(remote_path)} && "
            f"find . -type f -exec stat -c '%s %n' {{}} +"
        )
        proc = self.run("shell", cmd, timeout=1800)
        files: dict[str, int] = {}
        for line in proc.stdout.splitlines():
            size, separator, name = line.partition(" ")
            if not separator or not size.isdigit():
                continue
            if name.startswith("./"):
                name = name[2:]
            files[name] = int(size)
        return files

    def list_dirs(self, remote_path: str) -> set[str]:
        """Alle Ordner unterhalb von *remote_path* (relativ)."""
        proc = self.run("shell", f"cd {shlex.quote(remote_path)} && find . -type d", timeout=1800)
        dirs: set[str] = set()
        for line in proc.stdout.splitlines():
            line = line.strip()
            if line.startswith("./"):
                line = line[2:]
            if line and line != ".":
                dirs.add(line)
        return dirs

    def make_dirs(self, remote_path: str, relative_dirs: list[str], chunk_size: int = 60) -> None:
        """Legt fehlende Ordner an (gebündelt, um adb-Aufrufe zu sparen)."""
        for start in range(0, len(relative_dirs), chunk_size):
            chunk = relative_dirs[start : start + chunk_size]
            command = " && ".join(
                f"mkdir -p {shlex.quote(remote_path.rstrip('/') + '/' + rel)}" for rel in chunk
            )
            self.run("shell", command, timeout=600)

    def push(self, local_paths: list[str], remote_dir: str, timeout: int = 7200) -> None:
        """Kopiert Dateien in einen Ordner auf dem Gerät."""
        self.run("push", *local_paths, remote_dir.rstrip("/") + "/", timeout=timeout)

    def wait_for_device(self) -> None:
        self.run("wait-for-device", timeout=120, check=False)

    def md5(self, remote_file: str) -> str:
        proc = self.run("shell", f"md5sum {shlex.quote(remote_file)}", check=False)
        return proc.stdout.split()[0] if proc.stdout.strip() else ""
