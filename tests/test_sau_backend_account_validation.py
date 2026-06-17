import asyncio
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import sau_backend


def create_user_info_table(database_path: Path) -> None:
    with sqlite3.connect(database_path) as conn:
        conn.execute(
            """
            CREATE TABLE user_info (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type INTEGER,
                filePath TEXT,
                userName TEXT,
                status INTEGER,
                avatarUrl TEXT
            )
            """
        )
        conn.commit()


class SauBackendAccountValidationTests(unittest.TestCase):
    def setUp(self):
        sau_backend.app.config["TESTING"] = True
        self.client = sau_backend.app.test_client()

    def test_get_valid_accounts_validates_accounts_with_concurrency_limit(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
            base_dir = Path(tmp_dir)
            (base_dir / "db").mkdir()
            database_path = base_dir / "db" / "database.db"
            create_user_info_table(database_path)

            account_rows = [
                (index + 1, 2, f"account_{index + 1}.json", f"账号{index + 1}", 1)
                for index in range(25)
            ]
            with sqlite3.connect(database_path) as conn:
                conn.executemany(
                    """
                    INSERT INTO user_info (id, type, filePath, userName, status)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    account_rows,
                )
                conn.commit()

            active_count = 0
            max_concurrency = 0

            async def fake_fetch_account_profile(account_type, cookie_file, account_name=""):
                nonlocal active_count, max_concurrency
                active_count += 1
                max_concurrency = max(max_concurrency, active_count)
                await asyncio.sleep(0.05)
                active_count -= 1
                return {"name": account_name, "avatarUrl": None, "isValid": True}

            with patch.object(sau_backend, "BASE_DIR", base_dir), patch(
                "sau_backend.fetch_account_profile_from_cookie",
                side_effect=fake_fetch_account_profile,
            ):
                response = self.client.get("/getValidAccounts")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["code"], 200)
        self.assertEqual(len(payload["data"]), 25)
        self.assertEqual([row[0] for row in payload["data"]], [row[0] for row in account_rows])
        self.assertEqual(max_concurrency, sau_backend.ACCOUNT_VALIDATION_CONCURRENCY)

    def test_start_account_validation_exposes_incremental_progress(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
            base_dir = Path(tmp_dir)
            (base_dir / "db").mkdir()
            database_path = base_dir / "db" / "database.db"
            create_user_info_table(database_path)

            account_rows = [
                (index + 1, 2, f"account_{index + 1}.json", f"账号{index + 1}", 1)
                for index in range(25)
            ]
            with sqlite3.connect(database_path) as conn:
                conn.executemany(
                    """
                    INSERT INTO user_info (id, type, filePath, userName, status)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    account_rows,
                )
                conn.commit()

            async def fake_fetch_account_profile(account_type, cookie_file, account_name=""):
                account_id = int(Path(cookie_file).stem.split("_")[-1])
                await asyncio.sleep(0.02 if account_id <= 20 else 0.12)
                return {"name": account_name, "avatarUrl": None, "isValid": account_id % 2 == 0}

            with patch.object(sau_backend, "BASE_DIR", base_dir), patch(
                "sau_backend.fetch_account_profile_from_cookie",
                side_effect=fake_fetch_account_profile,
            ):
                start_response = self.client.post("/startAccountValidation")
                self.assertEqual(start_response.status_code, 200)
                start_payload = start_response.get_json()
                self.assertEqual(start_payload["code"], 200)
                task_id = start_payload["data"]["taskId"]

                intermediate_snapshot = None
                deadline = time.time() + 2
                while time.time() < deadline:
                    snapshot_response = self.client.get(f"/getAccountValidationTask?taskId={task_id}")
                    self.assertEqual(snapshot_response.status_code, 200)
                    snapshot_payload = snapshot_response.get_json()
                    self.assertEqual(snapshot_payload["code"], 200)
                    snapshot = snapshot_payload["data"]
                    if 0 < snapshot["completed"] < snapshot["total"]:
                        intermediate_snapshot = snapshot
                        break
                    time.sleep(0.02)

                self.assertIsNotNone(intermediate_snapshot)
                self.assertTrue(any(item["phase"] == "finished" for item in intermediate_snapshot["items"]))
                self.assertTrue(any(item["phase"] in {"pending", "running"} for item in intermediate_snapshot["items"]))

                final_snapshot = None
                deadline = time.time() + 2
                while time.time() < deadline:
                    snapshot_response = self.client.get(f"/getAccountValidationTask?taskId={task_id}")
                    snapshot = snapshot_response.get_json()["data"]
                    if snapshot["status"] == "success":
                        final_snapshot = snapshot
                        break
                    time.sleep(0.02)

                self.assertIsNotNone(final_snapshot)
                self.assertEqual(final_snapshot["completed"], final_snapshot["total"])
                self.assertTrue(all(item["phase"] == "finished" for item in final_snapshot["items"]))
                self.assertEqual(final_snapshot["items"][0]["status"], 0)
                self.assertEqual(final_snapshot["items"][1]["status"], 1)

            with sqlite3.connect(database_path) as conn:
                statuses = dict(conn.execute("SELECT id, status FROM user_info").fetchall())

        self.assertEqual(statuses[1], 0)
        self.assertEqual(statuses[2], 1)

    def test_start_account_validation_can_target_specific_accounts(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
            base_dir = Path(tmp_dir)
            (base_dir / "db").mkdir()
            database_path = base_dir / "db" / "database.db"
            create_user_info_table(database_path)

            account_rows = [
                (1, 2, "account_1.json", "账号1", 1),
                (2, 2, "account_2.json", "账号2", 1),
                (3, 2, "account_3.json", "账号3", 1),
            ]
            with sqlite3.connect(database_path) as conn:
                conn.executemany(
                    """
                    INSERT INTO user_info (id, type, filePath, userName, status)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    account_rows,
                )
                conn.commit()

            validated_ids = []

            async def fake_fetch_account_profile(account_type, cookie_file, account_name=""):
                validated_ids.append(int(Path(cookie_file).stem.split("_")[-1]))
                await asyncio.sleep(0.02)
                return {"name": account_name, "avatarUrl": None, "isValid": False}

            with patch.object(sau_backend, "BASE_DIR", base_dir), patch(
                "sau_backend.fetch_account_profile_from_cookie",
                side_effect=fake_fetch_account_profile,
            ):
                start_response = self.client.post(
                    "/startAccountValidation",
                    json={"accountIds": [2]},
                )
                self.assertEqual(start_response.status_code, 200)
                task_id = start_response.get_json()["data"]["taskId"]

                deadline = time.time() + 2
                final_snapshot = None
                while time.time() < deadline:
                    snapshot_response = self.client.get(f"/getAccountValidationTask?taskId={task_id}")
                    snapshot = snapshot_response.get_json()["data"]
                    if snapshot["status"] == "success":
                        final_snapshot = snapshot
                        break
                    time.sleep(0.02)

            self.assertIsNotNone(final_snapshot)
            self.assertEqual(final_snapshot["total"], 1)
            self.assertEqual(final_snapshot["items"][0]["id"], 2)
            self.assertEqual(validated_ids, [2])

            with sqlite3.connect(database_path) as conn:
                statuses = dict(conn.execute("SELECT id, status FROM user_info").fetchall())

        self.assertEqual(statuses[1], 1)
        self.assertEqual(statuses[2], 0)
        self.assertEqual(statuses[3], 1)

    def test_account_validation_stream_exposes_avatar_updates(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
            base_dir = Path(tmp_dir)
            (base_dir / "db").mkdir()
            (base_dir / "cookiesFile").mkdir()
            database_path = base_dir / "db" / "database.db"
            create_user_info_table(database_path)

            account_rows = [
                (1, 3, "account_1.json", "抖音账号", 1, None),
            ]
            with sqlite3.connect(database_path) as conn:
                conn.executemany(
                    """
                    INSERT INTO user_info (id, type, filePath, userName, status, avatarUrl)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    account_rows,
                )
                conn.commit()

            async def fake_fetch_account_profile(account_type, cookie_file, account_name=""):
                await asyncio.sleep(0.01)
                return {
                    "name": account_name or "抖音账号",
                    "avatarUrl": "https://avatar.example/douyin.png",
                    "isValid": True,
                }

            with patch.object(sau_backend, "BASE_DIR", base_dir), patch(
                "sau_backend.fetch_account_profile_from_cookie",
                side_effect=fake_fetch_account_profile,
            ):
                start_response = self.client.post("/startAccountValidation")
                self.assertEqual(start_response.status_code, 200)
                task_id = start_response.get_json()["data"]["taskId"]

                response = self.client.get(f"/accountValidationTasks/{task_id}/stream")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.mimetype, "text/event-stream")
                payload = response.get_data(as_text=True)

            self.assertIn("event: task-snapshot", payload)
            self.assertIn("https://avatar.example/douyin.png", payload)

            with sqlite3.connect(database_path) as conn:
                avatar_url = conn.execute("SELECT avatarUrl FROM user_info WHERE id = 1").fetchone()[0]

        self.assertEqual(avatar_url, "https://avatar.example/douyin.png")


if __name__ == "__main__":
    unittest.main()
