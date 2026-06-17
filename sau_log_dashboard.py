from __future__ import annotations

from datetime import datetime
from pathlib import Path

from conf import BASE_DIR

LOG_PANEL_MAPPING = [
    {"id": "douyin", "name": "抖音", "file": "douyin.log"},
    {"id": "kuaishou", "name": "快手", "file": "kuaishou.log"},
    {"id": "xiaohongshu", "name": "小红书", "file": "xiaohongshu.log"},
    {"id": "tencent", "name": "视频号", "file": "tencent.log"},
]


def _read_tail_lines(file_path: Path, max_lines: int) -> list[str]:
    text = file_path.read_text(encoding="utf-8", errors="replace")
    if not text:
        return []
    lines = text.splitlines()
    if max_lines <= 0:
        return lines
    return lines[-max_lines:]


def _find_panel_mapping(panel_id: str) -> dict:
    for mapping in LOG_PANEL_MAPPING:
        if mapping["id"] == panel_id:
            return mapping
    raise ValueError(f"unknown panel id: {panel_id}")


def _build_panel_payload(mapping: dict, file_path: Path, max_lines: int) -> dict:
    if not file_path.exists():
        return {
            "id": mapping["id"],
            "name": mapping["name"],
            "file": mapping["file"],
            "status": "missing",
            "updatedAt": "",
            "lineCount": 0,
            "lines": ["日志文件不存在"],
        }

    lines = _read_tail_lines(file_path, max_lines=max_lines)
    updated_at = datetime.fromtimestamp(file_path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
    status = "active" if lines else "idle"
    if status == "idle":
        lines = ["当前日志文件为空"]

    return {
        "id": mapping["id"],
        "name": mapping["name"],
        "file": mapping["file"],
        "status": status,
        "updatedAt": updated_at,
        "lineCount": len(lines) if status == "active" else 0,
        "lines": lines,
    }


def build_log_dashboard(*, base_dir: Path = BASE_DIR, max_lines: int = 200) -> dict:
    logs_dir = Path(base_dir) / "logs"
    panels = []

    for mapping in LOG_PANEL_MAPPING:
        file_path = logs_dir / mapping["file"]
        panels.append(_build_panel_payload(mapping, file_path, max_lines=max_lines))

    return {"panels": panels}


def clear_log_panel(panel_id: str, *, base_dir: Path = BASE_DIR, max_lines: int = 200) -> dict:
    mapping = _find_panel_mapping(panel_id)
    logs_dir = Path(base_dir) / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    file_path = logs_dir / mapping["file"]
    file_path.write_text("", encoding="utf-8")

    return _build_panel_payload(mapping, file_path, max_lines=max_lines)
