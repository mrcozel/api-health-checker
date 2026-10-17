"""Back up monitoring files and restore only into an empty Docker volume."""

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile


MANIFEST = "backup-manifest.json"
FILES = {"health_history.csv", "health_report.json", "endpoint_state.json"}


def allowed(name):
    return name in FILES or re.fullmatch(r"health_checker\.log(?:\.[1-9][0-9]*)?", name) is not None


def digest(stream):
    value = hashlib.sha256()
    size = 0
    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
        value.update(chunk)
        size += len(chunk)
    return value.hexdigest(), size


def validate_archive(path):
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or MANIFEST not in names:
            raise ValueError("Archive has duplicate entries or no manifest.")
        if any(name != MANIFEST and not allowed(name) for name in names):
            raise ValueError("Archive contains an unexpected filename or path.")
        if archive.getinfo(MANIFEST).file_size > 1024 * 1024:
            raise ValueError("Manifest is too large.")
        manifest = json.loads(archive.read(MANIFEST))
        if manifest.get("format") != 1 or not isinstance(manifest.get("files"), dict):
            raise ValueError("Unsupported backup manifest.")
        if set(manifest["files"]) != set(names) - {MANIFEST} or "health_history.csv" not in names:
            raise ValueError("Manifest and archive file list do not match, or history is missing.")
        for name, expected in manifest["files"].items():
            if not isinstance(expected, dict):
                raise ValueError("Invalid manifest entry.")
            with archive.open(name) as file:
                checksum, size = digest(file)
            if checksum != expected.get("sha256") or size != expected.get("size"):
                raise ValueError(f"Checksum or size mismatch: {name}")
        with archive.open("health_history.csv") as file:
            import io
            reader = csv.DictReader(io.TextIOWrapper(file, encoding="utf-8-sig", newline=""))
            if not {"timestamp", "name", "url", "status"}.issubset(reader.fieldnames or []):
                raise ValueError("History CSV is missing required columns.")
            count = sum(1 for _ in reader)
        return {"files": len(manifest["files"]), "history_checks": count,
                "bytes": sum(item["size"] for item in manifest["files"].values())}


def worker_backup(root):
    paths = sorted(path for path in root.iterdir() if allowed(path.name))
    if not any(path.name == "health_history.csv" for path in paths):
        raise ValueError("No history CSV found; nothing to back up.")
    manifest = {"format": 1, "files": {}}
    with zipfile.ZipFile(sys.stdout.buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in paths:
            if path.is_symlink() or not path.is_file():
                raise ValueError(f"Expected a regular monitoring file: {path.name}")
            with path.open("rb") as file:
                checksum, size = digest(file)
            manifest["files"][path.name] = {"sha256": checksum, "size": size}
            archive.write(path, path.name)
        archive.writestr(MANIFEST, json.dumps(manifest))


def worker_restore(root, archive_path):
    validate_archive(archive_path)
    if any(root.iterdir()):
        raise ValueError("Restore destination is not empty; refusing to overwrite files.")
    with zipfile.ZipFile(archive_path) as archive:
        for name in archive.namelist():
            if name == MANIFEST:
                continue
            destination = root / name  # All names were allowlisted; never extract arbitrary paths.
            with archive.open(name) as source, destination.open("xb") as target:
                shutil.copyfileobj(source, target)
            os.chmod(destination, 0o640)
            os.chown(destination, 10001, 10001)
        os.chmod(root, 0o750)
        os.chown(root, 10001, 10001)


def docker(*args):
    result = subprocess.run(["docker", *args], check=True, capture_output=True, text=True)
    return result.stdout.strip()


def volume_exists(name):
    return name in docker("volume", "ls", "--format", "{{.Name}}").splitlines()


def check_users(volume, writing_only):
    identifiers = docker("ps", "-q", "--filter", f"volume={volume}").splitlines()
    for identifier in identifiers:
        container = json.loads(docker("inspect", identifier))[0]
        for mount in container["Mounts"]:
            if mount.get("Name") == volume and (not writing_only or mount.get("RW")):
                raise ValueError(f"Stop container {container['Name']} before proceeding.")


def helper_args(image, volume, readonly):
    script = Path(__file__).resolve()
    if "," in str(script):
        raise ValueError("Docker bind-mount paths cannot contain commas.")
    return ["docker", "run", "--rm", "--network", "none", "--read-only",
            "--security-opt", "no-new-privileges:true", "--cap-drop", "ALL",
            *([] if readonly else ["--user", "0:0", "--cap-add", "CHOWN", "--cap-add", "DAC_READ_SEARCH"]),
            "--mount", f"type=volume,src={volume},dst=/data" + (",readonly" if readonly else ""),
            "--mount", f"type=bind,src={script},dst=/volume_backup.py,readonly"]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["backup", "verify", "restore"])
    parser.add_argument("--volume", help="Exact Docker volume name; required for backup and restore")
    parser.add_argument("--archive", type=Path, required=True, help="Local ZIP archive path")
    parser.add_argument("--image", default="api-health-checker:local", help="Existing project image")
    args = parser.parse_args(argv)
    if args.action != "verify" and (not args.volume or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", args.volume)):
        parser.error("A valid --volume is required for backup/restore.")
    archive = args.archive.resolve()
    if args.action == "verify":
        print(json.dumps(validate_archive(archive), indent=2))
        return
    if args.action == "backup":
        if not volume_exists(args.volume):
            raise ValueError("Source volume does not exist.")
        check_users(args.volume, writing_only=True)
        if archive.exists():
            raise ValueError("Archive already exists; choose a new filename.")
        archive.parent.mkdir(parents=True, exist_ok=True)
        partial = None
        try:
            with tempfile.NamedTemporaryFile(dir=archive.parent, suffix=".partial", delete=False) as file:
                partial = Path(file.name)
                subprocess.run(helper_args(args.image, args.volume, True) +
                               [args.image, "python", "/volume_backup.py", "_backup"],
                               stdout=file, check=True)
            summary = validate_archive(partial)
            # Publish a complete verified archive atomically, without overwriting.
            os.link(partial, archive)
            print(f"Backup saved: {archive}")
            print(json.dumps(summary, indent=2))
        finally:
            if partial is not None:
                partial.unlink(missing_ok=True)
    else:
        summary = validate_archive(archive)
        if "," in str(archive):
            raise ValueError("Docker bind-mount paths cannot contain commas.")
        if not volume_exists(args.volume):
            docker("volume", "create", args.volume)
        check_users(args.volume, writing_only=False)
        subprocess.run(helper_args(args.image, args.volume, False) +
                       ["--mount", f"type=bind,src={archive},dst=/backup.zip,readonly",
                        args.image, "python", "/volume_backup.py", "_restore"], check=True)
        print(f"Restored into {args.volume}; files owned by UID/GID 10001.")
        print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    try:
        if sys.argv[1:] == ["_backup"]:
            worker_backup(Path("/data"))
        elif sys.argv[1:] == ["_restore"]:
            worker_restore(Path("/data"), Path("/backup.zip"))
        else:
            main()
    except (OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile,
            subprocess.CalledProcessError) as error:
        print(f"Backup/restore failed: {error}", file=sys.stderr)
        raise SystemExit(1)
