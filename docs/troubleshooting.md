# Troubleshooting

## "No Android device found"

```
adb devices
```

| Output | Cause | Fix |
|---|---|---|
| empty | cable, USB mode or debugging | check the cable, choose "File transfer", enable USB debugging |
| `unauthorized` | the phone has not confirmed the key | unlock the phone and accept "Allow USB debugging?" |
| `offline` | the connection is stuck | unplug and replug, then `adb kill-server && adb start-server` |

A different USB port often helps. Ports on a monitor or dock are a common
source of trouble.

## "No external SD card found"

`adb shell ls /storage` shows only `emulated` and `self`. The card is missing
or not mounted. Check with:

```bash
adb shell sm list-volumes
adb shell ls /storage
```

Alternatively pass the target explicitly:

```bash
sdcard-sync --source "…" --remote /storage/XXXX-XXXX
```

## "Permission denied" while writing

Check the target path for typos and make sure it points at the removable
volume, not internal storage.

`Android/data` is restricted on Android 11 and newer for some applications.
Affected files are reported as failed batches and the rest of the run
continues.

Remounting the card on the phone (Settings → Storage) resolves some mount
problems.

## The transfer stops midway

Run the same command again:

```bash
sdcard-sync --source "…"
```

Only the difference is transferred. Files that were already copied are
skipped.

## The transfer is slow

Connect the phone directly to the Mac instead of through a hub or dock.

Large files run at roughly 35 MB/s. Many small files are much slower because
of the per-file protocol overhead.

Raising `--batch-files`, for example to 250, reduces the number of adb calls.

## "No interactive input available"

The program runs without a terminal, for example from a cron job. Either run
it interactively or confirm deliberately:

```bash
sdcard-sync --source "…" --yes
```

## "Remaining: N files" after a run

Failed batches are retried on the next start.

`Android/data` may fail permanently because of the permission restrictions
described above.

Check the log for details:

```bash
tail -n 50 ~/Library/Logs/sdcard-sync.log
```
