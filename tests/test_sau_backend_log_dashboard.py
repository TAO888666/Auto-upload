import unittest
from unittest.mock import patch

import sau_backend


class SauBackendLogDashboardTests(unittest.TestCase):
    def setUp(self):
        sau_backend.app.config["TESTING"] = True
        self.client = sau_backend.app.test_client()

    def test_task_progress_logs_returns_backend_dashboard_payload(self):
        fake_payload = {
            "panels": [
                {
                    "id": "douyin",
                    "name": "抖音",
                    "file": "douyin.log",
                    "status": "active",
                    "updatedAt": "2026-05-13 18:36:27",
                    "lineCount": 2,
                    "lines": ["a", "b"],
                }
            ]
        }

        with patch("sau_backend.build_log_dashboard", return_value=fake_payload) as mock_build:
            response = self.client.get("/taskProgressLogs")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["code"], 200)
        self.assertEqual(response.get_json()["data"], fake_payload)
        mock_build.assert_called_once_with()

    def test_clear_task_progress_log_uses_backend_clear_helper(self):
        fake_payload = {
            "id": "douyin",
            "name": "抖音",
            "file": "douyin.log",
            "status": "idle",
            "updatedAt": "2026-05-14 10:30:00",
            "lineCount": 0,
            "lines": ["当前日志文件为空"],
        }

        with patch("sau_backend.clear_log_panel", return_value=fake_payload) as mock_clear:
            response = self.client.post("/taskProgressLogs/clear", json={"panelId": "douyin"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["code"], 200)
        self.assertEqual(response.get_json()["data"], fake_payload)
        mock_clear.assert_called_once_with("douyin")


if __name__ == "__main__":
    unittest.main()
