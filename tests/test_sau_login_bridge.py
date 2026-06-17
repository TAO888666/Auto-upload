import sqlite3
import tempfile
import unittest
from pathlib import Path
from queue import Queue
from unittest.mock import AsyncMock, patch

import sau_login_bridge


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


class SauLoginBridgeTests(unittest.IsolatedAsyncioTestCase):
    def test_browser_login_launchers_include_tencent(self):
        self.assertIn("2", sau_login_bridge.BROWSER_LOGIN_LAUNCHERS)

    async def test_run_login_flow_streams_qrcode_and_records_success(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
            base_dir = Path(tmp_dir)
            (base_dir / "db").mkdir()
            (base_dir / "cookiesFile").mkdir()
            _create_user_info_table(base_dir / "db" / "database.db")

            async def fake_login(account_file, qrcode_callback=None, headless=True):
                self.assertEqual(Path(account_file), base_dir / "cookiesFile" / "fixed-login-id.json")
                self.assertTrue(headless)
                await qrcode_callback(
                    {
                        "image_data_url": "data:image/png;base64,qrpayload",
                        "image_path": str(base_dir / "douyin_qr.png"),
                    }
                )
                Path(account_file).write_text("cookie", encoding="utf-8")
                return {
                    "success": True,
                    "status": "success",
                    "message": "ok",
                    "account_file": account_file,
                }

            status_queue = Queue()
            with patch.object(sau_login_bridge, "BASE_DIR", base_dir), patch(
                "sau_login_bridge.uuid.uuid1",
                return_value="fixed-login-id",
            ), patch(
                "sau_login_bridge.douyin_cookie_gen",
                new=AsyncMock(side_effect=fake_login),
            ), patch(
                "sau_login_bridge.fetch_account_profile_from_cookie",
                new=AsyncMock(
                    return_value={
                        "name": "千聊",
                        "avatarUrl": "https://avatar.example/login.png",
                        "isValid": True,
                    }
                ),
            ):
                await sau_login_bridge.run_login_flow("3", "千聊", status_queue)

            self.assertEqual(status_queue.get_nowait(), "data:image/png;base64,qrpayload")
            self.assertEqual(status_queue.get_nowait(), "200")

            with sqlite3.connect(base_dir / "db" / "database.db") as conn:
                row = conn.execute(
                    "SELECT type, filePath, userName, status, avatarUrl FROM user_info"
                ).fetchone()

            self.assertEqual(row, (3, "fixed-login-id.json", "千聊", 1, "https://avatar.example/login.png"))

    async def test_run_login_flow_pushes_failure_status_without_db_write(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
            base_dir = Path(tmp_dir)
            (base_dir / "db").mkdir()
            (base_dir / "cookiesFile").mkdir()
            _create_user_info_table(base_dir / "db" / "database.db")

            status_queue = Queue()
            with patch.object(sau_login_bridge, "BASE_DIR", base_dir), patch(
                "sau_login_bridge.uuid.uuid1",
                return_value="failed-login-id",
            ), patch(
                "sau_login_bridge.douyin_cookie_gen",
                new=AsyncMock(
                    return_value={
                        "success": False,
                        "status": "timeout",
                        "message": "timeout",
                        "account_file": str(base_dir / "cookiesFile" / "failed-login-id.json"),
                    }
                ),
            ):
                await sau_login_bridge.run_login_flow("3", "千聊", status_queue)

            self.assertEqual(status_queue.get_nowait(), "500")

            with sqlite3.connect(base_dir / "db" / "database.db") as conn:
                count = conn.execute("SELECT COUNT(*) FROM user_info").fetchone()[0]

            self.assertEqual(count, 0)

    def test_confirm_browser_login_session_saves_avatar(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
            base_dir = Path(tmp_dir)
            (base_dir / "db").mkdir()
            (base_dir / "cookiesFile").mkdir()
            _create_user_info_table(base_dir / "db" / "database.db")

            session = sau_login_bridge.BrowserLoginSession(
                platform_type="3",
                account_type=3,
                account_name="千聊",
                account_file=base_dir / "cookiesFile" / "browser-login-id.json",
                cookie_auth=AsyncMock(return_value=True),
            )
            session.loop = object()
            sau_login_bridge.BROWSER_LOGIN_SESSIONS[("3", "千聊")] = session

            class _FakeFuture:
                def __init__(self, value):
                    self._value = value

                def result(self, timeout=None):
                    return self._value

            fake_results = iter(
                [
                    {"confirmed": True, "account_file": str(session.account_file)},
                    "https://avatar.example/browser.png",
                ]
            )

            def fake_run_coroutine_threadsafe(coro, loop):
                try:
                    coro.close()
                except Exception:
                    pass
                return _FakeFuture(next(fake_results))

            with patch.object(sau_login_bridge, "BASE_DIR", base_dir), patch(
                "sau_login_bridge.asyncio.run_coroutine_threadsafe",
                side_effect=fake_run_coroutine_threadsafe,
            ), patch(
                "sau_login_bridge.close_browser_login_session",
                return_value={"closed": True},
            ):
                result = sau_login_bridge.confirm_browser_login_session("3", "千聊")

            self.assertTrue(result["confirmed"])
            with sqlite3.connect(base_dir / "db" / "database.db") as conn:
                row = conn.execute(
                    "SELECT type, filePath, userName, status, avatarUrl FROM user_info"
                ).fetchone()

            self.assertEqual(
                row,
                (3, "browser-login-id.json", "千聊", 1, "https://avatar.example/browser.png"),
            )


if __name__ == "__main__":
    unittest.main()
