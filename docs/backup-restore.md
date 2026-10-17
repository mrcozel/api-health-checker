# Monitoring volume backup and restore

This procedure covers the **Docker Compose monitoring-data volume**: CSV history,
latest report JSON, incident state JSON, and checker logs (including numbered
rotations). It does not back up Prometheus samples, Grafana's database,
Alertmanager state, Mailpit mail, Kubernetes PVCs, endpoint configuration or SMTP
credentials. Keep configuration and secrets separately in appropriate protected
storage. History and logs can contain sensitive URLs or errors; protect archives
and keep a copy off this computer. ZIP archives are not encrypted.

The repository tool uses only the Python standard library plus Docker. You need
Python 3.10+, a working Docker engine, and the existing project image
`api-health-checker:local` (`docker compose build` if it is missing).
Run commands from the repository folder. Backups are ignored by Git.

## 1. Identify the source volume

```powershell
docker volume ls --filter label=com.docker.compose.volume=monitoring-data
```

For the default project name, the volume is `api-health-checker_monitoring-data`.
If you set a custom Compose project name or restored-volume override, use that
deployment's actual volume name in every command below. The tool requires an
existing source volume and a history CSV; it does not silently create an empty
source when a name is misspelled.

## 2. Take a consistent backup

Choose a new filename, stop the writer, and back up. Run commands one at a time:

```powershell
$backup = "backups/monitoring-$(Get-Date -Format yyyyMMdd-HHmmss).zip"
docker compose stop checker
python tools/volume_backup.py backup --volume api-health-checker_monitoring-data --archive $backup
docker compose start checker
```

**Restart the checker even if the backup command fails.** The dashboard can remain
running with its read-only mount. The tool refuses a source volume used by any
running writable container, then mounts it read-only in an isolated helper.
Do not restart writers during the backup. This pauses checks briefly; an extended
backup can trigger monitoring-overdue alerts.

The archive contains a versioned manifest with SHA-256 checksums and sizes for
each file. The tool verifies it before publishing the final filename, refuses
existing archive names, and reports the retained CSV row count. Atomic publishing
requires a filesystem supporting hard links (such as NTFS or ext4); on failure no
existing backup is overwritten. Keep the printed filename for the restore test.

## 3. Verify the archive without Docker

```powershell
python tools/volume_backup.py verify --archive $backup
```

Verification checks allowed filenames, required history columns, file sizes and
checksums. It reports the number of files, historical checks and uncompressed
bytes. A malformed ZIP, unexpected path, duplicate entry or checksum mismatch is
rejected. Checksums detect accidental corruption; they do not authenticate an
archive against a malicious author. Restore only backups you trust.

## 4. Restore into a separate empty volume

Choose a new volume name for this test:

```powershell
python tools/volume_backup.py restore --volume api-health-checker-restored-test --archive $backup
```

The tool creates that volume if needed, refuses running container users, and
refuses a nonempty destination before writing. It revalidates the archive in the
helper and restores ownership to UID/GID 10001 for the project image. The helper
runs without network access and temporarily uses root with CHOWN and
DAC_READ_SEARCH capabilities, to initialize the new volume and read a protected
archive bind mount without making the archive world-readable. Your original volume is
not changed. If restore fails after writing begins, the incomplete destination is
not rolled back; use a new empty volume for the next attempt.

Read the restored history independently of the running stack:

```powershell
docker run --rm --network none --mount type=volume,src=api-health-checker-restored-test,dst=/data,readonly api-health-checker:local python /app/health_stats.py
docker run --rm --network none --mount type=volume,src=api-health-checker-restored-test,dst=/data,readonly api-health-checker:local python /app/incident_history.py
```

For a byte-level round-trip check, back up the restored volume and verify it:

```powershell
python tools/volume_backup.py backup --volume api-health-checker-restored-test --archive backups/restored-verification.zip
python tools/volume_backup.py verify --archive backups/restored-verification.zip
```

Both archives should report the same historical-check count. For stronger
verification, compare the per-file hashes in each `backup-manifest.json`; they
should match. Do not compare whole ZIP hashes because ZIP metadata can differ.
CI performs this full file-by-file comparison on isolated test data, checks that
configuration files are excluded, and verifies that a second restore refuses to
overwrite existing files. This is separate from testing your real deployment.

## 5. Optional recovery cutover

Use this only when you actually want the application to use the restored copy.
First finish the checks above, then stop the checker and switch only the checker
and dashboard to the restored volume:

```powershell
docker compose stop checker
$env:RESTORE_VOLUME = "api-health-checker-restored-test"
docker compose -f compose.yaml -f compose.restore.yaml up -d --no-deps --force-recreate checker dashboard
```

The override refers to an external existing volume. It does not delete the old
volume or recreate Alertmanager, so an existing Brevo SMTP configuration remains
running. Keep using the restore override when recreating checker/dashboard; plain
Compose uses the original volume. Set `RESTORE_VOLUME` again in a new terminal.
When intentionally updating the full SMTP-enabled stack, include all required
files: `-f compose.yaml -f compose.email.yaml -f compose.restore.yaml`.

Refresh the dashboard, confirm historical records are present, and confirm new
checks append to the restored history. Any observations collected after the backup
point in the original volume are not automatically merged into the restored copy.
Restoring a snapshot also restores old incident/notification state, so alert
behavior should be reviewed after recovery. Recovery time and possible data loss
depend on backup frequency and when the checker resumes.

Do not run `docker compose down --volumes` or remove the original volume as part
of a restore drill. Cleanup and retention of old archives/volumes are deliberate
separate operations; this tool never deletes Docker volumes.
