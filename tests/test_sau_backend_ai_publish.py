import json
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

import sau_backend


class SauBackendAiPublishTests(unittest.TestCase):
    def setUp(self):
        sau_backend.app.config["TESTING"] = True
        self.client = sau_backend.app.test_client()

    def test_ai_publish_config_routes_round_trip(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
            base_dir = Path(tmp_dir)

            with patch.object(sau_backend, "BASE_DIR", base_dir):
                get_response = self.client.get("/aiPublish/config")
                self.assertEqual(get_response.status_code, 200)
                get_payload = get_response.get_json()
                self.assertEqual(get_payload["code"], 200)
                self.assertEqual(get_payload["data"]["hasApiKey"], False)

                save_response = self.client.post(
                    "/aiPublish/config",
                    json={
                        "provider": "deepseek",
                        "apiBase": "https://api.deepseek.com/v1",
                        "apiKey": "sk-demo",
                        "defaultModel": "deepseek-chat",
                    },
                )
                self.assertEqual(save_response.status_code, 200)
                save_payload = save_response.get_json()
                self.assertEqual(save_payload["data"]["hasApiKey"], True)

                stored = json.loads((base_dir / "gui_config.json").read_text(encoding="utf-8"))
                self.assertEqual(stored["provider"], "deepseek")
                self.assertEqual(stored["api_key"], "sk-demo")

                models_response = self.client.get("/aiPublish/models")
                self.assertEqual(models_response.status_code, 200)
                models_payload = models_response.get_json()
                self.assertEqual(models_payload["code"], 200)
                self.assertTrue(any(model["id"] == "deepseek-chat" for model in models_payload["data"]["models"]))

    def test_ai_publish_chat_start_uses_submit_helper(self):
        task_data = {"taskId": "ai-task-1", "status": "queued"}
        payload = {
            "conversationId": "conv-1",
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": "帮我发作品"}],
        }

        with patch("sau_backend._submit_ai_publish_chat_task", return_value=task_data, create=True) as mock_submit:
            response = self.client.post("/aiPublish/chat/start", json=payload)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["data"], task_data)
        mock_submit.assert_called_once_with(payload)

    def test_publish_center_generate_route_uses_ai_helper(self):
        payload = {
            "works": [
                {
                    "kind": "video",
                    "name": "demo.mp4",
                    "filePaths": ["demo.mp4"],
                }
            ],
            "platforms": ["douyin"],
            "accounts": ["千聊官号"],
            "model": "doubao-seed-2-0-mini-260428",
        }
        generated = {
            "items": [{"title": "测试标题", "content": "测试文案"}],
            "titles": ["测试标题"],
            "contents": ["测试文案"],
            "titleText": "测试标题",
            "contentText": "测试文案",
        }

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
            base_dir = Path(tmp_dir)
            with patch.object(sau_backend, "BASE_DIR", base_dir), patch(
                "sau_backend.load_ai_publish_config",
                return_value={
                    "provider": "ark",
                    "api_key": "sk-demo",
                    "api_base": "https://ark.cn-beijing.volces.com/api/v3",
                    "model": "doubao-seed-2-0-mini-260428",
                },
            ), patch(
                "sau_backend.generate_publish_center_copy",
                return_value=generated,
                create=True,
            ) as mock_generate:
                response = self.client.post("/aiPublish/publishCenter/generate", json=payload)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["data"], generated)
        mock_generate.assert_called_once_with(
            {
                "provider": "ark",
                "api_key": "sk-demo",
                "api_base": "https://ark.cn-beijing.volces.com/api/v3",
                "model": "doubao-seed-2-0-mini-260428",
            },
            works=payload["works"],
            base_dir=base_dir,
            platforms=payload["platforms"],
            account_names=payload["accounts"],
            model=payload["model"],
        )

    def test_ai_publish_chat_stream_emits_initial_snapshot(self):
        task_state = {
            "taskId": "ai-task-1",
            "conversationId": "conv-1",
            "status": "success",
            "message": "done",
            "createdAt": "2026-05-22T10:00:00",
            "updatedAt": "2026-05-22T10:00:01",
            "startedAt": "2026-05-22T10:00:00",
            "finishedAt": "2026-05-22T10:00:01",
            "model": "deepseek-chat",
            "result": {"taskPreview": None},
            "events": [],
        }

        with patch("sau_backend._get_ai_publish_task_state", side_effect=[task_state, task_state, task_state], create=True):
            response = self.client.get("/aiPublish/chatTasks/ai-task-1/stream")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "text/event-stream")
        self.assertEqual(response.headers.get("Content-Type"), "text/event-stream; charset=utf-8")
        self.assertIn("event: task-snapshot", response.get_data(as_text=True))

    def test_ai_publish_confirm_builds_publish_task(self):
        publish_task = {"taskId": "publish-1", "status": "queued"}
        confirm_payload = {
            "conversationId": "conv-1",
            "task": {
                "accounts": [{"id": 3, "platform": "douyin", "name": "千聊官号"}],
                "works": [{"name": "A作品", "kind": "video", "filePath": "demo.mp4"}],
                "title": "测试标题",
                "content": "测试文案",
                "tags": ["测试"],
                "scheduleType": "now",
                "scheduleTime": "",
            },
        }
        bridge_payload = {
            "accountIds": [3],
            "works": [{"kind": "video", "filePath": "demo.mp4"}],
            "title": "测试标题",
            "content": "测试文案",
            "tags": ["测试"],
        }

        with patch("sau_backend._build_ai_publish_confirm_payload", return_value=bridge_payload, create=True) as mock_build, patch(
            "sau_backend._submit_publish_task",
            return_value=publish_task,
            create=True,
        ) as mock_submit:
            response = self.client.post("/aiPublish/task/confirm", json=confirm_payload)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["data"]["publishTaskId"], "publish-1")
        mock_build.assert_called_once_with(confirm_payload["task"])
        mock_submit.assert_called_once_with("single", bridge_payload, sau_backend.run_publish_payload, tab_count=1)

    def test_ai_publish_upload_accepts_png(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
            base_dir = Path(tmp_dir)
            with patch.object(sau_backend, "BASE_DIR", base_dir):
                response = self.client.post(
                    "/aiPublish/uploads",
                    data={
                        "file": (BytesIO(b"\x89PNG\r\n\x1a\n"), "demo.png"),
                    },
                    content_type="multipart/form-data",
                )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["code"], 200)
        self.assertEqual(payload["data"]["mimeType"], "image/png")
        self.assertEqual(payload["data"]["originalName"], "demo.png")
        self.assertEqual(payload["data"]["category"], "image")

    def test_ai_publish_upload_accepts_audio_and_video(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
            base_dir = Path(tmp_dir)
            with patch.object(sau_backend, "BASE_DIR", base_dir):
                audio_response = self.client.post(
                    "/aiPublish/uploads",
                    data={
                        "file": (BytesIO(b"ID3demo"), "demo.mp3"),
                    },
                    content_type="multipart/form-data",
                )
                video_response = self.client.post(
                    "/aiPublish/uploads",
                    data={
                        "file": (BytesIO(b"\x00\x00\x00\x18ftypmp42"), "demo.mp4"),
                    },
                    content_type="multipart/form-data",
                )

        self.assertEqual(audio_response.status_code, 200)
        self.assertEqual(video_response.status_code, 200)
        self.assertEqual(audio_response.get_json()["data"]["category"], "audio")
        self.assertEqual(video_response.get_json()["data"]["category"], "video")

    def test_ai_publish_upload_accepts_video_with_chinese_filename(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
            base_dir = Path(tmp_dir)
            with patch.object(sau_backend, "BASE_DIR", base_dir):
                response = self.client.post(
                    "/aiPublish/uploads",
                    data={
                        "file": (BytesIO(b"\x00\x00\x00\x18ftypmp42"), "测试.mp4"),
                    },
                    content_type="multipart/form-data",
                )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["data"]["category"], "video")
        self.assertEqual(payload["data"]["mimeType"], "video/mp4")
        self.assertEqual(payload["data"]["originalName"], "测试.mp4")

    def test_ai_publish_upload_rejects_non_image_file(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
            base_dir = Path(tmp_dir)
            with patch.object(sau_backend, "BASE_DIR", base_dir):
                response = self.client.post(
                    "/aiPublish/uploads",
                    data={
                        "file": (BytesIO(b"hello"), "demo.txt"),
                    },
                    content_type="multipart/form-data",
                )

        self.assertEqual(response.status_code, 400)
        payload = response.get_json()
        self.assertEqual(payload["code"], 400)

    def test_hydrate_ai_publish_messages_keeps_relative_path_attachments(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
            base_dir = Path(tmp_dir)
            upload_dir = base_dir / "tmp" / sau_backend.AI_PUBLISH_UPLOAD_DIRNAME
            upload_dir.mkdir(parents=True, exist_ok=True)
            image_path = upload_dir / "demo.png"
            image_path.write_bytes(b"\x89PNG\r\n\x1a\n")

            hydrated_messages = sau_backend._hydrate_ai_publish_messages(
                [
                    {
                        "role": "user",
                        "content": "看看这张图",
                        "attachments": [
                            {
                                "relativePath": "tmp/ai_publish_uploads/demo.png",
                                "mimeType": "image/png",
                                "originalName": "demo.png",
                            }
                        ],
                    }
                ],
                base_dir,
            )

        self.assertEqual(len(hydrated_messages), 1)
        self.assertEqual(len(hydrated_messages[0]["attachments"]), 1)
        self.assertTrue(
            hydrated_messages[0]["attachments"][0]["dataUrl"].startswith("data:image/png;base64,")
        )

    def test_hydrate_ai_publish_messages_strips_history_message_attachments(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
            base_dir = Path(tmp_dir)
            upload_dir = base_dir / "tmp" / sau_backend.AI_PUBLISH_UPLOAD_DIRNAME
            upload_dir.mkdir(parents=True, exist_ok=True)
            (upload_dir / "first.mp4").write_bytes(b"\x00\x00\x00\x18ftypmp42")
            (upload_dir / "second.mp4").write_bytes(b"\x00\x00\x00\x18ftypmp42")

            hydrated_messages = sau_backend._hydrate_ai_publish_messages(
                [
                    {
                        "role": "user",
                        "content": "先看第一个视频",
                        "attachments": [
                            {
                                "relativePath": "tmp/ai_publish_uploads/first.mp4",
                                "mimeType": "video/mp4",
                                "originalName": "first.mp4",
                            }
                        ],
                    },
                    {
                        "role": "assistant",
                        "content": "我看完了",
                        "attachments": [],
                    },
                    {
                        "role": "user",
                        "content": "再看第二个视频",
                        "attachments": [
                            {
                                "relativePath": "tmp/ai_publish_uploads/second.mp4",
                                "mimeType": "video/mp4",
                                "originalName": "second.mp4",
                            }
                        ],
                    },
                ],
                base_dir,
            )

        self.assertEqual(len(hydrated_messages), 3)
        self.assertEqual(hydrated_messages[0]["attachments"], [])
        self.assertEqual(hydrated_messages[1]["attachments"], [])
        self.assertEqual(len(hydrated_messages[2]["attachments"]), 1)
        self.assertEqual(hydrated_messages[2]["attachments"][0]["originalName"], "second.mp4")

    def test_plain_chat_skips_publish_analysis(self):
        task_id = "ai-task-plain-chat"
        task_state = {
            "taskId": task_id,
            "conversationId": "conv-plain",
            "status": "queued",
            "message": "queued",
            "createdAt": "2026-05-22T10:00:00",
            "updatedAt": "2026-05-22T10:00:00",
            "startedAt": None,
            "finishedAt": None,
            "model": "deepseek-chat",
            "assistantText": "",
            "taskPreview": None,
            "result": None,
            "eventSeq": 0,
            "events": [],
        }

        with patch("sau_backend.BASE_DIR", Path(".")), patch(
            "sau_backend.load_ai_publish_config",
            return_value={"provider": "deepseek", "api_base": "https://example.com/v1", "api_key": "sk-demo", "model": "deepseek-chat"},
        ), patch("sau_backend.stream_chat_completion", return_value=iter(["你好"])), patch(
            "sau_backend.load_ai_publish_context"
        ) as mock_context, patch("sau_backend.analyze_publish_task") as mock_analyze:
            with sau_backend.ai_publish_tasks_lock:
                sau_backend.ai_publish_tasks[task_id] = task_state
            sau_backend._run_ai_publish_chat_task(
                task_id,
                {
                    "conversationId": "conv-plain",
                    "model": "deepseek-chat",
                    "messages": [{"role": "user", "content": "你是什么模型"}],
                },
            )

        mock_context.assert_not_called()
        mock_analyze.assert_not_called()
        with sau_backend.ai_publish_tasks_lock:
            event_types = [event["type"] for event in sau_backend.ai_publish_tasks[task_id]["events"]]
        self.assertIn("assistant-finished", event_types)

    def test_publish_request_runs_publish_analysis(self):
        task_id = "ai-task-publish-chat"
        task_state = {
            "taskId": task_id,
            "conversationId": "conv-publish",
            "status": "queued",
            "message": "queued",
            "createdAt": "2026-05-22T10:00:00",
            "updatedAt": "2026-05-22T10:00:00",
            "startedAt": None,
            "finishedAt": None,
            "model": "deepseek-chat",
            "assistantText": "",
            "taskPreview": None,
            "result": None,
            "eventSeq": 0,
            "events": [],
        }
        preview = {"intent": "publish", "ready": False}

        with patch("sau_backend.BASE_DIR", Path(".")), patch(
            "sau_backend.load_ai_publish_config",
            return_value={"provider": "deepseek", "api_base": "https://example.com/v1", "api_key": "sk-demo", "model": "deepseek-chat"},
        ), patch("sau_backend.stream_chat_completion", return_value=iter(["好的，我来帮你整理发布任务。"])), patch(
            "sau_backend.load_ai_publish_context",
            return_value={"accounts": [], "materials": []},
        ) as mock_context, patch("sau_backend.analyze_publish_task", return_value=preview) as mock_analyze:
            with sau_backend.ai_publish_tasks_lock:
                sau_backend.ai_publish_tasks[task_id] = task_state
            sau_backend._run_ai_publish_chat_task(
                task_id,
                {
                    "conversationId": "conv-publish",
                    "model": "deepseek-chat",
                    "messages": [{"role": "user", "content": "帮我发布这个作品到抖音"}],
                },
            )

        mock_context.assert_called_once()
        mock_analyze.assert_called_once()
        with sau_backend.ai_publish_tasks_lock:
            event_types = [event["type"] for event in sau_backend.ai_publish_tasks[task_id]["events"]]
        self.assertIn("assistant-finished", event_types)
        self.assertIn("task-preview", event_types)
        self.assertIn("task-finished", event_types)
        self.assertLess(event_types.index("assistant-finished"), event_types.index("task-preview"))
        self.assertLess(event_types.index("assistant-finished"), event_types.index("task-finished"))

    def test_ai_publish_storage_route_reports_usage(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
            base_dir = Path(tmp_dir)
            upload_dir = base_dir / "tmp" / sau_backend.AI_PUBLISH_UPLOAD_DIRNAME
            upload_dir.mkdir(parents=True, exist_ok=True)
            (upload_dir / "demo.png").write_bytes(b"1234")

            work_dir = base_dir / "videoFile"
            work_dir.mkdir(parents=True, exist_ok=True)
            (work_dir / "demo.mp4").write_bytes(b"123456")

            with patch.object(sau_backend, "BASE_DIR", base_dir):
                response = self.client.get("/aiPublish/storage")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["code"], 200)
        self.assertEqual(payload["data"]["aiAttachments"]["fileCount"], 1)
        self.assertEqual(payload["data"]["aiAttachments"]["sizeBytes"], 4)
        self.assertEqual(payload["data"]["workFiles"]["fileCount"], 1)
        self.assertEqual(payload["data"]["workFiles"]["sizeBytes"], 6)

    def test_ai_publish_storage_cleanup_clears_only_selected_target(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
            base_dir = Path(tmp_dir)
            upload_dir = base_dir / "tmp" / sau_backend.AI_PUBLISH_UPLOAD_DIRNAME
            upload_dir.mkdir(parents=True, exist_ok=True)
            (upload_dir / "demo.png").write_bytes(b"1234")

            work_dir = base_dir / "videoFile"
            work_dir.mkdir(parents=True, exist_ok=True)
            (work_dir / "demo.mp4").write_bytes(b"123456")

            with patch.object(sau_backend, "BASE_DIR", base_dir):
                attachments_response = self.client.post(
                    "/aiPublish/storage/cleanup",
                    json={"target": "aiAttachments"},
                )
                work_response = self.client.post(
                    "/aiPublish/storage/cleanup",
                    json={"target": "workFiles"},
                )

        self.assertEqual(attachments_response.status_code, 200)
        self.assertEqual(work_response.status_code, 200)
        self.assertFalse((upload_dir / "demo.png").exists())
        self.assertFalse((work_dir / "demo.mp4").exists())
        self.assertEqual(attachments_response.get_json()["data"]["current"]["sizeBytes"], 0)
        self.assertEqual(work_response.get_json()["data"]["current"]["sizeBytes"], 0)


if __name__ == "__main__":
    unittest.main()
