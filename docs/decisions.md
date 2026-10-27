# Decisions

## adb instead of MTP

The starting point was a Fairphone 5 with a 512 GB SD card and a 135 GB
backup containing 16,857 files.

The first attempt used MTP through OpenMTP and libmtp. On macOS the session
was hard to open: `ptpcamerad` held the device, and an aborted transfer left
a stuck session (`LIBUSB_ERROR_TIMEOUT`) that only a replug cleared. Once a
transfer was running it reached 2.3 MB/s, which projected to about 15 hours.
Small files dominated the runtime because the protocol adds overhead per
file.

The second attempt used adb. Setup required enabling USB debugging and
confirming the key once. `adb push` reached 36.8 MB/s for large files and
13.5 MB/s across the full set including the small files. The complete run
took 2 h 48 min. Interruptions are harmless because every run recomputes the
difference from the file listings.

The one-time setup cost is repaid in the first run.

## Required source directory

The backup that triggered the tool was an ad-hoc copy. A hardcoded path would
be stale within weeks and could point at the wrong directory without anyone
noticing. `--source` is therefore mandatory.

## Confirmation before writing

Automatic target detection is convenient, but a wrongly detected mount point
would place data somewhere unexpected. Before the first write the tool shows
device, target path, free space and transfer volume, and asks for an explicit
confirmation. `--yes` exists for deliberate automation.

## Comparison by path and size

A full hash comparison was the alternative. With 135 GB over a USB 2.0
high-speed link it would have doubled or tripled the runtime without a
practical benefit for restoring a backup. Path and size detect the cases that
occur in practice: missing files, interrupted transfers and differing
versions. Individual files can still be checked with `md5sum`.

## No deletions

A mirror mode with deletions would be risky. An incomplete source directory
would remove data from the SD card. The tool only adds and overwrites; files
that exist only on the card are left alone.

## Batched calls instead of one call per file

Each `adb push` invocation has overhead. Batches of 120 files or 2 GB reduce
the number of calls while keeping a failed batch small enough to retry
quickly.
