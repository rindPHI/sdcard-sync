# sdcard-sync

Synchronizes a local directory, for example a phone backup, with the SD card
in an Android device. The transfer runs over `adb`.

The tool compares every file by relative path and size, creates missing
directories, and copies only what differs. A second run transfers new or
changed files and leaves everything else alone.

```
=== Target check ===
  Device:      Fairphone FP5
  Target:      /storage/7EDF-B83A
  Free space:  349.2 GB
  To write:    42 files / 3.15 GB
  Note:        existing files with the same size are left untouched.

Write to this target? [yes/no]
```

## Why adb instead of MTP

MTP on macOS was slow and unstable for this workload. In a test with 16,857
files and 135.6 GB, OpenMTP/libmtp reached about 2.3 MB/s, which projected to
roughly 15 hours. An interrupted transfer also left the MTP session stuck
until the phone was unplugged and reconnected.

`adb push` on the same device reached 36.8 MB/s for large files and 13.5 MB/s
across the full set, finishing in 2 h 48 min. The details are in
[docs/decisions.md](docs/decisions.md).

## Requirements

- Python 3.9 or newer (standard library only)
- `adb` from the Android Platform Tools
- USB debugging enabled on the phone
- A USB cable

Install `adb`:

```bash
brew install --cask android-platform-tools
```

Enable USB debugging on the phone:

1. Settings → About phone → tap "Build number" seven times
2. Settings → System → Developer options → enable "USB debugging"
3. Connect the cable and choose "File transfer" as the USB mode
4. Confirm "Allow USB debugging?" on the phone

Check the connection:

```bash
adb devices
# 208cb67d    device
```

## Installation

### Running from the project

```bash
cd ~/PycharmProjects/sdcard-sync
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/sdcard-sync --help
```

### Running through the wrapper

The repository contains `bin/sdcard-sync`, which runs the package from the
checkout without installing it:

```bash
~/PycharmProjects/sdcard-sync/bin/sdcard-sync --help
```

To make the command available everywhere, link it into a directory on your
`PATH`:

```bash
ln -sf ~/PycharmProjects/sdcard-sync/bin/sdcard-sync ~/bin/sdcard-sync
```

The wrapper uses `.venv/bin/python` when the virtual environment exists and
falls back to `python3` otherwise.

## Usage

`--source` is required. There is no default directory, because a hardcoded
path can point at the wrong backup after a while.

```bash
# Target is detected automatically, then confirmed
sdcard-sync --source "/Users/me/Pictures/2026-10-23 SD Card Backup"

# Show what would be transferred
sdcard-sync --source "…" --dry-run

# Pin the target explicitly (confirmation still applies)
sdcard-sync --source "…" --remote /storage/7EDF-B83A

# Skip confirmation for automation
sdcard-sync --source "…" --yes
```

### Options

| Option | Description |
|---|---|
| `--source PATH` | Source directory (required) |
| `--remote PATH` | Target path; otherwise the SD card is detected |
| `--dry-run` | Print the difference without writing |
| `--yes` | Skip the confirmation prompt |
| `--batch-files N` | Maximum files per `adb push` call (default: 120) |
| `--batch-mb N` | Maximum batch size in MB (default: 2048) |

### Run sequence

1. Check that `adb devices` reports a ready device
2. Resolve the target, either from `--remote` or from `/storage`
3. Read the SD card: relative paths and file sizes
4. Scan the source directory
5. Compute the difference
6. Print device, target, free space and transfer volume
7. Wait for confirmation
8. Create missing directories and push the files in batches
9. Read the card again and report what is left

## Safety behaviour

The tool never deletes files. Entries that exist only on the SD card stay
where they are.

A file is overwritten only when the path exists with a different size. Files
with matching size are skipped.

If the target does not have enough free space, the run stops before the first
write. Without an explicit `yes` or `--yes`, nothing is written at all.

There is no state file on disk. After an interruption or a disconnected
cable, run the same command again and the difference is recalculated from the
actual file listings.

## Log

Each run also writes to:

```
~/Library/Logs/sdcard-sync.log
```

## Project layout

```
sdcard-sync/
├── bin/
│   └── sdcard-sync          # wrapper, no installation required
├── docs/
│   ├── decisions.md         # adb versus MTP, design choices
│   ├── how-it-works.md      # scan, diff, batching, verification
│   └── troubleshooting.md   # common errors and fixes
├── src/sdcard_sync/
│   ├── __init__.py
│   ├── __main__.py          # python -m sdcard_sync
│   ├── adb.py               # adb command wrapper
│   ├── cli.py               # arguments, confirmation, orchestration
│   └── sync.py              # scan, diff, batch planning (no I/O)
├── tests/
│   ├── test_cli.py
│   └── test_sync.py
├── pyproject.toml
└── README.md
```

## Tests

```bash
cd ~/PycharmProjects/sdcard-sync
.venv/bin/python -m pytest
```

The tests cover scanning, the diff, batch planning and the confirmation
logic. They do not need a connected device.

## Limitations

The comparison uses path and size. It does not hash file contents, which
keeps a 135 GB run within a reasonable time. Two files with the same name and
the same size but different content are treated as identical.

Renamed files are copied under their new name; the old copy stays on the
card.

`.DS_Store` and `.Trashes` are skipped.

Write access to `Android/data` depends on the Android version and may be
denied for some applications.

For a one-off integrity check of an individual file:

```bash
md5 -q local/photo.jpg
adb shell md5sum /storage/XXXX-XXXX/path/photo.jpg
```

## License

MIT, see [LICENSE](LICENSE). SPDX identifier: `MIT`. Copyright (c) 2026
Dominic Steinhöfel.
