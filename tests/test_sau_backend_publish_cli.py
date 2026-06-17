import unittest
from unittest.mock import patch

import sau_backend


class SauBackendPublishCliTests(unittest.TestCase):
    def setUp(self):
        sau_backend.app.config["TESTING"] = True
        self.client = sau_backend.app.test_client()
        with sau_backend.publish_tasks_lock:
            sau_backend.publish_tasks.clear()

    def test_post_video_creates_async_publish_task(self):
        payload = {
            "type": 3,
            "title": "??A\n??B",
            "titles": ["??A", "??B"],
            "fileList": ["video_a.mp4", "video_b.mp4"],
            "accountList": ["acct.json"],
        }

        task_data = {"taskId": "task-1", "status": "queued"}
        with patch("sau_backend._submit_publish_task", return_value=task_data, create=True) as mock_submit:
            response = self.client.post("/postVideo", json=payload)

        self.assertEqual(response.status_code, 200)
        mock_submit.assert_called_once_with("single", payload, sau_backend.run_publish_payload, tab_count=1)
        self.assertEqual(response.get_json()["code"], 200)
        self.assertEqual(response.get_json()["data"], task_data)

    def test_post_video_batch_creates_async_publish_task(self):
        payload = [
            {
                "type": 1,
                "title": "??A\n??B",
                "titles": ["??A", "??B"],
                "fileList": ["video_a.mp4", "video_b.mp4"],
                "accountList": ["acct.json"],
            }
        ]

        task_data = {"taskId": "task-batch", "status": "queued"}
        with patch("sau_backend._submit_publish_task", return_value=task_data, create=True) as mock_submit:
            response = self.client.post("/postVideoBatch", json=payload)

        self.assertEqual(response.status_code, 200)
        mock_submit.assert_called_once_with("batch", payload, sau_backend.run_publish_batch, tab_count=1)
        self.assertEqual(response.get_json()["code"], 200)
        self.assertEqual(response.get_json()["data"], task_data)

    def test_get_publish_task_returns_task_snapshot(self):
        with patch("sau_backend._get_publish_task_snapshot", return_value={"taskId": "task-1", "status": "running"}):
            response = self.client.get("/publishTasks/task-1")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["data"]["taskId"], "task-1")

    def test_get_current_publish_task_returns_latest_snapshot(self):
        with patch("sau_backend._get_latest_publish_task_snapshot", return_value={"taskId": "task-live", "status": "running"}):
            response = self.client.get("/publishTasks/current")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["data"]["taskId"], "task-live")

    def test_publish_task_stream_emits_initial_snapshot(self):
        task_state = {
            "taskId": "task-1",
            "status": "success",
            "mode": "single",
            "tabCount": 1,
            "message": "done",
            "createdAt": "2026-05-19T10:00:00",
            "updatedAt": "2026-05-19T10:00:01",
            "startedAt": "2026-05-19T10:00:00",
            "finishedAt": "2026-05-19T10:00:01",
            "result": None,
            "items": [],
            "events": [],
            "totalItems": 0,
            "completedItems": 0,
            "pendingItems": 0,
            "runningItems": 0,
            "successItems": 0,
            "errorItems": 0,
            "skippedItems": 0,
        }
        with patch("sau_backend._get_publish_task_state", side_effect=[task_state, task_state, task_state]):
            response = self.client.get("/publishTasks/task-1/stream")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "text/event-stream")
        self.assertIn("event: task-snapshot", response.get_data(as_text=True))

    def test_pause_publish_task_sets_pause_request(self):
        with patch(
            "sau_backend._get_publish_task_snapshot",
            side_effect=[
                {"taskId": "task-1", "status": "running"},
                {"taskId": "task-1", "status": "running", "pauseRequested": True},
            ],
        ), patch("sau_backend._request_publish_task_pause", return_value=True):
            response = self.client.post("/publishTasks/task-1/pause")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["code"], 200)

    def test_retry_publish_task_item_rejects_non_failed_item(self):
        with patch("sau_backend._get_publish_task_item_state", return_value={"itemId": "item-1", "status": "success"}):
            response = self.client.post("/publishTasks/task-1/items/item-1/retry")

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()["code"], 409)

    def test_post_video_returns_conflict_when_another_task_is_running(self):
        payload = {
            "title": "??A",
            "fileList": ["video_a.mp4"],
            "accountList": ["acct.json"],
        }

        with patch(
            "sau_backend._submit_publish_task",
            side_effect=sau_backend.PublishBridgeError("Another publish task is already running", status_code=409),
            create=True,
        ):
            response = self.client.post("/postVideo", json=payload)

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()["code"], 409)

    def test_submit_publish_task_initializes_planned_items(self):
        class FakeThread:
            def __init__(self, *args, **kwargs):
                self.started = False

            def start(self):
                self.started = True

        planned_items = [
            {
                "itemId": "item-0",
                "orderIndex": 0,
                "taskIndex": 0,
                "kind": "video",
                "platform": "douyin",
                "platformType": 3,
                "accountName": "acct",
                "title": "title",
                "mediaLabel": "video_a.mp4",
                "mediaPaths": ["video_a.mp4"],
                "command": ["douyin", "video_a.mp4"],
            }
        ]

        with patch("sau_backend._build_publish_task_plan", return_value=planned_items) as mock_plan, patch(
            "sau_backend.threading.Thread",
            FakeThread,
        ):
            task = sau_backend._submit_publish_task(
                "batch",
                [{"fileList": ["video_a.mp4"]}],
                lambda *args, **kwargs: None,
                tab_count=1,
            )

        mock_plan.assert_called_once_with("batch", [{"fileList": ["video_a.mp4"]}])
        self.assertEqual(task["totalItems"], 1)
        self.assertEqual(task["pendingItems"], 1)
        self.assertEqual(task["items"][0]["itemId"], "item-0")
        self.assertEqual(task["items"][0]["status"], "pending")
        self.assertNotIn("command", task["items"][0])


if __name__ == "__main__":
    unittest.main()
