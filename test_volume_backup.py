import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from tools.volume_backup import MANIFEST, validate_archive, worker_restore


class TestVolumeBackup(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def archive(self, files=None, manifest_override=None):
        files = files or {"health_history.csv": b"timestamp,name,url,status\n2026-10-17T12:00:00,API,url,UP\n"}
        manifest = {"format": 1, "files": {name: {"sha256": hashlib.sha256(value).hexdigest(), "size": len(value)}
                                          for name, value in files.items()}}
        if manifest_override:
            manifest_override(manifest)
        path = self.root / "backup.zip"
        with zipfile.ZipFile(path, "w") as archive:
            for name, value in files.items():
                archive.writestr(name, value)
            archive.writestr(MANIFEST, json.dumps(manifest))
        return path

    def test_valid_backup_counts_checks_and_files(self):
        result = validate_archive(self.archive())
        self.assertEqual(result["history_checks"], 1)
        self.assertEqual(result["files"], 1)

    def test_changed_content_rejected(self):
        path = self.archive(manifest_override=lambda m: m["files"]["health_history.csv"].update(sha256="bad"))
        with self.assertRaisesRegex(ValueError, "Checksum"):
            validate_archive(path)

    def test_paths_and_credentials_rejected(self):
        for name in ["../health_history.csv", "/health_history.csv", ".env", "endpoints.json", ".smtp-password"]:
            with self.subTest(name=name):
                path = self.archive({name: b"not allowed"})
                with self.assertRaisesRegex(ValueError, "unexpected"):
                    validate_archive(path)

    def test_duplicate_entries_rejected(self):
        path = self.archive()
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            with zipfile.ZipFile(path, "a") as archive:
                archive.writestr("health_history.csv", b"duplicate")
        with self.assertRaisesRegex(ValueError, "duplicate"):
            validate_archive(path)

    def test_restore_refuses_nonempty_target_without_changing_it(self):
        target = self.root / "target"
        target.mkdir()
        original = target / "health_history.csv"
        original.write_bytes(b"existing data")
        with self.assertRaisesRegex(ValueError, "not empty"):
            worker_restore(target, self.archive())
        self.assertEqual(original.read_bytes(), b"existing data")

    def test_missing_history_and_bad_csv_headers_rejected(self):
        for files in [{"health_report.json": b"[]"}, {"health_history.csv": b"wrong,columns\n"}]:
            with self.subTest(files=list(files)), self.assertRaises(ValueError):
                validate_archive(self.archive(files))


if __name__ == "__main__":
    unittest.main()
