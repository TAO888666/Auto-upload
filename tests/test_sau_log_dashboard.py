import tempfile
import unittest
from pathlib import Path

import sau_log_dashboard as dashboard


class SauLogDashboardTests(unittest.TestCase):
    def test_build_log_dashboard_reads_fixed_panel_mapping(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            base_dir = Path(tmp_dir)
            logs_dir = base_dir / "logs"
            logs_dir.mkdir()

            (logs_dir / "douyin.log").write_text(
                "[18:36:03] 开始发布 抖音 / 千聊开课平台\n[18:36:49] 发布成功\n",
                encoding="utf-8",
            )
            (logs_dir / "kuaishou.log").write_text("", encoding="utf-8")
            (logs_dir / "xiaohongshu.log").write_text(
                "[11:50:42] 等待新的小红书发布任务\n",
                encoding="utf-8",
            )
            (logs_dir / "tencent.log").write_text(
                "[17:38:47] WARN  当前走的是旧链路\n",
                encoding="utf-8",
            )

            payload = dashboard.build_log_dashboard(base_dir=base_dir, max_lines=2)

        self.assertEqual([panel["id"] for panel in payload["panels"]], [
            "douyin",
            "kuaishou",
            "xiaohongshu",
            "tencent",
        ])
        self.assertEqual(payload["panels"][0]["file"], "douyin.log")
        self.assertEqual(payload["panels"][0]["status"], "active")
        self.assertEqual(payload["panels"][0]["lines"], [
            "[18:36:03] 开始发布 抖音 / 千聊开课平台",
            "[18:36:49] 发布成功",
        ])
        self.assertEqual(payload["panels"][1]["status"], "idle")
        self.assertEqual(payload["panels"][2]["lineCount"], 1)
        self.assertEqual(payload["panels"][3]["name"], "视频号")

    def test_build_log_dashboard_marks_missing_files(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            base_dir = Path(tmp_dir)
            (base_dir / "logs").mkdir()

            payload = dashboard.build_log_dashboard(base_dir=base_dir)

        self.assertEqual(len(payload["panels"]), 4)
        self.assertEqual(payload["panels"][0]["status"], "missing")
        self.assertEqual(payload["panels"][0]["lines"], ["日志文件不存在"])

    def test_clear_log_panel_empties_target_file(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            base_dir = Path(tmp_dir)
            logs_dir = base_dir / "logs"
            logs_dir.mkdir()
            log_file = logs_dir / "douyin.log"
            log_file.write_text("line1\nline2\n", encoding="utf-8")

            result = dashboard.clear_log_panel("douyin", base_dir=base_dir)

            self.assertEqual(result["id"], "douyin")
            self.assertEqual(result["file"], "douyin.log")
            self.assertEqual(log_file.read_text(encoding="utf-8"), "")

    def test_clear_log_panel_rejects_unknown_panel(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            base_dir = Path(tmp_dir)
            (base_dir / "logs").mkdir()

            with self.assertRaises(ValueError):
                dashboard.clear_log_panel("unknown", base_dir=base_dir)


if __name__ == "__main__":
    unittest.main()
