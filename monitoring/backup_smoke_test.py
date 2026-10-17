"""CI-only backup/restore exercise using isolated disposable Docker volumes."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import uuid
import zipfile


def docker(*args):
    return subprocess.run(["docker", *args], check=True, capture_output=True, text=True).stdout.strip()


def main():
    suffix = uuid.uuid4().hex[:12]
    source = "api-monitor-backup-ci-" + suffix
    target = "api-monitor-restore-ci-" + suffix
    image = "api-health-checker:test"
    created = []
    try:
        docker("volume", "create", source)
        created.append(source)
        fixture = {"health_history.csv": "timestamp,name,url,status\n2026-10-17T12:00:00,API,url,FAIL\n2026-10-17T12:01:00,API,url,UP\n",
                   "health_report.json": '[{"name":"API","url":"url","status":"UP"}]',
                   "endpoint_state.json": '{"API":{"consecutive_failures":0}}',
                   "health_checker.log": "fixture log\n", "health_checker.log.1": "older log\n",
                   ".env": "EXCLUDED_SECRET=fixture-only", "endpoints.json": "[]"}
        script = "import json,pathlib; data=json.loads(input()); [(pathlib.Path('/data')/k).write_text(v) for k,v in data.items()]"
        subprocess.run(["docker", "run", "--rm", "-i", "--network", "none", "--user", "0:0",
                        "--mount", f"type=volume,src={source},dst=/data", image, "python", "-c", script],
                       input=json.dumps(fixture), text=True, check=True)
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "monitoring.zip"
            tool = [sys.executable, "tools/volume_backup.py"]
            subprocess.run(tool + ["backup", "--volume", source, "--archive", str(archive), "--image", image], check=True)
            subprocess.run(tool + ["verify", "--archive", str(archive)], check=True)
            created.append(target)
            subprocess.run(tool + ["restore", "--volume", target, "--archive", str(archive), "--image", image], check=True)
            second = Path(directory) / "restored.zip"
            subprocess.run(tool + ["backup", "--volume", target, "--archive", str(second), "--image", image], check=True)
            with zipfile.ZipFile(archive) as first, zipfile.ZipFile(second) as restored:
                original = {name: first.read(name) for name in first.namelist()}
                recovered = {name: restored.read(name) for name in restored.namelist()}
                assert original == recovered, "Restored file bytes or manifest differ"
                assert ".env" not in original and "endpoints.json" not in original
            rejected = subprocess.run(tool + ["restore", "--volume", target, "--archive", str(archive), "--image", image],
                                      capture_output=True, text=True)
            assert rejected.returncode != 0 and "not empty" in rejected.stderr
            print("PASS: restored all monitoring files byte-for-byte, excluded configuration, and refused an overwrite.")
    finally:
        for name in reversed(created):
            subprocess.run(["docker", "volume", "rm", name], check=False)


if __name__ == "__main__":
    main()
