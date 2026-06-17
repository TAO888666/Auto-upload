import sqlite3
import tempfile
import unittest
from pathlib import Path
from queue import Queue
from unittest.mock import AsyncMock, patch

import sau_backend


def _create_user_info_table(db_path: Path) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE user_info (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type INTEGER NOT NULL,
                filePath TEXT NOT NULL,
                userName TEXT NOT NULL,
                status INTEGER DEFAULT 0,
                avatarUrl TEXT
            )
            """
        )
        conn.commit()


class SauBackendLoginBridgeTests(unittest.TestCase):
    def setUp(self):
        sau_backend.app.config["TESTING"] = True
        self.client = sau_backend.app.test_client()

    def test_run_async_function_uses_login_bridge(self):
        status_queue = Queue()

        with patch("sau_backend.run_login_flow", new=AsyncMock(), create=True) as mock_run, patch(
            "sau_backend.douyin_cookie_gen",
            new=AsyncMock(return_value=None),
            create=True,
        ):
            sau_backend.run_async_function("3", "千聊", status_queue)

        mock_run.assert_awaited_once_with("3", "千聊", status_queue)

    def test_sse_stream_stops_after_terminal_message(self):
        status_queue = Queue()
        status_queue.put("data:image/png;base64,qrpayload")
        status_queue.put("200")

        stream = sau_backend.sse_stream(status_queue)

        self.assertEqual(next(stream), "data: data:image/png;base64,qrpayload\n\n")
        self.assertEqual(next(stream), "data: 200\n\n")
        with patch("sau_backend.time.sleep", side_effect=AssertionError("stream should stop after terminal status")):
            with self.assertRaises(StopIteration):
                next(stream)

    def test_login_start_uses_browser_login_session_manager(self):
        payload = {"type": "3", "id": "千聊开课平台"}

        with patch(
            "sau_backend.start_browser_login_session",
            return_value={"started": True, "message": "browser opened"},
            create=True,
        ) as mock_start:
            response = self.client.post("/login/start", json=payload)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["code"], 200)
        mock_start.assert_called_once_with("3", "千聊开课平台")

    def test_login_confirm_uses_browser_login_session_manager(self):
        payload = {"type": "3", "id": "千聊开课平台"}

        with patch(
            "sau_backend.confirm_browser_login_session",
            return_value={"confirmed": True, "message": "登录成功"},
            create=True,
        ) as mock_confirm:
            response = self.client.post("/login/confirm", json=payload)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["code"], 200)
        self.assertTrue(response.get_json()["data"]["confirmed"])
        mock_confirm.assert_called_once_with("3", "千聊开课平台")

    def test_open_account_browser_uses_cookie_runtime_session_manager(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
            base_dir = Path(tmp_dir)
            (base_dir / "db").mkdir()
            (base_dir / "cookiesFile").mkdir()
            db_path = base_dir / "db" / "database.db"
            _create_user_info_table(db_path)

            with sqlite3.connect(db_path) as conn:
                conn.execute(
                    """
                    INSERT INTO user_info (id, type, filePath, userName, status, avatarUrl)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (1, 3, "open-account.json", "千聊官号", 1, None),
                )
                conn.commit()

            with patch.object(sau_backend, "BASE_DIR", base_dir), patch(
                "sau_backend.start_account_browser_session",
                return_value={"started": True, "message": "browser opened"},
                create=True,
            ) as mock_open:
                response = self.client.post("/account/open", json={"id": 1})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["code"], 200)
        mock_open.assert_called_once_with(
            1,
            "3",
            "千聊官号",
            base_dir / "cookiesFile" / "open-account.json",
        )


if __name__ == "__main__":
    unittest.main()
