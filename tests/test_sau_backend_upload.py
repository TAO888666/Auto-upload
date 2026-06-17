import io
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sau_backend


def _create_file_records_table(db_path: Path) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE file_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                filesize REAL,
                upload_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                file_path TEXT
            )
            """
        )
        conn.commit()


class SauBackendUploadTests(unittest.TestCase):
    def setUp(self):
        sau_backend.app.config["TESTING"] = True
        self.client = sau_backend.app.test_client()

    def test_upload_save_creates_video_directory_when_missing(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
            base_dir = Path(tmp_dir)
            (base_dir / "db").mkdir()
            _create_file_records_table(base_dir / "db" / "database.db")

            with patch.object(sau_backend, "BASE_DIR", base_dir), patch(
                "sau_backend.uuid.uuid1",
                return_value="fixed-upload-id",
            ):
                response = self.client.post(
                    "/uploadSave",
                    data={"file": (io.BytesIO(b"demo"), "demo.mp4")},
                    content_type="multipart/form-data",
                )

            self.assertEqual(response.status_code, 200)
            payload = response.get_json()
            self.assertEqual(payload["code"], 200)
            self.assertTrue((base_dir / "videoFile" / "fixed-upload-id_demo.mp4").exists())

    def test_delete_all_files_removes_records_and_linked_files(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
            base_dir = Path(tmp_dir)
            database_path = base_dir / "db" / "database.db"
            video_dir = base_dir / "videoFile"
            (base_dir / "db").mkdir()
            video_dir.mkdir()
            _create_file_records_table(database_path)

            first_file = video_dir / "first_demo.mp4"
            second_file = video_dir / "second_demo.mp4"
            orphan_file = video_dir / "orphan.mp4"
            first_file.write_bytes(b"first")
            second_file.write_bytes(b"second")
            orphan_file.write_bytes(b"orphan")

            with sqlite3.connect(database_path) as conn:
                conn.executemany(
                    "INSERT INTO file_records (filename, filesize, file_path) VALUES (?, ?, ?)",
                    [
                        ("demo-a.mp4", 1.0, first_file.name),
                        ("demo-b.mp4", 2.0, second_file.name),
                    ],
                )
                conn.commit()

            with patch.object(sau_backend, "BASE_DIR", base_dir):
                response = self.client.post("/deleteAllFiles")

            self.assertEqual(response.status_code, 200)
            payload = response.get_json()
            self.assertEqual(payload["code"], 200)
            self.assertEqual(payload["data"]["deletedRecords"], 2)
            self.assertEqual(payload["data"]["deletedFiles"], 2)
            self.assertFalse(first_file.exists())
            self.assertFalse(second_file.exists())
            self.assertTrue(orphan_file.exists())

            with sqlite3.connect(database_path) as conn:
                remaining_count = conn.execute("SELECT COUNT(*) FROM file_records").fetchone()[0]
            self.assertEqual(remaining_count, 0)


if __name__ == "__main__":
    unittest.main()
