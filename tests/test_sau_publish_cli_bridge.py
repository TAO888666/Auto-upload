import sqlite3
import tempfile
import threading
import time
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock

import sau_publish_cli_bridge as bridge


def create_user_info_table(database_path: Path) -> None:
    with sqlite3.connect(database_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE user_info (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type INTEGER,
                filePath TEXT,
                userName TEXT,
                status INTEGER
            )
            """
        )
        conn.commit()


class SauPublishCliBridgeTests(unittest.TestCase):
    def test_prepare_account_cookie_for_cli_copies_legacy_cookie(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
            base_dir = Path(tmp_dir)
            legacy_dir = base_dir / "cookiesFile"
            runtime_dir = base_dir / "cookies"
            legacy_dir.mkdir()
            runtime_dir.mkdir()
            legacy_cookie = legacy_dir / "legacy_cookie.json"
            legacy_cookie.write_text('{"ok": true}', encoding="utf-8")

            account_name = bridge.prepare_account_cookie_for_cli(
                platform="douyin",
                legacy_account_path="legacy_cookie.json",
                base_dir=base_dir,
            )

            runtime_cookie = runtime_dir / "douyin_legacy_cookie.json"
            runtime_exists = runtime_cookie.exists()
            runtime_text = runtime_cookie.read_text(encoding="utf-8") if runtime_exists else ""

        self.assertEqual(account_name, "legacy_cookie")
        self.assertTrue(runtime_exists)
        self.assertEqual(runtime_text, '{"ok": true}')

    def test_prepare_account_cookie_for_cli_uses_database_username_for_uuid_cookie(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
            base_dir = Path(tmp_dir)
            legacy_dir = base_dir / "cookiesFile"
            runtime_dir = base_dir / "cookies"
            db_dir = base_dir / "db"
            legacy_dir.mkdir()
            runtime_dir.mkdir()
            db_dir.mkdir()

            legacy_cookie = legacy_dir / "f8ae30ec-4e88-11f1-84ba-b81ea4b8d7b8.json"
            legacy_cookie.write_text('{"ok": true}', encoding="utf-8")

            database_path = db_dir / "database.db"
            create_user_info_table(database_path)
            with sqlite3.connect(database_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO user_info (type, filePath, userName, status)
                    VALUES (?, ?, ?, ?)
                    """,
                    (1, legacy_cookie.name, "千聊", 1),
                )
                conn.commit()

            account_name = bridge.prepare_account_cookie_for_cli(
                platform="xiaohongshu",
                legacy_account_path=legacy_cookie.name,
                base_dir=base_dir,
            )

            runtime_cookie = runtime_dir / "xiaohongshu_千聊.json"
            runtime_exists = runtime_cookie.exists()
            runtime_text = runtime_cookie.read_text(encoding="utf-8") if runtime_exists else ""

        self.assertEqual(account_name, "千聊")
        self.assertTrue(runtime_exists)
        self.assertEqual(runtime_text, '{"ok": true}')

    def test_build_publish_commands_translates_legacy_single_platform_payload(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
            base_dir = Path(tmp_dir)
            (base_dir / "videoFile").mkdir()
            (base_dir / "cookiesFile").mkdir()
            (base_dir / "videoFile" / "video_a.mp4").write_bytes(b"a")
            (base_dir / "videoFile" / "video_b.mp4").write_bytes(b"b")
            (base_dir / "cookiesFile" / "acct_a.json").write_text("{}")
            (base_dir / "cookiesFile" / "acct_b.json").write_text("{}")

            payload = {
                "type": 3,
                "title": "测试标题",
                "tags": ["话题1", "话题2"],
                "fileList": ["video_a.mp4", "video_b.mp4"],
                "accountList": ["acct_a.json", "acct_b.json"],
                "enableTimer": 1,
                "videosPerDay": 2,
                "dailyTimes": ["10:00", "14:30"],
                "startDays": 1,
                "productLink": "https://example.com/item",
                "productTitle": "商品名",
            }

            commands = bridge.build_publish_commands(
                payload,
                base_dir=base_dir,
                now_provider=lambda: datetime(2026, 5, 13, 9, 0, 0),
            )

        self.assertEqual(len(commands), 4)
        self.assertEqual(
            commands[0],
            [
                "douyin",
                "upload-video",
                "--account",
                "acct_a",
                "--file",
                str(base_dir / "videoFile" / "video_a.mp4"),
                "--title",
                "测试标题",
                "--tags",
                "话题1,话题2",
                "--schedule",
                "2026-05-14 10:00",
                "--product-link",
                "https://example.com/item",
                "--product-title",
                "商品名",
            ],
        )
        self.assertEqual(commands[1][3], "acct_b")
        self.assertEqual(commands[2][commands[2].index("--schedule") + 1], "2026-05-14 14:30")

    def test_build_publish_commands_start_days_zero_publishes_first_work_immediately(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
            base_dir = Path(tmp_dir)
            (base_dir / "videoFile").mkdir()
            (base_dir / "cookiesFile").mkdir()
            (base_dir / "videoFile" / "video_a.mp4").write_bytes(b"a")
            (base_dir / "videoFile" / "video_b.mp4").write_bytes(b"b")
            (base_dir / "cookiesFile" / "acct_a.json").write_text("{}")

            payload = {
                "type": 3,
                "title": "立即开始",
                "fileList": ["video_a.mp4", "video_b.mp4"],
                "accountList": ["acct_a.json"],
                "enableTimer": 1,
                "videosPerDay": 1,
                "dailyTimes": ["09:00"],
                "startDays": 0,
            }

            commands = bridge.build_publish_commands(
                payload,
                base_dir=base_dir,
                now_provider=lambda: datetime(2026, 5, 13, 8, 0, 0),
            )

        self.assertEqual(len(commands), 2)
        self.assertNotIn("--schedule", commands[0])
        self.assertEqual(commands[1][commands[1].index("--schedule") + 1], "2026-05-14 09:00")

    def test_build_publish_commands_accepts_explicit_schedule_time(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
            base_dir = Path(tmp_dir)
            (base_dir / "videoFile").mkdir()
            (base_dir / "cookiesFile").mkdir()
            (base_dir / "videoFile" / "video_a.mp4").write_bytes(b"a")
            (base_dir / "cookiesFile" / "acct_a.json").write_text("{}")

            payload = {
                "type": 3,
                "title": "绝对时间发布",
                "fileList": ["video_a.mp4"],
                "accountList": ["acct_a.json"],
                "enableTimer": 1,
                "scheduleTime": "2026-05-20 21:30:00",
            }

            commands = bridge.build_publish_commands(payload, base_dir=base_dir)

        self.assertEqual(commands[0][commands[0].index("--schedule") + 1], "2026-05-20 21:30")

    def test_build_publish_commands_groups_accounts_by_platform_from_account_ids(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
            base_dir = Path(tmp_dir)
            (base_dir / "videoFile").mkdir()
            (base_dir / "cookiesFile").mkdir()
            (base_dir / "db").mkdir()
            (base_dir / "videoFile" / "video_a.mp4").write_bytes(b"a")
            (base_dir / "cookiesFile" / "xhs_uuid.json").write_text("{}")
            (base_dir / "cookiesFile" / "douyin_uuid.json").write_text("{}")

            database_path = base_dir / "db" / "database.db"
            create_user_info_table(database_path)
            with sqlite3.connect(database_path) as conn:
                cursor = conn.cursor()
                cursor.executemany(
                    """
                    INSERT INTO user_info (id, type, filePath, userName, status)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    [
                        (101, 1, "xhs_uuid.json", "小红书2", 1),
                        (202, 3, "douyin_uuid.json", "抖音A", 1),
                    ],
                )
                conn.commit()

            payload = {
                "title": "多平台标题",
                "fileList": ["video_a.mp4"],
                "accountIds": [101, 202],
                "accountList": ["xhs_uuid.json", "douyin_uuid.json"],
                "tags": ["混发"],
                "productLink": "https://example.com/item",
                "productTitle": "抖音商品",
                "enableTimer": 0,
            }

            commands = bridge.build_publish_commands(payload, base_dir=base_dir)

        self.assertEqual(commands, [
            [
                "xiaohongshu",
                "upload-video",
                "--account",
                "小红书2",
                "--file",
                str(base_dir / "videoFile" / "video_a.mp4"),
                "--title",
                "多平台标题",
                "--tags",
                "混发",
            ],
            [
                "douyin",
                "upload-video",
                "--account",
                "抖音A",
                "--file",
                str(base_dir / "videoFile" / "video_a.mp4"),
                "--title",
                "多平台标题",
                "--tags",
                "混发",
                "--product-link",
                "https://example.com/item",
                "--product-title",
                "抖音商品",
            ],
        ])

    def test_build_publish_commands_supports_weixin_video_publish(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
            base_dir = Path(tmp_dir)
            (base_dir / "videoFile").mkdir()
            (base_dir / "cookiesFile").mkdir()
            (base_dir / "videoFile" / "video_a.mp4").write_bytes(b"a")
            (base_dir / "cookiesFile" / "channel_account.json").write_text("{}")

            payload = {
                "type": 2,
                "title": "视频号标题",
                "tags": ["话题1", "话题2"],
                "fileList": ["video_a.mp4"],
                "accountList": ["channel_account.json"],
                "enableTimer": 0,
                "isDraft": True,
            }

            commands = bridge.build_publish_commands(payload, base_dir=base_dir)

        self.assertEqual(
            commands[0],
            [
                "weixin",
                "upload-video",
                "--account",
                "channel_account",
                "--file",
                str(base_dir / "videoFile" / "video_a.mp4"),
                "--title",
                "视频号标题",
                "--tags",
                "话题1,话题2",
                "--draft",
            ],
        )

    def test_build_publish_commands_appends_headed_flag_for_visible_publish(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
            base_dir = Path(tmp_dir)
            (base_dir / "videoFile").mkdir()
            (base_dir / "cookiesFile").mkdir()
            (base_dir / "videoFile" / "video_a.mp4").write_bytes(b"a")
            (base_dir / "cookiesFile" / "acct_a.json").write_text("{}")

            payload = {
                "type": 3,
                "title": "可见发布",
                "fileList": ["video_a.mp4"],
                "accountList": ["acct_a.json"],
                "enableTimer": 0,
                "headless": False,
            }

            commands = bridge.build_publish_commands(payload, base_dir=base_dir)

        self.assertIn("--headed", commands[0])
        self.assertNotIn("--headless", commands[0])

    def test_build_publish_commands_appends_douyin_self_declaration_flag(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
            base_dir = Path(tmp_dir)
            (base_dir / "videoFile").mkdir()
            (base_dir / "cookiesFile").mkdir()
            (base_dir / "videoFile" / "video_a.mp4").write_bytes(b"a")
            (base_dir / "videoFile" / "note_1.jpg").write_bytes(b"1")
            (base_dir / "cookiesFile" / "acct_a.json").write_text("{}")

            payload = {
                "type": 3,
                "title": "自主声明",
                "content": "图文正文",
                "works": [
                    {"kind": "video", "filePath": "video_a.mp4"},
                    {"kind": "note", "filePaths": ["note_1.jpg"]},
                ],
                "accountList": ["acct_a.json"],
                "enableTimer": 0,
                "douyinSelfDeclaration": True,
            }

            commands = bridge.build_publish_commands(payload, base_dir=base_dir)

        self.assertIn("--self-declaration", commands[0])
        self.assertIn("--self-declaration", commands[1])

    def test_build_publish_plan_returns_structured_publish_items(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
            base_dir = Path(tmp_dir)
            (base_dir / "videoFile").mkdir()
            (base_dir / "cookiesFile").mkdir()
            (base_dir / "videoFile" / "video_a.mp4").write_bytes(b"a")
            (base_dir / "cookiesFile" / "acct_a.json").write_text("{}")

            payload = {
                "type": 3,
                "title": "结构化计划",
                "fileList": ["video_a.mp4"],
                "accountList": ["acct_a.json"],
                "enableTimer": 0,
            }

            items = bridge.build_publish_plan(payload, base_dir=base_dir)

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["itemId"], "item-0")
        self.assertEqual(items[0]["platform"], "douyin")
        self.assertEqual(items[0]["accountName"], "acct_a")
        self.assertEqual(items[0]["mediaLabel"], "video_a.mp4")

    def test_run_publish_payload_reports_progress_events(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
            base_dir = Path(tmp_dir)
            (base_dir / "videoFile").mkdir()
            (base_dir / "cookiesFile").mkdir()
            (base_dir / "sau_cli.py").write_text("print('stub')", encoding="utf-8")
            (base_dir / "videoFile" / "video_a.mp4").write_bytes(b"a")
            (base_dir / "cookiesFile" / "acct_a.json").write_text("{}")

            payload = {
                "type": 3,
                "title": "进度事件",
                "fileList": ["video_a.mp4"],
                "accountList": ["acct_a.json"],
                "enableTimer": 0,
            }
            events = []

            result = bridge.run_publish_payload(
                payload,
                base_dir=base_dir,
                runner=Mock(return_value=Mock(returncode=0, stdout="ok", stderr="")),
                progress_callback=events.append,
            )

        self.assertEqual(result["executed"], 1)
        self.assertEqual(events[0]["type"], "plan-prepared")
        self.assertEqual(events[1]["type"], "item-started")
        self.assertEqual(events[2]["type"], "item-finished")

    def test_build_publish_commands_supports_mixed_video_and_note_works(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
            base_dir = Path(tmp_dir)
            (base_dir / "videoFile").mkdir()
            (base_dir / "cookiesFile").mkdir()
            (base_dir / "db").mkdir()

            (base_dir / "videoFile" / "video_a.mp4").write_bytes(b"a")
            (base_dir / "videoFile" / "note_1.jpg").write_bytes(b"1")
            (base_dir / "videoFile" / "note_2.png").write_bytes(b"2")
            (base_dir / "videoFile" / "note_3.jpeg").write_bytes(b"3")
            (base_dir / "cookiesFile" / "xhs_uuid.json").write_text("{}")
            (base_dir / "cookiesFile" / "douyin_uuid.json").write_text("{}")

            database_path = base_dir / "db" / "database.db"
            create_user_info_table(database_path)
            with sqlite3.connect(database_path) as conn:
                cursor = conn.cursor()
                cursor.executemany(
                    """
                    INSERT INTO user_info (id, type, filePath, userName, status)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    [
                        (101, 1, "xhs_uuid.json", "xhsA", 1),
                        (202, 3, "douyin_uuid.json", "douyinA", 1),
                    ],
                )
                conn.commit()

            payload = {
                "titles": ["video title", "note title"],
                "contents": ["video desc", "note body"],
                "tags": ["topic1", "topic2"],
                "works": [
                    {"kind": "video", "filePath": "video_a.mp4"},
                    {"kind": "note", "filePaths": ["note_1.jpg", "note_2.png", "note_3.jpeg"]},
                ],
                "accountIds": [101, 202],
                "accountList": ["xhs_uuid.json", "douyin_uuid.json"],
                "enableTimer": 0,
            }

            commands = bridge.build_publish_commands(payload, base_dir=base_dir)

        self.assertEqual(len(commands), 4)
        self.assertEqual(
            commands[0],
            [
                "xiaohongshu",
                "upload-video",
                "--account",
                "xhsA",
                "--file",
                str(base_dir / "videoFile" / "video_a.mp4"),
                "--title",
                "video title",
                "--desc",
                "video desc",
                "--tags",
                "topic1,topic2",
            ],
        )
        self.assertEqual(
            commands[1],
            [
                "douyin",
                "upload-video",
                "--account",
                "douyinA",
                "--file",
                str(base_dir / "videoFile" / "video_a.mp4"),
                "--title",
                "video title",
                "--desc",
                "video desc",
                "--tags",
                "topic1,topic2",
            ],
        )
        self.assertEqual(
            commands[2],
            [
                "xiaohongshu",
                "upload-note",
                "--account",
                "xhsA",
                "--images",
                str(base_dir / "videoFile" / "note_1.jpg"),
                str(base_dir / "videoFile" / "note_2.png"),
                str(base_dir / "videoFile" / "note_3.jpeg"),
                "--title",
                "note title",
                "--note",
                "note body",
                "--tags",
                "topic1,topic2",
            ],
        )
        self.assertEqual(
            commands[3],
            [
                "douyin",
                "upload-note",
                "--account",
                "douyinA",
                "--images",
                str(base_dir / "videoFile" / "note_1.jpg"),
                str(base_dir / "videoFile" / "note_2.png"),
                str(base_dir / "videoFile" / "note_3.jpeg"),
                "--title",
                "note title",
                "--note",
                "note body",
                "--tags",
                "topic1,topic2",
            ],
        )

    def test_build_publish_commands_rejects_note_works_for_weixin(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
            base_dir = Path(tmp_dir)
            (base_dir / "videoFile").mkdir()
            (base_dir / "cookiesFile").mkdir()
            (base_dir / "db").mkdir()

            (base_dir / "videoFile" / "note_1.jpg").write_bytes(b"1")
            (base_dir / "videoFile" / "note_2.png").write_bytes(b"2")
            (base_dir / "cookiesFile" / "weixin_uuid.json").write_text("{}")

            database_path = base_dir / "db" / "database.db"
            create_user_info_table(database_path)
            with sqlite3.connect(database_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO user_info (id, type, filePath, userName, status)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (301, 2, "weixin_uuid.json", "weixinA", 1),
                )
                conn.commit()

            payload = {
                "titles": ["note title"],
                "contents": ["note body"],
                "works": [
                    {"kind": "note", "filePaths": ["note_1.jpg", "note_2.png"]},
                ],
                "accountIds": [301],
                "accountList": ["weixin_uuid.json"],
                "enableTimer": 0,
            }

            with self.assertRaisesRegex(bridge.PublishBridgeError, "视频号目前不支持图文发布"):
                bridge.build_publish_commands(payload, base_dir=base_dir)

    def test_run_publish_payload_executes_each_command(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
            base_dir = Path(tmp_dir)
            (base_dir / "videoFile").mkdir()
            (base_dir / "cookiesFile").mkdir()
            (base_dir / "sau_cli.py").write_text("print('stub')", encoding="utf-8")
            (base_dir / "videoFile" / "video_a.mp4").write_bytes(b"a")
            (base_dir / "cookiesFile" / "acct_a.json").write_text("{}")
            payload = {
                "type": 1,
                "title": "测试标题",
                "tags": [],
                "fileList": ["video_a.mp4"],
                "accountList": ["acct_a.json"],
                "enableTimer": 0,
            }

            runner = Mock(return_value=Mock(returncode=0, stdout="ok", stderr=""))

            result = bridge.run_publish_payload(
                payload,
                base_dir=base_dir,
                now_provider=lambda: datetime(2026, 5, 13, 9, 0, 0),
                runner=runner,
            )

        self.assertEqual(result["executed"], 1)
        self.assertEqual(result["results"][0]["returncode"], 0)
        invoked_command = runner.call_args.kwargs["args"]
        self.assertEqual(invoked_command[1:4], [str(base_dir / "sau_cli.py"), "xiaohongshu", "upload-video"])

    def test_run_publish_payload_runs_accounts_concurrently_within_same_platform(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
            base_dir = Path(tmp_dir)
            (base_dir / "videoFile").mkdir()
            (base_dir / "cookiesFile").mkdir()
            (base_dir / "db").mkdir()
            (base_dir / "sau_cli.py").write_text("print('stub')", encoding="utf-8")
            (base_dir / "videoFile" / "video_a.mp4").write_bytes(b"a")
            database_path = base_dir / "db" / "database.db"
            create_user_info_table(database_path)

            account_rows = []
            for index in range(4):
                cookie_name = f"douyin_{index}.json"
                (base_dir / "cookiesFile" / cookie_name).write_text("{}")
                account_rows.append((100 + index, 3, cookie_name, f"抖音{index}", 1))

            with sqlite3.connect(database_path) as conn:
                cursor = conn.cursor()
                cursor.executemany(
                    """
                    INSERT INTO user_info (id, type, filePath, userName, status)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    account_rows,
                )
                conn.commit()

            payload = {
                "title": "并发测试",
                "fileList": ["video_a.mp4"],
                "accountIds": [100, 101, 102, 103],
                "accountList": [row[2] for row in account_rows],
                "enableTimer": 0,
            }

            def runner(**kwargs):
                time.sleep(0.2)
                return Mock(returncode=0, stdout="ok", stderr="")

            started_at = time.perf_counter()
            result = bridge.run_publish_payload(
                payload,
                base_dir=base_dir,
                now_provider=lambda: datetime(2026, 5, 13, 9, 0, 0),
                runner=runner,
            )
            elapsed = time.perf_counter() - started_at

        self.assertEqual(result["executed"], 4)
        self.assertLess(elapsed, 0.55)

    def test_run_publish_payload_runs_platforms_concurrently(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
            base_dir = Path(tmp_dir)
            (base_dir / "videoFile").mkdir()
            (base_dir / "cookiesFile").mkdir()
            (base_dir / "db").mkdir()
            (base_dir / "sau_cli.py").write_text("print('stub')", encoding="utf-8")
            (base_dir / "videoFile" / "video_a.mp4").write_bytes(b"a")
            database_path = base_dir / "db" / "database.db"
            create_user_info_table(database_path)

            account_rows = [
                (101, 1, "xhs_uuid.json", "灏忕孩涔", 1),
                (202, 3, "douyin_uuid.json", "鎶栭煶A", 1),
            ]
            for _, _, cookie_name, _, _ in account_rows:
                (base_dir / "cookiesFile" / cookie_name).write_text("{}")

            with sqlite3.connect(database_path) as conn:
                cursor = conn.cursor()
                cursor.executemany(
                    """
                    INSERT INTO user_info (id, type, filePath, userName, status)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    account_rows,
                )
                conn.commit()

            payload = {
                "title": "澶氬钩鍙板苟鍙戞祴璇�",
                "fileList": ["video_a.mp4"],
                "accountIds": [101, 202],
                "accountList": ["xhs_uuid.json", "douyin_uuid.json"],
                "enableTimer": 0,
            }

            def runner(**kwargs):
                time.sleep(0.2)
                return Mock(returncode=0, stdout="ok", stderr="")

            started_at = time.perf_counter()
            result = bridge.run_publish_payload(
                payload,
                base_dir=base_dir,
                now_provider=lambda: datetime(2026, 5, 13, 9, 0, 0),
                runner=runner,
            )
            elapsed = time.perf_counter() - started_at

        self.assertEqual(result["executed"], 2)
        self.assertLess(elapsed, 0.35)

    def test_build_publish_commands_maps_titles_per_video_file(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
            base_dir = Path(tmp_dir)
            (base_dir / "videoFile").mkdir()
            (base_dir / "cookiesFile").mkdir()
            (base_dir / "videoFile" / "video_a.mp4").write_bytes(b"a")
            (base_dir / "videoFile" / "video_b.mp4").write_bytes(b"b")
            (base_dir / "cookiesFile" / "acct_a.json").write_text("{}")

            payload = {
                "type": 3,
                "title": "兼容旧字段",
                "titles": ["标题A", "标题B"],
                "fileList": ["video_a.mp4", "video_b.mp4"],
                "accountList": ["acct_a.json"],
                "enableTimer": 0,
            }

            commands = bridge.build_publish_commands(payload, base_dir=base_dir)

        self.assertEqual(commands[0][commands[0].index("--title") + 1], "标题A")
        self.assertEqual(commands[1][commands[1].index("--title") + 1], "标题B")

    def test_build_publish_commands_rejects_mismatched_titles_and_files(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
            base_dir = Path(tmp_dir)
            (base_dir / "videoFile").mkdir()
            (base_dir / "cookiesFile").mkdir()
            (base_dir / "videoFile" / "video_a.mp4").write_bytes(b"a")
            (base_dir / "videoFile" / "video_b.mp4").write_bytes(b"b")
            (base_dir / "cookiesFile" / "acct_a.json").write_text("{}")

            payload = {
                "type": 3,
                "titles": ["标题A"],
                "fileList": ["video_a.mp4", "video_b.mp4"],
                "accountList": ["acct_a.json"],
                "enableTimer": 0,
            }

            with self.assertRaisesRegex(bridge.PublishBridgeError, "标题行数必须和作品数一致"):
                bridge.build_publish_commands(payload, base_dir=base_dir)

    def test_run_publish_batch_keeps_same_account_tabs_serial(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
            base_dir = Path(tmp_dir)
            (base_dir / "videoFile").mkdir()
            (base_dir / "cookiesFile").mkdir()
            (base_dir / "sau_cli.py").write_text("print('stub')", encoding="utf-8")
            (base_dir / "videoFile" / "video_a.mp4").write_bytes(b"a")
            (base_dir / "cookiesFile" / "acct_a.json").write_text("{}")

            payloads = [
                {"type": 1, "title": "tab1", "fileList": ["video_a.mp4"], "accountList": ["acct_a.json"], "enableTimer": 0},
                {"type": 1, "title": "tab2", "fileList": ["video_a.mp4"], "accountList": ["acct_a.json"], "enableTimer": 0},
            ]

            call_titles: list[str] = []

            def runner(**kwargs):
                call_titles.append(kwargs["args"][kwargs["args"].index("--title") + 1])
                return Mock(returncode=0, stdout="ok", stderr="")

            result = bridge.run_publish_batch(payloads, base_dir=base_dir, runner=runner)

        self.assertEqual(result["tasks"], 2)
        self.assertEqual(call_titles, ["tab1", "tab2"])

    def test_run_publish_batch_allows_different_accounts_from_multiple_tabs_to_overlap(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
            base_dir = Path(tmp_dir)
            (base_dir / "videoFile").mkdir()
            (base_dir / "cookiesFile").mkdir()
            (base_dir / "sau_cli.py").write_text("print('stub')", encoding="utf-8")
            (base_dir / "videoFile" / "video_a.mp4").write_bytes(b"a")
            (base_dir / "cookiesFile" / "acct_a.json").write_text("{}")
            (base_dir / "cookiesFile" / "acct_b.json").write_text("{}")

            payloads = [
                {"type": 1, "title": "tab1", "fileList": ["video_a.mp4"], "accountList": ["acct_a.json"], "enableTimer": 0},
                {"type": 1, "title": "tab2", "fileList": ["video_a.mp4"], "accountList": ["acct_b.json"], "enableTimer": 0},
            ]

            active_calls = 0
            max_active_calls = 0
            counter_lock = threading.Lock()

            def runner(**kwargs):
                nonlocal active_calls, max_active_calls
                with counter_lock:
                    active_calls += 1
                    max_active_calls = max(max_active_calls, active_calls)
                time.sleep(0.1)
                with counter_lock:
                    active_calls -= 1
                return Mock(returncode=0, stdout="ok", stderr="")

            result = bridge.run_publish_batch(payloads, base_dir=base_dir, runner=runner)

        self.assertEqual(result["tasks"], 2)
        self.assertGreaterEqual(max_active_calls, 2)


if __name__ == "__main__":
    unittest.main()
