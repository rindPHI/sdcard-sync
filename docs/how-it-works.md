# How it works

## Overview

```
┌──────────────┐    adb shell find/stat     ┌────────────────┐
│ local folder │ ─────────────────────────▶ │ Android device │
│   (source)   │                            │  /storage/…    │
│              │ ◀───────────────────────── │  (SD card)     │
└──────────────┘        adb push            └────────────────┘
```

## Device and target

`adb devices` has to report one device in state `device`. Unless `--remote`
is given, the target is derived from `ls /storage`: every entry other than
`emulated` and `self` is an external volume, usually `/storage/XXXX-XXXX`
with the volume UUID.

Internal storage (`/storage/emulated/0`) is never selected automatically,
because the tool is meant for the SD card.

## Reading the target

One `find` call runs on the device:

```sh
cd /storage/XXXX-XXXX && find . -type f -exec stat -c '%s %n' {} +
```

Each line contains the size and the relative path. `-exec … +` passes many
files to a single `stat` process, which keeps the call fast with tens of
thousands of files (seconds rather than minutes).

The result is a dictionary of relative path to size in bytes.

## Reading the source

`os.walk` traverses the source directory. The following are skipped:

- `.DS_Store` (macOS metadata)
- `.Trashes` (trash leftovers)
- symbolic links, which would otherwise be followed twice or point outside
  the tree
- files that cannot be read, for example because of permissions

Each file becomes a `FileEntry(rel, size, path)`.

## Computing the difference

A file is transferred when `remote.get(rel) != local.size`, which covers two
cases: the file does not exist on the target, or it exists with a different
size.

Timestamps are not compared. Android sets `dateAdded` when it writes a file,
and neither MTP nor adb preserve `mtime` reliably.

## Batch planning

Every `adb push` call has process and protocol overhead. Files are grouped by
target directory and then split into batches of at most 120 files and 2 GB.
Both limits can be changed with `--batch-files` and `--batch-mb`. A single
large file becomes its own batch.

## Transfer

Missing directories are created first with `mkdir -p`, up to 60 directories
per adb call.

Each batch is then sent with `adb push file1 file2 … target/`. A failed call
is retried up to three times with `adb wait-for-device` in between. A batch
that still fails does not stop the run; it is counted at the end and is part
of the difference again on the next start.

## Verification

After the upload the target listing is read again and compared with the
source. The run prints what is left:

```
Remaining: 0 files / 0.00 GB
```

This confirms completeness without hashing more than 100 GB.

## No stored state

There is no database and no list of completed files. The state is always the
current file listing on both sides. That makes the tool safe to interrupt at
any point: a restart recomputes the difference from scratch.

## Limits of the comparison

Path and size are a trade-off between speed and certainty. Two cases are not
detected:

- same path, same size, different content
- renames; the file is copied under the new name and the old copy remains

For an integrity check of a specific file:

```bash
md5 -q local/photo.jpg
adb shell md5sum /storage/XXXX-XXXX/path/photo.jpg
```
