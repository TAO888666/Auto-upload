import asyncio
import base64
import copy
import json
import mimetypes
import os
import re
import sqlite3
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from queue import Queue
from flask_cors import CORS
from myUtils.auth import check_cookie
from flask import Flask, request, jsonify, Response, render_template, send_from_directory
from myUtils.ai_publish_service import (
    BASE_SYSTEM_PROMPT,
    analyze_publish_task,
    build_model_options,
    generate_publish_center_copy,
    load_ai_publish_config,
    load_ai_publish_context,
    normalize_chat_messages,
    normalize_messages,
    save_ai_publish_config,
    serialize_ai_publish_config,
    stream_chat_completion,
    test_ai_publish_connection,
)
from conf import BASE_DIR
from myUtils.login import get_tencent_cookie, douyin_cookie_gen, get_ks_cookie, xiaohongshu_cookie_gen
from myUtils.postVideo import post_video_tencent, post_video_DouYin, post_video_ks, post_video_xhs
from sau_log_dashboard import build_log_dashboard, clear_log_panel
from sau_login_bridge import (
    confirm_browser_login_session,
    run_login_flow,
    start_account_browser_session,
    start_browser_login_session,
)
from sau_publish_cli_bridge import (
    PublishBridgeError,
    build_publish_batch_plan,
    build_publish_plan,
    run_publish_batch,
    run_publish_plan_items,
    run_publish_payload,
)
from werkzeug.utils import secure_filename
from utils.account_profile import fetch_account_profile_from_cookie, fetch_avatar_url_from_cookie
from utils.user_info_db import UNSET, ensure_user_info_schema_at_path, update_user_info_status

active_queues = {}
publish_tasks = {}
publish_tasks_lock = threading.Lock()
account_validation_tasks = {}
account_validation_tasks_lock = threading.Lock()
ai_publish_tasks = {}
ai_publish_tasks_lock = threading.Lock()
MAX_PUBLISH_TASK_RECORDS = 20
MAX_ACCOUNT_VALIDATION_TASK_RECORDS = 20
MAX_AI_PUBLISH_TASK_RECORDS = 20
ACCOUNT_VALIDATION_CONCURRENCY = 20
MAX_PUBLISH_TASK_EVENT_RECORDS = 400
MAX_ACCOUNT_VALIDATION_TASK_EVENT_RECORDS = 400
MAX_AI_PUBLISH_TASK_EVENT_RECORDS = 400
app = Flask(__name__)

#允许所有来源跨域访问
CORS(app)

# 限制上传文件大小为160MB
app.config['MAX_CONTENT_LENGTH'] = 2000 * 1024 * 1024

# 获取当前目录（假设 index.html 和 assets 在这里）
current_dir = os.path.dirname(os.path.abspath(__file__))
AI_PUBLISH_UPLOAD_DIRNAME = "ai_publish_uploads"
AI_PUBLISH_ALLOWED_ATTACHMENT_EXTENSIONS = {
    ".png": {"mimeType": "image/png", "category": "image", "maxBytes": 10 * 1024 * 1024},
    ".jpg": {"mimeType": "image/jpeg", "category": "image", "maxBytes": 10 * 1024 * 1024},
    ".jpeg": {"mimeType": "image/jpeg", "category": "image", "maxBytes": 10 * 1024 * 1024},
    ".webp": {"mimeType": "image/webp", "category": "image", "maxBytes": 10 * 1024 * 1024},
    ".mp3": {"mimeType": "audio/mpeg", "category": "audio", "maxBytes": 50 * 1024 * 1024},
    ".wav": {"mimeType": "audio/wav", "category": "audio", "maxBytes": 50 * 1024 * 1024},
    ".m4a": {"mimeType": "audio/mp4", "category": "audio", "maxBytes": 50 * 1024 * 1024},
    ".aac": {"mimeType": "audio/aac", "category": "audio", "maxBytes": 50 * 1024 * 1024},
    ".ogg": {"mimeType": "audio/ogg", "category": "audio", "maxBytes": 50 * 1024 * 1024},
    ".flac": {"mimeType": "audio/flac", "category": "audio", "maxBytes": 50 * 1024 * 1024},
    ".mp4": {"mimeType": "video/mp4", "category": "video", "maxBytes": 200 * 1024 * 1024},
    ".mov": {"mimeType": "video/quicktime", "category": "video", "maxBytes": 200 * 1024 * 1024},
    ".avi": {"mimeType": "video/x-msvideo", "category": "video", "maxBytes": 200 * 1024 * 1024},
    ".mkv": {"mimeType": "video/x-matroska", "category": "video", "maxBytes": 200 * 1024 * 1024},
    ".webm": {"mimeType": "video/webm", "category": "video", "maxBytes": 200 * 1024 * 1024},
    ".m4v": {"mimeType": "video/x-m4v", "category": "video", "maxBytes": 200 * 1024 * 1024},
}


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _prune_publish_tasks_locked() -> None:
    if len(publish_tasks) <= MAX_PUBLISH_TASK_RECORDS:
        return

    finished_ids = [
        task_id
        for task_id, task in publish_tasks.items()
        if task.get("status") in {"success", "error", "paused"}
    ]
    finished_ids.sort(key=lambda task_id: publish_tasks[task_id].get("createdAt", ""))
    while len(publish_tasks) > MAX_PUBLISH_TASK_RECORDS and finished_ids:
        publish_tasks.pop(finished_ids.pop(0), None)


def _serialize_publish_task(task: dict | None):
    if not task:
        return None

    serialized_items = []
    for item in task.get("items", []):
        serialized_items.append(
            {
                key: value
                for key, value in item.items()
                if key not in {"command"}
            }
        )

    return {
        "taskId": task["taskId"],
        "mode": task.get("mode"),
        "tabCount": task.get("tabCount", 1),
        "status": task.get("status"),
        "message": task.get("message"),
        "createdAt": task.get("createdAt"),
        "updatedAt": task.get("updatedAt"),
        "startedAt": task.get("startedAt"),
        "finishedAt": task.get("finishedAt"),
        "result": copy.deepcopy(task.get("result")),
        "pauseRequested": bool(task.get("pauseRequested")),
        "totalItems": task.get("totalItems", 0),
        "completedItems": task.get("completedItems", 0),
        "pendingItems": task.get("pendingItems", 0),
        "runningItems": task.get("runningItems", 0),
        "successItems": task.get("successItems", 0),
        "errorItems": task.get("errorItems", 0),
        "skippedItems": task.get("skippedItems", 0),
        "pausedItems": task.get("pausedItems", 0),
        "items": serialized_items,
    }


def _append_publish_task_snapshot_locked(task: dict) -> None:
    task["eventSeq"] = int(task.get("eventSeq", 0)) + 1
    task.setdefault("events", []).append(
        {
            "seq": task["eventSeq"],
            "type": "task-snapshot",
            "createdAt": _now_iso(),
            "data": _serialize_publish_task(task),
        }
    )
    if len(task["events"]) > MAX_PUBLISH_TASK_EVENT_RECORDS:
        task["events"] = task["events"][-MAX_PUBLISH_TASK_EVENT_RECORDS:]


def _refresh_publish_task_counts_locked(task: dict) -> None:
    items = task.get("items", [])
    total_items = len(items)
    pending_items = sum(1 for item in items if item.get("status") == "pending")
    running_items = sum(1 for item in items if item.get("status") == "running")
    success_items = sum(1 for item in items if item.get("status") == "success")
    error_items = sum(1 for item in items if item.get("status") == "error")
    skipped_items = sum(1 for item in items if item.get("status") == "skipped")
    paused_items = sum(1 for item in items if item.get("status") == "paused")
    completed_items = success_items + error_items + skipped_items + paused_items

    task["totalItems"] = total_items
    task["pendingItems"] = pending_items
    task["runningItems"] = running_items
    task["successItems"] = success_items
    task["errorItems"] = error_items
    task["skippedItems"] = skipped_items
    task["pausedItems"] = paused_items
    task["completedItems"] = completed_items


def _sanitize_publish_task_item(raw_item: dict) -> dict:
    return {
        "itemId": str(raw_item.get("itemId") or ""),
        "orderIndex": int(raw_item.get("orderIndex") or 0),
        "taskIndex": int(raw_item.get("taskIndex") or 0),
        "kind": raw_item.get("kind"),
        "platform": str(raw_item.get("platform") or ""),
        "platformType": raw_item.get("platformType"),
        "accountId": raw_item.get("accountId"),
        "accountName": str(raw_item.get("accountName") or ""),
        "title": str(raw_item.get("title") or ""),
        "videoTitle": str(raw_item.get("mediaLabel") or raw_item.get("title") or ""),
        "mediaPaths": list(raw_item.get("mediaPaths") or []),
        "scheduleValue": raw_item.get("scheduleValue"),
        "status": "pending",
        "progress": 0,
        "message": "等待中",
        "errorMessage": "",
        "updatedAt": _now_iso(),
        "command": list(raw_item.get("command") or []),
    }


def _get_publish_task_snapshot(task_id: str):
    with publish_tasks_lock:
        return _serialize_publish_task(publish_tasks.get(task_id))


def _get_publish_task_state(task_id: str):
    with publish_tasks_lock:
        task = publish_tasks.get(task_id)
        return copy.deepcopy(task) if task else None


def _get_latest_publish_task_snapshot():
    with publish_tasks_lock:
        if not publish_tasks:
            return None

        tasks = list(publish_tasks.values())
        active_tasks = [task for task in tasks if task.get("status") in {"queued", "running"}]
        candidates = active_tasks or tasks
        candidates.sort(key=lambda task: task.get("createdAt", ""))
        return _serialize_publish_task(candidates[-1])


def _get_publish_task_item_state(task_id: str, item_id: str):
    with publish_tasks_lock:
        task = publish_tasks.get(task_id)
        if not task:
            return None
        for item in task.get("items", []):
            if item.get("itemId") == item_id:
                return copy.deepcopy(item)
    return None


def _update_publish_task(task_id: str, **changes) -> None:
    with publish_tasks_lock:
        task = publish_tasks.get(task_id)
        if not task:
            return
        task.update(changes)
        task["updatedAt"] = _now_iso()
        _refresh_publish_task_counts_locked(task)
        _append_publish_task_snapshot_locked(task)


def _set_publish_task_items(task_id: str, items: list[dict]) -> None:
    with publish_tasks_lock:
        task = publish_tasks.get(task_id)
        if not task:
            return

        task["items"] = [_sanitize_publish_task_item(item) for item in items]
        task["updatedAt"] = _now_iso()
        _refresh_publish_task_counts_locked(task)
        _append_publish_task_snapshot_locked(task)


def _update_publish_task_item(
    task_id: str,
    item_id: str,
    *,
    status: str,
    progress: int,
    message: str,
    error_message: str = "",
) -> None:
    with publish_tasks_lock:
        task = publish_tasks.get(task_id)
        if not task:
            return

        for item in task.get("items", []):
            if item.get("itemId") != item_id:
                continue

            item["status"] = status
            item["progress"] = progress
            item["message"] = message
            item["errorMessage"] = error_message
            item["updatedAt"] = _now_iso()
            break
        else:
            return

        task["updatedAt"] = _now_iso()
        _refresh_publish_task_counts_locked(task)
        _append_publish_task_snapshot_locked(task)


def _mark_pending_publish_items_skipped(task_id: str, reason: str = "未执行", status: str = "skipped") -> None:
    with publish_tasks_lock:
        task = publish_tasks.get(task_id)
        if not task:
            return

        changed = False
        for item in task.get("items", []):
            if item.get("status") != "pending":
                continue
            item["status"] = status
            item["progress"] = 0
            item["message"] = reason
            item["updatedAt"] = _now_iso()
            changed = True

        if not changed:
            return

        task["updatedAt"] = _now_iso()
        _refresh_publish_task_counts_locked(task)
        _append_publish_task_snapshot_locked(task)


def _publish_task_has_items(task_id: str) -> bool:
    with publish_tasks_lock:
        task = publish_tasks.get(task_id)
        return bool(task and task.get("items"))


def _is_publish_task_pause_requested(task_id: str) -> bool:
    with publish_tasks_lock:
        task = publish_tasks.get(task_id)
        return bool(task and task.get("pauseRequested"))


def _request_publish_task_pause(task_id: str) -> bool:
    with publish_tasks_lock:
        task = publish_tasks.get(task_id)
        if not task:
            return False

        task["pauseRequested"] = True
        task["pauseRequestedAt"] = _now_iso()
        task["updatedAt"] = _now_iso()
        _append_publish_task_snapshot_locked(task)
        return True


def _ai_publish_upload_dir(base_dir: Path) -> Path:
    upload_dir = Path(base_dir) / "tmp" / AI_PUBLISH_UPLOAD_DIRNAME
    upload_dir.mkdir(parents=True, exist_ok=True)
    return upload_dir


def _build_ai_publish_upload_response(
    relative_path: str,
    original_name: str,
    mime_type: str,
    size_bytes: int,
    category: str,
) -> dict:
    return {
        "relativePath": relative_path,
        "originalName": original_name,
        "mimeType": mime_type,
        "sizeBytes": size_bytes,
        "category": category,
    }


def _format_storage_size(size_bytes: int) -> str:
    size = float(max(int(size_bytes or 0), 0))
    units = ["B", "KB", "MB", "GB", "TB"]
    unit_index = 0
    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1
    if unit_index == 0:
        return f"{int(size)} {units[unit_index]}"
    return f"{size:.2f} {units[unit_index]}"


def _get_directory_usage(target_dir: Path, relative_path: str) -> dict:
    size_bytes = 0
    file_count = 0

    if target_dir.exists():
        for item in target_dir.rglob("*"):
            if item.is_file():
                file_count += 1
                try:
                    size_bytes += item.stat().st_size
                except OSError:
                    continue

    return {
        "relativePath": relative_path,
        "sizeBytes": size_bytes,
        "sizeLabel": _format_storage_size(size_bytes),
        "fileCount": file_count,
    }


def _clear_directory_contents(target_dir: Path) -> dict:
    removed_files = 0
    removed_bytes = 0

    if target_dir.exists():
        for item in sorted(target_dir.rglob("*"), key=lambda path: len(path.parts), reverse=True):
            if item.is_file():
                try:
                    removed_bytes += item.stat().st_size
                except OSError:
                    pass
                item.unlink(missing_ok=True)
                removed_files += 1
            elif item.is_dir():
                try:
                    item.rmdir()
                except OSError:
                    continue

    target_dir.mkdir(parents=True, exist_ok=True)
    return {
        "removedFiles": removed_files,
        "removedBytes": removed_bytes,
        "removedSizeLabel": _format_storage_size(removed_bytes),
    }


def _build_ai_publish_storage_payload(base_dir: Path) -> dict:
    ai_attachment_dir = Path(base_dir) / "tmp" / AI_PUBLISH_UPLOAD_DIRNAME
    work_dir = Path(base_dir) / "videoFile"
    return {
        "aiAttachments": _get_directory_usage(ai_attachment_dir, "tmp/ai_publish_uploads"),
        "workFiles": _get_directory_usage(work_dir, "videoFile"),
    }


def _save_ai_publish_upload(file_storage, base_dir: Path) -> dict:
    raw_original_name = str(getattr(file_storage, "filename", "") or "").strip()
    original_name = secure_filename(raw_original_name)
    extension = Path(raw_original_name).suffix.lower()

    if not raw_original_name or not extension:
        raise ValueError("请先选择附件文件")

    attachment_rule = AI_PUBLISH_ALLOWED_ATTACHMENT_EXTENSIONS.get(extension)
    if not attachment_rule:
        raise ValueError("仅支持图片、音频、视频附件")

    if not original_name:
        original_name = f"attachment{extension}"
    elif Path(original_name).suffix.lower() != extension:
        original_name = f"{Path(original_name).stem or 'attachment'}{extension}"

    file_bytes = file_storage.read()
    if not file_bytes:
        raise ValueError("上传附件不能为空")
    if len(file_bytes) > int(attachment_rule["maxBytes"]):
        if attachment_rule["category"] == "image":
            raise ValueError("图片大小不能超过 10MB")
        if attachment_rule["category"] == "audio":
            raise ValueError("音频大小不能超过 50MB")
        raise ValueError("视频大小不能超过 200MB")

    mime_type = str(attachment_rule["mimeType"])
    category = str(attachment_rule["category"])
    upload_dir = _ai_publish_upload_dir(base_dir)
    stored_name = f"{uuid.uuid4().hex}{extension}"
    target_path = upload_dir / stored_name
    target_path.write_bytes(file_bytes)
    relative_path = str(Path("tmp") / AI_PUBLISH_UPLOAD_DIRNAME / stored_name).replace("\\", "/")
    return _build_ai_publish_upload_response(
        relative_path,
        raw_original_name,
        mime_type,
        len(file_bytes),
        category,
    )


def _resolve_ai_publish_upload_path(base_dir: Path, relative_path: str) -> Path:
    upload_root = _ai_publish_upload_dir(base_dir).resolve()
    candidate = (Path(base_dir) / relative_path).resolve()
    if not candidate.is_relative_to(upload_root):
        raise ValueError("AI 图片附件路径无效")
    if not candidate.exists():
        raise ValueError("AI 图片附件不存在或已被清理")
    return candidate


def _build_data_url_from_attachment(base_dir: Path, attachment: dict) -> str:
    existing_data_url = str(attachment.get("dataUrl") or attachment.get("data_url") or "").strip()
    if existing_data_url:
        return existing_data_url

    relative_path = str(attachment.get("relativePath") or attachment.get("relative_path") or "").strip()
    if not relative_path:
        raise ValueError("AI 图片附件缺少 relativePath")

    file_path = _resolve_ai_publish_upload_path(base_dir, relative_path)
    mime_type = str(attachment.get("mimeType") or attachment.get("mime_type") or "").strip() or mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
    encoded = base64.b64encode(file_path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def _hydrate_ai_publish_messages(messages, base_dir: Path) -> list[dict]:
    hydrated_messages = []
    for message in _strip_ai_publish_history_attachments(normalize_chat_messages(messages)):
        attachments = []
        for attachment in message.get("attachments") or []:
            hydrated_attachment = dict(attachment)
            relative_path = str(attachment.get("relativePath") or attachment.get("relative_path") or "").strip()
            file_path = _resolve_ai_publish_upload_path(base_dir, relative_path) if relative_path else None
            if file_path is not None:
                hydrated_attachment["localPath"] = str(file_path)

            mime_type = str(attachment.get("mimeType") or attachment.get("mime_type") or "").strip().lower()
            existing_data_url = str(attachment.get("dataUrl") or attachment.get("data_url") or "").strip()
            if existing_data_url or mime_type.startswith("image/") or file_path is None:
                hydrated_attachment["dataUrl"] = _build_data_url_from_attachment(base_dir, attachment)
            attachments.append(hydrated_attachment)
        hydrated_messages.append(
            {
                "role": message["role"],
                "content": message.get("content") or "",
                "attachments": attachments,
            }
        )
    return hydrated_messages


def _strip_ai_publish_history_attachments(messages: list[dict]) -> list[dict]:
    if not isinstance(messages, list):
        return []

    last_user_index = -1
    for index, message in enumerate(messages):
        if str(message.get("role") or "").strip() == "user":
            last_user_index = index

    if last_user_index < 0:
        return [dict(message) for message in messages]

    trimmed_messages = []
    for index, message in enumerate(messages):
        normalized_message = {
            "role": message.get("role") or "",
            "content": message.get("content") or "",
            "attachments": list(message.get("attachments") or []),
        }
        if index != last_user_index:
            normalized_message["attachments"] = []
        trimmed_messages.append(normalized_message)
    return trimmed_messages


def _should_trigger_ai_publish_analysis(messages) -> bool:
    latest_user_text = ""
    for message in reversed(list(messages or [])):
        if not isinstance(message, dict):
            continue
        if str(message.get("role") or "").strip() != "user":
            continue
        latest_user_text = str(message.get("content") or "").strip()
        break

    if not latest_user_text:
        return False

    normalized_text = re.sub(r"\s+", "", latest_user_text)
    publish_patterns = (
        r"(帮我|给我|需要|想要|我要|准备|计划|安排).{0,8}(发布|发到|发布到|同步发|定时发)",
        r"(发布任务|定时发布|安排发布|同步发布|帮我发|帮我安排发|需要发布)",
        r"(发布|发到|发布到).{0,20}(抖音|视频号|小红书|快手|账号|平台|作品|视频|图文)",
    )
    return any(re.search(pattern, normalized_text) for pattern in publish_patterns)


def _prune_account_validation_tasks_locked() -> None:
    if len(account_validation_tasks) <= MAX_ACCOUNT_VALIDATION_TASK_RECORDS:
        return

    finished_ids = [
        task_id
        for task_id, task in account_validation_tasks.items()
        if task.get("status") in {"success", "error"}
    ]
    finished_ids.sort(key=lambda task_id: account_validation_tasks[task_id].get("createdAt", ""))
    while len(account_validation_tasks) > MAX_ACCOUNT_VALIDATION_TASK_RECORDS and finished_ids:
        account_validation_tasks.pop(finished_ids.pop(0), None)


def _serialize_account_validation_task(task: dict | None):
    if not task:
        return None

    return {
        "taskId": task["taskId"],
        "status": task["status"],
        "message": task.get("message"),
        "createdAt": task.get("createdAt"),
        "updatedAt": task.get("updatedAt"),
        "startedAt": task.get("startedAt"),
        "finishedAt": task.get("finishedAt"),
        "total": task.get("total", 0),
        "completed": task.get("completed", 0),
        "items": [dict(item) for item in task.get("items", [])],
    }


def _get_account_validation_task_snapshot(task_id: str):
    with account_validation_tasks_lock:
        return _serialize_account_validation_task(account_validation_tasks.get(task_id))


def _get_account_validation_task_state(task_id: str):
    with account_validation_tasks_lock:
        task = account_validation_tasks.get(task_id)
        return copy.deepcopy(task) if task else None


def _append_account_validation_task_snapshot_locked(task: dict) -> None:
    task["eventSeq"] = int(task.get("eventSeq", 0)) + 1
    task.setdefault("events", []).append(
        {
            "seq": task["eventSeq"],
            "type": "task-snapshot",
            "createdAt": _now_iso(),
            "data": _serialize_account_validation_task(task),
        }
    )
    if len(task["events"]) > MAX_ACCOUNT_VALIDATION_TASK_EVENT_RECORDS:
        task["events"] = task["events"][-MAX_ACCOUNT_VALIDATION_TASK_EVENT_RECORDS:]


def _create_account_validation_task(rows_list) -> dict:
    task = {
        "taskId": uuid.uuid4().hex,
        "status": "queued",
        "message": "account validation task created",
        "createdAt": _now_iso(),
        "updatedAt": _now_iso(),
        "startedAt": None,
        "finishedAt": None,
        "total": len(rows_list),
        "completed": 0,
        "items": [
            {
                "id": row[0],
                "type": row[1],
                "filePath": row[2],
                "userName": row[3],
                "status": int(row[4]) if row[4] is not None else 0,
                "avatarUrl": row[5] if len(row) > 5 else None,
                "phase": "pending",
            }
            for row in rows_list
        ],
    }

    with account_validation_tasks_lock:
        account_validation_tasks[task["taskId"]] = task
        _prune_account_validation_tasks_locked()
        _append_account_validation_task_snapshot_locked(task)
        return _serialize_account_validation_task(task)


def _update_account_validation_task(task_id: str, **changes) -> None:
    with account_validation_tasks_lock:
        task = account_validation_tasks.get(task_id)
        if not task:
            return
        task.update(changes)
        task["updatedAt"] = _now_iso()
        _append_account_validation_task_snapshot_locked(task)


def _update_account_validation_item(
    task_id: str,
    row_id: int,
    *,
    phase: str | None = None,
    status: int | None = None,
    avatar_url=None,
    account_name=None,
) -> None:
    with account_validation_tasks_lock:
        task = account_validation_tasks.get(task_id)
        if not task:
            return

        for item in task.get("items", []):
            if item.get("id") != row_id:
                continue

            previous_phase = item.get("phase")
            if phase is not None:
                item["phase"] = phase
            if status is not None:
                item["status"] = status
            if avatar_url is not None:
                item["avatarUrl"] = avatar_url
            if account_name is not None:
                item["userName"] = account_name

            if phase == "finished" and previous_phase != "finished":
                task["completed"] = min(task.get("completed", 0) + 1, task.get("total", 0))

            task["updatedAt"] = _now_iso()
            _append_account_validation_task_snapshot_locked(task)
            break


def _persist_account_status(
    database_path: Path,
    row_id: int,
    status_code: int,
    *,
    avatar_url=UNSET,
    account_name=UNSET,
) -> None:
    update_user_info_status(
        database_path,
        row_id,
        status_code,
        avatar_url=avatar_url,
        account_name=account_name,
    )


def _select_account_rows(database_path: Path, account_ids=None):
    ensure_user_info_schema_at_path(database_path)
    with sqlite3.connect(database_path) as conn:
        cursor = conn.cursor()
        if account_ids:
            placeholders = ",".join("?" for _ in account_ids)
            cursor.execute(
                f"""
                SELECT * FROM user_info
                WHERE id IN ({placeholders})
                ORDER BY id
                """,
                list(account_ids),
            )
        else:
            cursor.execute(
                """
                SELECT * FROM user_info
                ORDER BY id
                """
            )
        rows = cursor.fetchall()
    return [list(row) for row in rows]


async def _check_account_cookie_with_limit(row, semaphore: asyncio.Semaphore, on_start=None, on_finish=None):
    async with semaphore:
        if callable(on_start):
            on_start(row)

        status_code = 0
        avatar_url = row[5] if len(row) > 5 else None
        account_name = str(row[3] or "")
        try:
            if int(row[1]) in (1, 2, 3, 4):
                profile = await fetch_account_profile_from_cookie(
                    int(row[1]),
                    Path(BASE_DIR / "cookiesFile" / row[2]),
                    account_name=account_name,
                )
                status_code = 1 if profile.get("isValid") else 0
                if profile.get("name"):
                    account_name = profile["name"]
                if profile.get("avatarUrl"):
                    avatar_url = profile["avatarUrl"]
        except Exception as exc:
            print(f"account validation failed for row {row[0]}: {exc}")
            status_code = 0

        if callable(on_finish):
            on_finish(row, status_code, avatar_url, account_name)
        return row[0], status_code, avatar_url, account_name


async def _validate_account_rows(rows_list, concurrency: int = ACCOUNT_VALIDATION_CONCURRENCY):
    semaphore = asyncio.Semaphore(max(1, concurrency))
    tasks = [
        asyncio.create_task(_check_account_cookie_with_limit(row, semaphore))
        for row in rows_list
    ]
    if not tasks:
        return {}

    results = await asyncio.gather(*tasks)
    return {row_id: status_code for row_id, status_code, _, _ in results}


async def _run_account_validation_task_async(task_id: str, rows_list, database_path: Path) -> None:
    semaphore = asyncio.Semaphore(max(1, ACCOUNT_VALIDATION_CONCURRENCY))

    def on_start(row) -> None:
        _update_account_validation_item(task_id, row[0], phase="running")

    def on_finish(row, status_code: int, avatar_url: str | None, account_name: str | None) -> None:
        persist_avatar = avatar_url if avatar_url is not None else UNSET
        persist_account_name = account_name if account_name else UNSET
        _persist_account_status(
            database_path,
            row[0],
            status_code,
            avatar_url=persist_avatar,
            account_name=persist_account_name,
        )
        _update_account_validation_item(
            task_id,
            row[0],
            phase="finished",
            status=status_code,
            avatar_url=avatar_url,
            account_name=account_name,
        )

    tasks = [
        asyncio.create_task(
            _check_account_cookie_with_limit(
                row,
                semaphore,
                on_start=on_start,
                on_finish=on_finish,
            )
        )
        for row in rows_list
    ]

    if tasks:
        await asyncio.gather(*tasks)


def _run_account_validation_task(task_id: str, rows_list, database_path: Path) -> None:
    _update_account_validation_task(
        task_id,
        status="running",
        message="account validation task is running",
        startedAt=_now_iso(),
    )

    try:
        asyncio.run(_run_account_validation_task_async(task_id, rows_list, database_path))
        _update_account_validation_task(
            task_id,
            status="success",
            message="account validation task completed",
            finishedAt=_now_iso(),
        )
    except Exception as exc:
        print(f"account validation task failed: {exc}")
        _update_account_validation_task(
            task_id,
            status="error",
            message=str(exc),
            finishedAt=_now_iso(),
        )


def _build_publish_task_plan(mode: str, payload):
    if mode == "retry":
        if isinstance(payload, dict):
            return [payload]
        return []
    if mode == "batch":
        return build_publish_batch_plan(payload)
    return build_publish_plan(payload)


def _create_publish_progress_callback(task_id: str):
    def handle_progress(event: dict) -> None:
        event_type = str((event or {}).get("type") or "")
        if event_type == "plan-prepared":
            _set_publish_task_items(task_id, list(event.get("items") or []))
            return

        if event_type == "item-started":
            _update_publish_task_item(
                task_id,
                str(event.get("itemId") or ""),
                status="running",
                progress=68,
                message="发布中",
            )
            return

        if event_type == "item-finished":
            returncode = int(event.get("returncode") or 0)
            stderr = str(event.get("stderr") or "").strip()
            stdout = str(event.get("stdout") or "").strip()
            error_message = stderr or stdout
            _update_publish_task_item(
                task_id,
                str(event.get("itemId") or ""),
                status="success" if returncode == 0 else "error",
                progress=100 if returncode == 0 else 88,
                message="全部成功" if returncode == 0 else "上传失败",
                error_message=error_message,
            )

    return handle_progress


def _run_publish_task(task_id: str, mode: str, publish_callable, payload) -> None:
    _update_publish_task(
        task_id,
        status="running",
        message="publish task is running",
        startedAt=_now_iso(),
    )
    try:
        progress_callback = _create_publish_progress_callback(task_id)
        result = publish_callable(
            payload,
            progress_callback=progress_callback,
            should_stop=lambda: _is_publish_task_pause_requested(task_id),
        )
        if _is_publish_task_pause_requested(task_id):
            _mark_pending_publish_items_skipped(task_id, reason="已暂停", status="paused")
            _update_publish_task(
                task_id,
                status="paused",
                message="publish task paused",
                finishedAt=_now_iso(),
                result=result,
            )
            return
        _update_publish_task(
            task_id,
            status="success",
            message="publish task completed",
            finishedAt=_now_iso(),
            result=result,
        )
    except PublishBridgeError as exc:
        if not _publish_task_has_items(task_id):
            try:
                planned_items = _build_publish_task_plan(mode, payload)
                _set_publish_task_items(task_id, planned_items)
            except Exception:
                planned_items = []
        _mark_pending_publish_items_skipped(task_id)
        _update_publish_task(
            task_id,
            status="error",
            message=str(exc),
            finishedAt=_now_iso(),
            result=None,
            statusCode=exc.status_code,
        )
        print(f"Async publish rejected: {exc}")
    except Exception as exc:
        if not _publish_task_has_items(task_id):
            try:
                planned_items = _build_publish_task_plan(mode, payload)
                _set_publish_task_items(task_id, planned_items)
            except Exception:
                planned_items = []
        _mark_pending_publish_items_skipped(task_id)
        _update_publish_task(
            task_id,
            status="error",
            message=str(exc),
            finishedAt=_now_iso(),
            result=None,
            statusCode=500,
        )
        print(f"Async publish failed: {exc}")


def _submit_publish_task(mode: str, payload, publish_callable, *, tab_count: int = 1) -> dict:
    with publish_tasks_lock:
        has_active_task = any(
            task.get("status") in {"queued", "running"} for task in publish_tasks.values()
        )
        if has_active_task:
            raise PublishBridgeError("Another publish task is already running", status_code=409)

        try:
            planned_items = _build_publish_task_plan(mode, payload)
        except Exception as exc:
            print(f"Publish task plan initialization failed: {exc}")
            planned_items = []

        task_id = uuid.uuid4().hex
        task = {
            "taskId": task_id,
            "mode": mode,
            "tabCount": tab_count,
            "status": "queued",
            "message": "publish task created",
            "createdAt": _now_iso(),
            "updatedAt": _now_iso(),
            "startedAt": None,
            "finishedAt": None,
            "result": None,
            "items": [_sanitize_publish_task_item(item) for item in planned_items],
            "eventSeq": 0,
            "events": [],
            "totalItems": 0,
            "completedItems": 0,
            "pendingItems": 0,
            "runningItems": 0,
            "successItems": 0,
            "errorItems": 0,
            "skippedItems": 0,
            "pausedItems": 0,
            "pauseRequested": False,
            "pauseRequestedAt": None,
        }
        _refresh_publish_task_counts_locked(task)
        _append_publish_task_snapshot_locked(task)
        publish_tasks[task_id] = task
        _prune_publish_tasks_locked()

    thread = threading.Thread(
        target=_run_publish_task,
        args=(task_id, mode, publish_callable, payload),
        daemon=True,
    )
    thread.start()
    return _serialize_publish_task(task)


def _prune_ai_publish_tasks_locked() -> None:
    if len(ai_publish_tasks) <= MAX_AI_PUBLISH_TASK_RECORDS:
        return

    finished_ids = [
        task_id
        for task_id, task in ai_publish_tasks.items()
        if task.get("status") in {"success", "error"}
    ]
    finished_ids.sort(key=lambda task_id: ai_publish_tasks[task_id].get("createdAt", ""))
    while len(ai_publish_tasks) > MAX_AI_PUBLISH_TASK_RECORDS and finished_ids:
        ai_publish_tasks.pop(finished_ids.pop(0), None)


def _serialize_ai_publish_task(task: dict | None):
    if not task:
        return None

    return {
        "taskId": task["taskId"],
        "conversationId": task.get("conversationId"),
        "status": task.get("status"),
        "message": task.get("message"),
        "createdAt": task.get("createdAt"),
        "updatedAt": task.get("updatedAt"),
        "startedAt": task.get("startedAt"),
        "finishedAt": task.get("finishedAt"),
        "model": task.get("model"),
        "result": copy.deepcopy(task.get("result")),
    }


def _append_ai_publish_event_locked(task: dict, event_type: str, data) -> None:
    task["eventSeq"] = int(task.get("eventSeq", 0)) + 1
    task.setdefault("events", []).append(
        {
            "seq": task["eventSeq"],
            "type": event_type,
            "createdAt": _now_iso(),
            "data": copy.deepcopy(data),
        }
    )
    if len(task["events"]) > MAX_AI_PUBLISH_TASK_EVENT_RECORDS:
        task["events"] = task["events"][-MAX_AI_PUBLISH_TASK_EVENT_RECORDS:]


def _append_ai_publish_snapshot_locked(task: dict) -> None:
    _append_ai_publish_event_locked(task, "task-snapshot", _serialize_ai_publish_task(task))


def _get_ai_publish_task_state(task_id: str):
    with ai_publish_tasks_lock:
        task = ai_publish_tasks.get(task_id)
        return copy.deepcopy(task) if task else None


def _update_ai_publish_task(task_id: str, **changes):
    with ai_publish_tasks_lock:
        task = ai_publish_tasks.get(task_id)
        if not task:
            return None
        task.update(changes)
        task["updatedAt"] = _now_iso()
        _append_ai_publish_snapshot_locked(task)
        return _serialize_ai_publish_task(task)


def _append_ai_publish_delta(task_id: str, delta: str) -> None:
    with ai_publish_tasks_lock:
        task = ai_publish_tasks.get(task_id)
        if not task:
            return
        task["assistantText"] = f"{task.get('assistantText') or ''}{delta}"
        task["updatedAt"] = _now_iso()
        _append_ai_publish_event_locked(task, "assistant-delta", {"delta": delta})


def _mark_ai_publish_assistant_finished(task_id: str) -> None:
    with ai_publish_tasks_lock:
        task = ai_publish_tasks.get(task_id)
        if not task:
            return
        task["message"] = "assistant reply completed"
        task["updatedAt"] = _now_iso()
        _append_ai_publish_event_locked(task, "assistant-finished", {"message": "done"})


def _set_ai_publish_task_preview(task_id: str, preview: dict) -> None:
    with ai_publish_tasks_lock:
        task = ai_publish_tasks.get(task_id)
        if not task:
            return
        task["taskPreview"] = copy.deepcopy(preview)
        task["updatedAt"] = _now_iso()
        _append_ai_publish_event_locked(task, "task-preview", preview)


def _set_ai_publish_task_error(task_id: str, message: str) -> None:
    with ai_publish_tasks_lock:
        task = ai_publish_tasks.get(task_id)
        if not task:
            return
        task["status"] = "error"
        task["message"] = message
        task["finishedAt"] = _now_iso()
        task["updatedAt"] = _now_iso()
        task["result"] = {
            "assistantText": task.get("assistantText") or "",
            "taskPreview": copy.deepcopy(task.get("taskPreview")),
        }
        _append_ai_publish_event_locked(task, "task-error", {"message": message})
        _append_ai_publish_snapshot_locked(task)


def _run_ai_publish_chat_task(task_id: str, payload: dict) -> None:
    _update_ai_publish_task(
        task_id,
        status="running",
        message="ai publish task is running",
        startedAt=_now_iso(),
    )

    try:
        base_dir = Path(BASE_DIR)
        config = load_ai_publish_config(base_dir)
        model = str(payload.get("model") or config.get("model") or "").strip()
        incoming_messages = _hydrate_ai_publish_messages(payload.get("messages") or [], base_dir)
        chat_messages = [{"role": "system", "content": BASE_SYSTEM_PROMPT}, *incoming_messages]

        assistant_chunks = []
        for delta in stream_chat_completion(config, messages=chat_messages, model=model):
            assistant_chunks.append(delta)
            _append_ai_publish_delta(task_id, delta)

        assistant_text = "".join(assistant_chunks).strip()
        _mark_ai_publish_assistant_finished(task_id)
        task_preview = None
        if assistant_text and _should_trigger_ai_publish_analysis(incoming_messages):
            _update_ai_publish_task(
                task_id,
                status="running",
                message="analyzing publish preview",
            )
            context = load_ai_publish_context(base_dir)
            task_preview = analyze_publish_task(
                config,
                messages=incoming_messages,
                assistant_text=assistant_text,
                context=context,
                model=model,
            )
            if task_preview:
                _set_ai_publish_task_preview(task_id, task_preview)

        with ai_publish_tasks_lock:
            task = ai_publish_tasks.get(task_id)
            if task:
                task["status"] = "success"
                task["message"] = "ai publish task completed"
                task["finishedAt"] = _now_iso()
                task["updatedAt"] = _now_iso()
                task["result"] = {
                    "assistantText": assistant_text,
                    "taskPreview": copy.deepcopy(task_preview),
                }
                _append_ai_publish_event_locked(task, "task-finished", {"message": "done"})
                _append_ai_publish_snapshot_locked(task)
    except Exception as exc:
        _set_ai_publish_task_error(task_id, str(exc))


def _submit_ai_publish_chat_task(payload: dict) -> dict:
    conversation_id = str(payload.get("conversationId") or uuid.uuid4().hex).strip() or uuid.uuid4().hex
    model = str(payload.get("model") or "").strip()

    with ai_publish_tasks_lock:
        task_id = uuid.uuid4().hex
        task = {
            "taskId": task_id,
            "conversationId": conversation_id,
            "status": "queued",
            "message": "ai publish task created",
            "createdAt": _now_iso(),
            "updatedAt": _now_iso(),
            "startedAt": None,
            "finishedAt": None,
            "model": model,
            "assistantText": "",
            "taskPreview": None,
            "result": None,
            "eventSeq": 0,
            "events": [],
        }
        _append_ai_publish_snapshot_locked(task)
        ai_publish_tasks[task_id] = task
        _prune_ai_publish_tasks_locked()

    thread = threading.Thread(
        target=_run_ai_publish_chat_task,
        args=(task_id, dict(payload)),
        daemon=True,
    )
    thread.start()
    return _serialize_ai_publish_task(task)


def _build_ai_publish_confirm_payload(task_data: dict) -> dict:
    if not isinstance(task_data, dict):
        raise PublishBridgeError("AI 发布任务格式无效", status_code=400)

    accounts = [item for item in (task_data.get("accounts") or []) if isinstance(item, dict)]
    works = [item for item in (task_data.get("works") or []) if isinstance(item, dict)]
    title = str(task_data.get("title") or "").strip()
    content = str(task_data.get("content") or "").strip()
    tags = [str(item).strip() for item in (task_data.get("tags") or []) if str(item).strip()]
    schedule_type = str(task_data.get("scheduleType") or "now").strip().lower()
    schedule_time = str(task_data.get("scheduleTime") or "").strip()

    account_ids = []
    for account in accounts:
        try:
            account_ids.append(int(account.get("id")))
        except (TypeError, ValueError) as exc:
            raise PublishBridgeError("AI 任务中的账号 ID 无效", status_code=400) from exc

    if not account_ids:
        raise PublishBridgeError("AI 任务缺少发布账号", status_code=400)
    if not works:
        raise PublishBridgeError("AI 任务缺少发布作品", status_code=400)
    if not title:
        raise PublishBridgeError("AI 任务缺少标题", status_code=400)

    normalized_works = []
    for work in works:
        kind = str(work.get("kind") or "video").strip().lower() or "video"
        if kind == "note":
            file_paths = [str(item).strip() for item in (work.get("filePaths") or []) if str(item).strip()]
            if not file_paths:
                raise PublishBridgeError("AI 图文任务缺少 filePaths", status_code=400)
            normalized_works.append({"kind": "note", "filePaths": file_paths})
            continue

        file_path = str(work.get("filePath") or "").strip()
        if not file_path:
            raise PublishBridgeError("AI 视频任务缺少 filePath", status_code=400)
        normalized_works.append({"kind": "video", "filePath": file_path})

    payload = {
        "accountIds": account_ids,
        "works": normalized_works,
        "title": title,
        "content": content,
        "tags": tags,
        "enableTimer": 1 if schedule_type == "scheduled" and schedule_time else 0,
        "headless": True,
    }
    if schedule_type == "scheduled" and schedule_time:
        payload["scheduleTime"] = schedule_time
    return payload

# 处理所有静态资源请求（未来打包用）
@app.route('/assets/<filename>')
def custom_static(filename):
    return send_from_directory(os.path.join(current_dir, 'assets'), filename)

# 处理 favicon.ico 静态资源（未来打包用）
@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(current_dir, 'assets'), 'vite.svg')

@app.route('/vite.svg')
def vite_svg():
    return send_from_directory(os.path.join(current_dir, 'assets'), 'vite.svg')

# （未来打包用）
@app.route('/')
def index():  # put application's code here
    return send_from_directory(current_dir, 'index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({
            "code": 400,
            "data": None,
            "msg": "No file part in the request"
        }), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({
            "code": 400,
            "data": None,
            "msg": "No selected file"
        }), 400
    try:
        # 保存文件到指定位置
        uuid_v1 = uuid.uuid1()
        print(f"UUID v1: {uuid_v1}")
        video_dir = Path(BASE_DIR / "videoFile")
        video_dir.mkdir(parents=True, exist_ok=True)
        filepath = video_dir / f"{uuid_v1}_{file.filename}"
        file.save(filepath)
        return jsonify({"code":200,"msg": "File uploaded successfully", "data": f"{uuid_v1}_{file.filename}"}), 200
    except Exception as e:
        return jsonify({"code":500,"msg": str(e),"data":None}), 500

@app.route('/getFile', methods=['GET'])
def get_file():
    # 获取 filename 参数
    filename = request.args.get('filename')

    if not filename:
        return jsonify({"code": 400, "msg": "filename is required", "data": None}), 400

    # 防止路径穿越攻击
    if '..' in filename or filename.startswith('/'):
        return jsonify({"code": 400, "msg": "Invalid filename", "data": None}), 400

    # 拼接完整路径
    file_path = str(Path(BASE_DIR / "videoFile"))

    # 返回文件
    return send_from_directory(file_path,filename)


@app.route('/uploadSave', methods=['POST'])
def upload_save():
    if 'file' not in request.files:
        return jsonify({
            "code": 400,
            "data": None,
            "msg": "No file part in the request"
        }), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({
            "code": 400,
            "data": None,
            "msg": "No selected file"
        }), 400

    # 获取表单中的自定义文件名（可选）
    custom_filename = request.form.get('filename', None)
    if custom_filename:
        filename = custom_filename + "." + file.filename.split('.')[-1]
    else:
        filename = file.filename

    try:
        # 生成 UUID v1
        uuid_v1 = uuid.uuid1()
        print(f"UUID v1: {uuid_v1}")

        # 构造文件名和路径
        final_filename = f"{uuid_v1}_{filename}"
        video_dir = Path(BASE_DIR / "videoFile")
        video_dir.mkdir(parents=True, exist_ok=True)
        filepath = video_dir / f"{uuid_v1}_{filename}"

        # 保存文件
        file.save(filepath)

        with sqlite3.connect(Path(BASE_DIR / "db" / "database.db")) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                                INSERT INTO file_records (filename, filesize, file_path)
            VALUES (?, ?, ?)
                                ''', (filename, round(float(os.path.getsize(filepath)) / (1024 * 1024),2), final_filename))
            conn.commit()
            print("✅ 上传文件已记录")

        return jsonify({
            "code": 200,
            "msg": "File uploaded and saved successfully",
            "data": {
                "filename": filename,
                "filepath": final_filename
            }
        }), 200

    except Exception as e:
        print(f"Upload failed: {e}")
        return jsonify({
            "code": 500,
            "msg": f"upload failed: {e}",
            "data": None
        }), 500

@app.route('/getFiles', methods=['GET'])
def get_all_files():
    try:
        # 使用 with 自动管理数据库连接
        with sqlite3.connect(Path(BASE_DIR / "db" / "database.db")) as conn:
            conn.row_factory = sqlite3.Row  # 允许通过列名访问结果
            cursor = conn.cursor()

            # 查询所有记录
            cursor.execute("SELECT * FROM file_records")
            rows = cursor.fetchall()

            # 将结果转为字典列表，并提取UUID
            data = []
            for row in rows:
                row_dict = dict(row)
                # 从 file_path 中提取 UUID (文件名的第一部分，下划线前)
                if row_dict.get('file_path'):
                    file_path_parts = row_dict['file_path'].split('_', 1)  # 只分割第一个下划线
                    if len(file_path_parts) > 0:
                        row_dict['uuid'] = file_path_parts[0]  # UUID 部分
                    else:
                        row_dict['uuid'] = ''
                else:
                    row_dict['uuid'] = ''
                data.append(row_dict)

            return jsonify({
                "code": 200,
                "msg": "success",
                "data": data
            }), 200
    except Exception as e:
        return jsonify({
            "code": 500,
            "msg": str("get file failed!"),
            "data": None
        }), 500


@app.route("/getAccounts", methods=['GET'])
def getAccounts():
    """快速获取所有账号信息，不进行cookie验证"""
    try:
        database_path = Path(BASE_DIR / "db" / "database.db")
        ensure_user_info_schema_at_path(database_path)
        with sqlite3.connect(database_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
            SELECT * FROM user_info''')
            rows = cursor.fetchall()
            rows_list = [list(row) for row in rows]

            print("\n📋 当前数据表内容（快速获取）：")
            for row in rows:
                print(row)

            return jsonify(
                {
                    "code": 200,
                    "msg": None,
                    "data": rows_list
                }), 200
    except Exception as e:
        print(f"获取账号列表时出错: {str(e)}")
        return jsonify({
            "code": 500,
            "msg": f"获取账号列表失败: {str(e)}",
            "data": None
        }), 500


@app.route("/startAccountValidation", methods=["POST"])
def startAccountValidation():
    try:
        database_path = Path(BASE_DIR / "db" / "database.db")
        payload = request.get_json(silent=True) or {}
        account_ids = payload.get("accountIds")
        normalized_account_ids = []
        if isinstance(account_ids, list):
            for account_id in account_ids:
                try:
                    normalized_account_ids.append(int(account_id))
                except (TypeError, ValueError):
                    return jsonify({
                        "code": 400,
                        "msg": f"invalid account id: {account_id}",
                        "data": None,
                    }), 400

        rows_list = _select_account_rows(
            database_path,
            account_ids=normalized_account_ids or None,
        )

        task = _create_account_validation_task(rows_list)
        thread = threading.Thread(
            target=_run_account_validation_task,
            args=(task["taskId"], rows_list, database_path),
            daemon=True,
        )
        thread.start()

        return jsonify({
            "code": 200,
            "msg": "account validation task created",
            "data": task,
        }), 200
    except Exception as exc:
        print(f"start account validation failed: {exc}")
        return jsonify({
            "code": 500,
            "msg": f"start account validation failed: {exc}",
            "data": None,
        }), 500


@app.route("/accountValidationTasks/<task_id>/stream", methods=["GET"])
def stream_account_validation_task(task_id):
    task_state = _get_account_validation_task_state(task_id)
    if not task_state:
        return jsonify({
            "code": 404,
            "msg": "account validation task not found",
            "data": None,
        }), 404

    def event_stream():
        initial_state = _get_account_validation_task_state(task_id)
        if not initial_state:
            yield _format_sse_event("task-error", {"message": "account validation task not found"})
            return

        yield _format_sse_event(
            "task-snapshot",
            _serialize_account_validation_task(initial_state),
            event_id="snapshot",
        )
        last_seq = int(initial_state.get("eventSeq", 0))

        while True:
            latest_state = _get_account_validation_task_state(task_id)
            if not latest_state:
                yield _format_sse_event("task-error", {"message": "account validation task not found"})
                break

            new_events = [
                event
                for event in latest_state.get("events", [])
                if int(event.get("seq", 0)) > last_seq
            ]
            if new_events:
                for event in new_events:
                    last_seq = int(event.get("seq", 0))
                    yield _format_sse_event(
                        str(event.get("type") or "task-snapshot"),
                        event.get("data"),
                        event_id=last_seq,
                    )
                continue

            if latest_state.get("status") in {"success", "error"}:
                break

            yield ": keep-alive\n\n"
            time.sleep(1.0)

    response = Response(event_stream(), mimetype="text/event-stream")
    response.headers["Cache-Control"] = "no-cache"
    response.headers["X-Accel-Buffering"] = "no"
    response.headers["Content-Type"] = "text/event-stream; charset=utf-8"
    response.headers["Connection"] = "keep-alive"
    return response


@app.route("/getAccountValidationTask", methods=["GET"])
def getAccountValidationTask():
    task_id = request.args.get("taskId", "").strip()
    if not task_id:
        return jsonify({
            "code": 400,
            "msg": "taskId is required",
            "data": None,
        }), 400

    task = _get_account_validation_task_snapshot(task_id)
    if not task:
        return jsonify({
            "code": 404,
            "msg": "account validation task not found",
            "data": None,
        }), 404

    return jsonify({
        "code": 200,
        "msg": None,
        "data": task,
    }), 200


@app.route("/getValidAccounts",methods=['GET'])
async def getValidAccounts():
    with sqlite3.connect(Path(BASE_DIR / "db" / "database.db")) as conn:
        cursor = conn.cursor()
        cursor.execute('''
        SELECT * FROM user_info''')
        rows = cursor.fetchall()
        rows_list = [list(row) for row in rows]
        print("\n📋 当前数据表内容：")
        for row in rows:
            print(row)
        validation_results = await _validate_account_rows(rows_list)
        for row in rows_list:
            if not validation_results.get(row[0], False):
                row[4] = 0
                cursor.execute('''
                UPDATE user_info 
                SET status = ? 
                WHERE id = ?
                ''', (0,row[0]))
                conn.commit()
                print("✅ 用户状态已更新")
        for row in rows:
            print(row)
        return jsonify(
                        {
                            "code": 200,
                            "msg": None,
                            "data": rows_list
                        }),200

async def _get_valid_accounts_override():
    with sqlite3.connect(Path(BASE_DIR / "db" / "database.db")) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT * FROM user_info
            """
        )
        rows = cursor.fetchall()
        rows_list = [list(row) for row in rows]
        validation_results = await _validate_account_rows(rows_list)
        for row in rows_list:
            row[4] = validation_results.get(row[0], 0)
            cursor.execute(
                """
                UPDATE user_info
                SET status = ?
                WHERE id = ?
                """,
                (row[4], row[0]),
            )
        conn.commit()

        return jsonify(
            {
                "code": 200,
                "msg": None,
                "data": rows_list
            }
        ), 200


app.view_functions['getValidAccounts'] = _get_valid_accounts_override


@app.route('/deleteFile', methods=['GET'])
def delete_file():
    file_id = request.args.get('id')

    if not file_id or not file_id.isdigit():
        return jsonify({
            "code": 400,
            "msg": "Invalid or missing file ID",
            "data": None
        }), 400

    try:
        # 获取数据库连接
        with sqlite3.connect(Path(BASE_DIR / "db" / "database.db")) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # 查询要删除的记录
            cursor.execute("SELECT * FROM file_records WHERE id = ?", (file_id,))
            record = cursor.fetchone()

            if not record:
                return jsonify({
                    "code": 404,
                    "msg": "File not found",
                    "data": None
                }), 404

            record = dict(record)

            # 获取文件路径并删除实际文件
            file_path = Path(BASE_DIR / "videoFile" / record['file_path'])
            if file_path.exists():
                try:
                    file_path.unlink()  # 删除文件
                    print(f"✅ 实际文件已删除: {file_path}")
                except Exception as e:
                    print(f"⚠️ 删除实际文件失败: {e}")
                    # 即使删除文件失败，也要继续删除数据库记录，避免数据不一致
            else:
                print(f"⚠️ 实际文件不存在: {file_path}")

            # 删除数据库记录
            cursor.execute("DELETE FROM file_records WHERE id = ?", (file_id,))
            conn.commit()

        return jsonify({
            "code": 200,
            "msg": "File deleted successfully",
            "data": {
                "id": record['id'],
                "filename": record['filename']
            }
        }), 200

    except Exception as e:
        return jsonify({
            "code": 500,
            "msg": str("delete failed!"),
            "data": None
        }), 500

@app.route('/deleteAllFiles', methods=['POST'])
def delete_all_files():
    try:
        database_path = Path(BASE_DIR / "db" / "database.db")
        video_dir = Path(BASE_DIR / "videoFile")
        video_root = video_dir.resolve()
        deleted_files = 0
        missing_files = 0
        skipped_files = 0

        with sqlite3.connect(database_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM file_records")
            records = [dict(row) for row in cursor.fetchall()]

            for record in records:
                file_path_value = str(record.get("file_path") or "").strip()
                if not file_path_value:
                    skipped_files += 1
                    continue

                file_path = (video_root / file_path_value).resolve()
                if not file_path.is_relative_to(video_root):
                    skipped_files += 1
                    print(f"⚠️ 跳过异常素材路径: {file_path_value}")
                    continue

                if file_path.exists() and file_path.is_file():
                    try:
                        file_path.unlink()
                        deleted_files += 1
                        print(f"✅ 实际文件已删除: {file_path}")
                    except Exception as exc:
                        skipped_files += 1
                        print(f"⚠️ 删除实际文件失败: {exc}")
                else:
                    missing_files += 1
                    print(f"⚠️ 实际文件不存在: {file_path}")

            cursor.execute("DELETE FROM file_records")
            conn.commit()

        return jsonify({
            "code": 200,
            "msg": "All files deleted successfully",
            "data": {
                "deletedRecords": len(records),
                "deletedFiles": deleted_files,
                "missingFiles": missing_files,
                "skippedFiles": skipped_files,
            }
        }), 200

    except Exception as e:
        print(f"delete all files failed: {e}")
        return jsonify({
            "code": 500,
            "msg": "delete all files failed!",
            "data": None
        }), 500

@app.route('/deleteAccount', methods=['GET'])
def delete_account():
    account_id = request.args.get('id')

    if not account_id or not account_id.isdigit():
        return jsonify({
            "code": 400,
            "msg": "Invalid or missing account ID",
            "data": None
        }), 400

    account_id = int(account_id)

    try:
        # 获取数据库连接
        with sqlite3.connect(Path(BASE_DIR / "db" / "database.db")) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # 查询要删除的记录
            cursor.execute("SELECT * FROM user_info WHERE id = ?", (account_id,))
            record = cursor.fetchone()

            if not record:
                return jsonify({
                    "code": 404,
                    "msg": "account not found",
                    "data": None
                }), 404

            record = dict(record)

            # 删除关联的cookie文件
            if record.get('filePath'):
                cookie_file_path = Path(BASE_DIR / "cookiesFile" / record['filePath'])
                if cookie_file_path.exists():
                    try:
                        cookie_file_path.unlink()
                        print(f"✅ Cookie文件已删除: {cookie_file_path}")
                    except Exception as e:
                        print(f"⚠️ 删除Cookie文件失败: {e}")

            # 删除数据库记录
            cursor.execute("DELETE FROM user_info WHERE id = ?", (account_id,))
            conn.commit()

        return jsonify({
            "code": 200,
            "msg": "account deleted successfully",
            "data": None
        }), 200

    except Exception as e:
        return jsonify({
            "code": 500,
            "msg": f"delete failed: {str(e)}",
            "data": None
        }), 500


# SSE 登录接口
@app.route('/login')
def login():
    # 1 小红书 2 视频号 3 抖音 4 快手
    type = request.args.get('type')
    # 账号名
    id = request.args.get('id')

    # 模拟一个用于异步通信的队列
    status_queue = Queue()
    active_queues[id] = status_queue

    def on_close():
        print(f"清理队列: {id}")
        del active_queues[id]
    # 启动异步任务线程
    thread = threading.Thread(target=run_async_function, args=(type,id,status_queue), daemon=True)
    thread.start()
    response = Response(sse_stream(status_queue,), mimetype='text/event-stream')
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['X-Accel-Buffering'] = 'no'  # 关键：禁用 Nginx 缓冲
    response.headers['Content-Type'] = 'text/event-stream; charset=utf-8'
    response.headers['Connection'] = 'keep-alive'
    return response

@app.route('/postVideo', methods=['POST'])
def postVideo():
    # 获取JSON数据
    data = request.get_json()

    if not data:
        return jsonify({"code": 400, "msg": "请求数据不能为空", "data": None}), 400

    # 从JSON数据中提取fileList和accountList
    file_list = data.get('fileList', [])
    account_list = data.get('accountList', [])
    type = data.get('type')
    title = data.get('title')
    tags = data.get('tags')
    category = data.get('category')
    enableTimer = data.get('enableTimer')
    if category == 0:
        category = None
    productLink = data.get('productLink', '')
    productTitle = data.get('productTitle', '')
    thumbnail_path = data.get('thumbnail', '')
    is_draft = data.get('isDraft', False)  # 新增参数：是否保存为草稿

    videos_per_day = data.get('videosPerDay')
    daily_times = data.get('dailyTimes')
    start_days = data.get('startDays')

    # 参数校验
    if not file_list:
        return jsonify({"code": 400, "msg": "文件列表不能为空", "data": None}), 400
    if not account_list:
        return jsonify({"code": 400, "msg": "账号列表不能为空", "data": None}), 400
    if not type:
        return jsonify({"code": 400, "msg": "平台类型不能为空", "data": None}), 400
    if not title:
        return jsonify({"code": 400, "msg": "标题不能为空", "data": None}), 400

    # 打印获取到的数据（仅作为示例）
    print("File List:", file_list)
    print("Account List:", account_list)

    try:
        match type:
            case 1:
                post_video_xhs(title, file_list, tags, account_list, category, enableTimer, videos_per_day, daily_times,
                                   start_days)
            case 2:
                post_video_tencent(title, file_list, tags, account_list, category, enableTimer, videos_per_day, daily_times,
                                   start_days, is_draft)
            case 3:
                post_video_DouYin(title, file_list, tags, account_list, category, enableTimer, videos_per_day, daily_times,
                          start_days, thumbnail_path, productLink, productTitle)
            case 4:
                post_video_ks(title, file_list, tags, account_list, category, enableTimer, videos_per_day, daily_times,
                          start_days)
            case _:
                return jsonify({"code": 400, "msg": f"不支持的平台类型: {type}", "data": None}), 400

        # 返回响应给客户端
        return jsonify(
            {
                "code": 200,
                "msg": "发布任务已提交",
                "data": None
            }), 200
    except Exception as e:
        print(f"发布视频时出错: {str(e)}")
        return jsonify({
            "code": 500,
            "msg": f"发布失败: {str(e)}",
            "data": None
        }), 500


@app.route('/updateUserinfo', methods=['POST'])
def updateUserinfo():
    # 获取JSON数据
    data = request.get_json()

    # 从JSON数据中提取 type 和 userName
    user_id = data.get('id')
    type = data.get('type')
    userName = data.get('userName')
    try:
        # 获取数据库连接
        with sqlite3.connect(Path(BASE_DIR / "db" / "database.db")) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # 更新数据库记录
            cursor.execute('''
                           UPDATE user_info
                           SET type     = ?,
                               userName = ?
                           WHERE id = ?;
                           ''', (type, userName, user_id))
            conn.commit()

        return jsonify({
            "code": 200,
            "msg": "account update successfully",
            "data": None
        }), 200

    except Exception as e:
        return jsonify({
            "code": 500,
            "msg": str("update failed!"),
            "data": None
        }), 500

@app.route('/postVideoBatch', methods=['POST'])
def postVideoBatch():
    data_list = request.get_json()

    if not isinstance(data_list, list):
        return jsonify({"code": 400, "msg": "Expected a JSON array", "data": None}), 400
    for data in data_list:
        # 从JSON数据中提取fileList和accountList
        file_list = data.get('fileList', [])
        account_list = data.get('accountList', [])
        type = data.get('type')
        title = data.get('title')
        tags = data.get('tags')
        category = data.get('category')
        enableTimer = data.get('enableTimer')
        if category == 0:
            category = None
        productLink = data.get('productLink', '')
        productTitle = data.get('productTitle', '')
        is_draft = data.get('isDraft', False)

        videos_per_day = data.get('videosPerDay')
        daily_times = data.get('dailyTimes')
        start_days = data.get('startDays')
        # 打印获取到的数据（仅作为示例）
        print("File List:", file_list)
        print("Account List:", account_list)
        match type:
            case 1:
                post_video_xhs(title, file_list, tags, account_list, category, enableTimer, videos_per_day, daily_times,
                               start_days)
            case 2:
                post_video_tencent(title, file_list, tags, account_list, category, enableTimer, videos_per_day, daily_times,
                                   start_days, is_draft)
            case 3:
                post_video_DouYin(title, file_list, tags, account_list, category, enableTimer, videos_per_day, daily_times,
                          start_days, productLink, productTitle)
            case 4:
                post_video_ks(title, file_list, tags, account_list, category, enableTimer, videos_per_day, daily_times,
                          start_days)
    # 返回响应给客户端
    return jsonify(
        {
            "code": 200,
            "msg": None,
            "data": None
        }), 200

# Cookie文件上传API
def _post_video_cli():
    data = request.get_json()
    if not data:
        return jsonify({"code": 400, "msg": "request payload is required", "data": None}), 400

    try:
        task = _submit_publish_task("single", data, run_publish_payload, tab_count=1)
        return jsonify({
            "code": 200,
            "msg": "publish task created",
            "data": task,
        }), 200
    except PublishBridgeError as exc:
        print(f"CLI publish rejected: {exc}")
        return jsonify({
            "code": exc.status_code,
            "msg": f"publish failed: {exc}",
            "data": None,
        }), exc.status_code
    except Exception as exc:
        print(f"CLI publish failed: {exc}")
        return jsonify({
            "code": 500,
            "msg": f"publish failed: {exc}",
            "data": None,
        }), 500


def _post_video_batch_cli():
    data_list = request.get_json()
    if not isinstance(data_list, list):
        return jsonify({"code": 400, "msg": "Expected a JSON array", "data": None}), 400

    try:
        task = _submit_publish_task("batch", data_list, run_publish_batch, tab_count=len(data_list))
        return jsonify({
            "code": 200,
            "msg": "publish task created",
            "data": task,
        }), 200
    except PublishBridgeError as exc:
        print(f"CLI batch publish rejected: {exc}")
        return jsonify({
            "code": exc.status_code,
            "msg": f"publish failed: {exc}",
            "data": None,
        }), exc.status_code
    except Exception as exc:
        print(f"CLI batch publish failed: {exc}")
        return jsonify({
            "code": 500,
            "msg": f"publish failed: {exc}",
            "data": None,
        }), 500


app.view_functions['postVideo'] = _post_video_cli
app.view_functions['postVideoBatch'] = _post_video_batch_cli

@app.route('/uploadCookie', methods=['POST'])
def upload_cookie():
    try:
        if 'file' not in request.files:
            return jsonify({
                "code": 400,
                "msg": "没有找到Cookie文件",
                "data": None
            }), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({
                "code": 400,
                "msg": "Cookie文件名不能为空",
                "data": None
            }), 400

        if not file.filename.endswith('.json'):
            return jsonify({
                "code": 400,
                "msg": "Cookie文件必须是JSON格式",
                "data": None
            }), 400

        # 获取账号信息
        account_id = request.form.get('id')
        platform = request.form.get('platform')

        if not account_id or not platform:
            return jsonify({
                "code": 400,
                "msg": "缺少账号ID或平台信息",
                "data": None
            }), 400

        # 从数据库获取账号的文件路径
        with sqlite3.connect(Path(BASE_DIR / "db" / "database.db")) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('SELECT filePath FROM user_info WHERE id = ?', (account_id,))
            result = cursor.fetchone()

        if not result:
            return jsonify({
                "code": 500,
                "msg": "账号不存在",
                "data": None
            }), 404

        # 保存上传的Cookie文件到对应路径
        cookie_file_path = Path(BASE_DIR / "cookiesFile" / result['filePath'])
        cookie_file_path.parent.mkdir(parents=True, exist_ok=True)

        file.save(str(cookie_file_path))

        # 更新数据库中的账号信息（可选，比如更新更新时间）
        # 这里可以根据需要添加额外的处理逻辑

        return jsonify({
            "code": 200,
            "msg": "Cookie文件上传成功",
            "data": None
        }), 200

    except Exception as e:
        print(f"上传Cookie文件时出错: {str(e)}")
        return jsonify({
            "code": 500,
            "msg": f"上传Cookie文件失败: {str(e)}",
            "data": None
        }), 500


# Cookie文件下载API
@app.route('/downloadCookie', methods=['GET'])
def download_cookie():
    try:
        file_path = request.args.get('filePath')
        if not file_path:
            return jsonify({
                "code": 500,
                "msg": "缺少文件路径参数",
                "data": None
            }), 400

        # 验证文件路径的安全性，防止路径遍历攻击
        cookie_file_path = Path(BASE_DIR / "cookiesFile" / file_path).resolve()
        base_path = Path(BASE_DIR / "cookiesFile").resolve()

        if not cookie_file_path.is_relative_to(base_path):
            return jsonify({
                "code": 500,
                "msg": "非法文件路径",
                "data": None
            }), 400

        if not cookie_file_path.exists():
            return jsonify({
                "code": 500,
                "msg": "Cookie文件不存在",
                "data": None
            }), 404

        # 返回文件
        return send_from_directory(
            directory=str(cookie_file_path.parent),
            path=cookie_file_path.name,
            as_attachment=True
        )

    except Exception as e:
        print(f"下载Cookie文件时出错: {str(e)}")
        return jsonify({
            "code": 500,
            "msg": f"下载Cookie文件失败: {str(e)}",
            "data": None
        }), 500


# 包装函数：在线程中运行异步函数
@app.route('/taskProgressLogs', methods=['GET'])
def task_progress_logs():
    try:
        payload = build_log_dashboard()
        return jsonify({
            "code": 200,
            "msg": None,
            "data": payload,
        }), 200
    except Exception as exc:
        print(f"task progress logs failed: {exc}")
        return jsonify({
            "code": 500,
            "msg": f"获取日志看板失败: {exc}",
            "data": None,
        }), 500


@app.route('/taskProgressLogs/clear', methods=['POST'])
def clear_task_progress_log():
    try:
        payload = request.get_json(silent=True) or {}
        panel_id = payload.get("panelId")
        if not panel_id:
            return jsonify({
                "code": 400,
                "msg": "panelId 不能为空",
                "data": None,
            }), 400

        panel = clear_log_panel(panel_id)
        return jsonify({
            "code": 200,
            "msg": "日志已清理",
            "data": panel,
        }), 200
    except ValueError as exc:
        return jsonify({
            "code": 400,
            "msg": str(exc),
            "data": None,
        }), 400
    except Exception as exc:
        print(f"clear task progress log failed: {exc}")
        return jsonify({
            "code": 500,
            "msg": f"清理日志失败: {exc}",
            "data": None,
        }), 500


@app.route('/publishTasks/<task_id>', methods=['GET'])
def get_publish_task(task_id):
    task = _get_publish_task_snapshot(task_id)
    if not task:
        return jsonify({
            "code": 404,
            "msg": "publish task not found",
            "data": None,
        }), 404

    return jsonify({
        "code": 200,
        "msg": None,
        "data": task,
    }), 200


@app.route('/publishTasks/current', methods=['GET'])
def get_current_publish_task():
    task = _get_latest_publish_task_snapshot()
    return jsonify({
        "code": 200,
        "msg": None,
        "data": task,
    }), 200


@app.route('/publishTasks/<task_id>/pause', methods=['POST'])
def pause_publish_task(task_id):
    task = _get_publish_task_snapshot(task_id)
    if not task:
        return jsonify({
            "code": 404,
            "msg": "publish task not found",
            "data": None,
        }), 404

    if task.get("status") not in {"queued", "running"}:
        return jsonify({
            "code": 409,
            "msg": "publish task is not running",
            "data": task,
        }), 409

    _request_publish_task_pause(task_id)
    return jsonify({
        "code": 200,
        "msg": "pause requested",
        "data": _get_publish_task_snapshot(task_id),
    }), 200


@app.route('/publishTasks/<task_id>/clear', methods=['POST'])
def clear_publish_task(task_id):
    with publish_tasks_lock:
        task = publish_tasks.get(task_id)
        if not task:
            return jsonify({
                "code": 404,
                "msg": "publish task not found",
                "data": None,
            }), 404

        if task.get("status") in {"queued", "running"}:
            return jsonify({
                "code": 409,
                "msg": "running publish task cannot be cleared",
                "data": _serialize_publish_task(task),
            }), 409

        publish_tasks.pop(task_id, None)

    return jsonify({
        "code": 200,
        "msg": "publish task cleared",
        "data": None,
    }), 200


@app.route('/publishTasks/<task_id>/items/<item_id>/retry', methods=['POST'])
def retry_publish_task_item(task_id, item_id):
    item = _get_publish_task_item_state(task_id, item_id)
    if not item:
        return jsonify({
            "code": 404,
            "msg": "publish task item not found",
            "data": None,
        }), 404

    if item.get("status") != "error":
        return jsonify({
            "code": 409,
            "msg": "only failed publish task items can be retried",
            "data": None,
        }), 409

    retry_item = dict(item)
    retry_item["itemId"] = uuid.uuid4().hex
    retry_item["orderIndex"] = 0
    retry_item["taskIndex"] = 0
    retry_item["status"] = "pending"
    retry_item["progress"] = 0
    retry_item["message"] = "等待执行"
    retry_item["errorMessage"] = ""
    retry_item["updatedAt"] = _now_iso()

    try:
        task = _submit_publish_task(
            "retry",
            retry_item,
            lambda payload, progress_callback=None, should_stop=None: run_publish_plan_items(
                [payload],
                progress_callback=progress_callback,
                should_stop=should_stop,
            ),
            tab_count=1,
        )
        return jsonify({
            "code": 200,
            "msg": "publish retry task created",
            "data": task,
        }), 200
    except PublishBridgeError as exc:
        return jsonify({
            "code": exc.status_code,
            "msg": f"publish retry failed: {exc}",
            "data": None,
        }), exc.status_code


def _format_sse_event(event_type: str, payload, event_id=None) -> str:
    chunks = []
    if event_type:
        chunks.append(f"event: {event_type}")
    if event_id is not None:
        chunks.append(f"id: {event_id}")
    chunks.append(f"data: {json.dumps(payload, ensure_ascii=False)}")
    return "\n".join(chunks) + "\n\n"


@app.route("/aiPublish/config", methods=["GET"])
def get_ai_publish_config():
    config = load_ai_publish_config(Path(BASE_DIR))
    return jsonify({
        "code": 200,
        "msg": "ok",
        "data": serialize_ai_publish_config(config),
    }), 200


@app.route("/aiPublish/config", methods=["POST"])
def save_ai_publish_config_route():
    payload = request.get_json(silent=True) or {}
    config = save_ai_publish_config(payload, Path(BASE_DIR))
    return jsonify({
        "code": 200,
        "msg": "保存成功",
        "data": serialize_ai_publish_config(config),
    }), 200


@app.route("/aiPublish/config/test", methods=["POST"])
def test_ai_publish_config_route():
    payload = request.get_json(silent=True) or {}
    current = load_ai_publish_config(Path(BASE_DIR))
    config = {
        "provider": str(payload.get("provider") or current.get("provider") or "").strip(),
        "api_base": str(payload.get("apiBase") or payload.get("api_base") or current.get("api_base") or "").strip(),
        "api_key": str(payload.get("apiKey") or payload.get("api_key") or current.get("api_key") or "").strip(),
        "model": str(payload.get("model") or payload.get("defaultModel") or current.get("model") or "").strip(),
    }
    try:
        result = test_ai_publish_connection(config, model=config["model"])
        return jsonify({
            "code": 200,
            "msg": "连接成功",
            "data": result,
        }), 200
    except Exception as exc:
        return jsonify({
            "code": 400,
            "msg": str(exc),
            "data": None,
        }), 400


@app.route("/aiPublish/storage", methods=["GET"])
def get_ai_publish_storage_route():
    storage_payload = _build_ai_publish_storage_payload(Path(BASE_DIR))
    return jsonify({
        "code": 200,
        "msg": "ok",
        "data": storage_payload,
    }), 200


@app.route("/aiPublish/storage/cleanup", methods=["POST"])
def clear_ai_publish_storage_route():
    payload = request.get_json(silent=True) or {}
    target = str(payload.get("target") or "").strip()
    base_dir = Path(BASE_DIR)
    target_mapping = {
        "aiAttachments": (base_dir / "tmp" / AI_PUBLISH_UPLOAD_DIRNAME, "tmp/ai_publish_uploads"),
        "workFiles": (base_dir / "videoFile", "videoFile"),
    }

    target_config = target_mapping.get(target)
    if target_config is None:
        return jsonify({
            "code": 400,
            "msg": "invalid cleanup target",
            "data": None,
        }), 400

    target_dir, relative_path = target_config
    cleanup_result = _clear_directory_contents(target_dir)
    current_usage = _get_directory_usage(target_dir, relative_path)
    return jsonify({
        "code": 200,
        "msg": "cleanup finished",
        "data": {
            "target": target,
            **cleanup_result,
            "current": current_usage,
        },
    }), 200


@app.route("/aiPublish/uploads", methods=["POST"])
def upload_ai_publish_attachment():
    file_storage = request.files.get("file")
    if file_storage is None:
        return jsonify({
            "code": 400,
            "msg": "请先选择附件文件",
            "data": None,
        }), 400

    try:
        attachment = _save_ai_publish_upload(file_storage, Path(BASE_DIR))
        return jsonify({
            "code": 200,
            "msg": "上传成功",
            "data": attachment,
        }), 200
    except ValueError as exc:
        print(f"publish center ai generate rejected: {exc}")
        return jsonify({
            "code": 400,
            "msg": str(exc),
            "data": None,
        }), 400
    except Exception as exc:
        print(f"ai publish upload failed: {exc}")
        return jsonify({
            "code": 500,
            "msg": f"附件上传失败: {exc}",
            "data": None,
        }), 500


@app.route("/aiPublish/models", methods=["GET"])
def get_ai_publish_models():
    config = load_ai_publish_config(Path(BASE_DIR))
    return jsonify({
        "code": 200,
        "msg": "ok",
        "data": build_model_options(config),
    }), 200


@app.route("/aiPublish/publishCenter/generate", methods=["POST"])
def generate_publish_center_copy_route():
    payload = request.get_json(silent=True) or {}
    works = [item for item in (payload.get("works") or []) if isinstance(item, dict)]
    if not works:
        return jsonify({
            "code": 400,
            "msg": "works 不能为空",
            "data": None,
        }), 400

    config = load_ai_publish_config(Path(BASE_DIR))
    model = str(payload.get("model") or config.get("model") or "").strip() or None

    try:
        result = generate_publish_center_copy(
            config,
            works=works,
            base_dir=Path(BASE_DIR),
            platforms=payload.get("platforms") or [],
            account_names=payload.get("accounts") or [],
            model=model,
        )
        return jsonify({
            "code": 200,
            "msg": "ok",
            "data": result,
        }), 200
    except ValueError as exc:
        return jsonify({
            "code": 400,
            "msg": str(exc),
            "data": None,
        }), 400
    except Exception as exc:
        print(f"publish center ai generate failed: {exc}")
        return jsonify({
            "code": 500,
            "msg": f"AI 生成失败: {exc}",
            "data": None,
        }), 500


@app.route("/aiPublish/chat/start", methods=["POST"])
def start_ai_publish_chat():
    payload = request.get_json(silent=True) or {}
    messages = normalize_chat_messages(payload.get("messages") or [])
    if not messages:
        return jsonify({
            "code": 400,
            "msg": "messages 不能为空",
            "data": None,
        }), 400

    task = _submit_ai_publish_chat_task(payload)
    return jsonify({
        "code": 200,
        "msg": "started",
        "data": task,
    }), 200


@app.route("/aiPublish/chatTasks/<task_id>/stream", methods=["GET"])
def stream_ai_publish_chat_task(task_id):
    task_state = _get_ai_publish_task_state(task_id)
    if not task_state:
        return jsonify({
            "code": 404,
            "msg": "ai publish task not found",
            "data": None,
        }), 404

    def event_stream():
        initial_state = _get_ai_publish_task_state(task_id)
        if not initial_state:
            yield _format_sse_event("task-error", {"message": "ai publish task not found"})
            return

        yield _format_sse_event("task-snapshot", _serialize_ai_publish_task(initial_state), event_id="snapshot")
        last_seq = 0

        while True:
            latest_state = _get_ai_publish_task_state(task_id)
            if not latest_state:
                yield _format_sse_event("task-error", {"message": "ai publish task not found"})
                break

            new_events = [event for event in latest_state.get("events", []) if int(event.get("seq", 0)) > last_seq]
            if new_events:
                for event in new_events:
                    last_seq = int(event.get("seq", 0))
                    yield _format_sse_event(
                        str(event.get("type") or "task-snapshot"),
                        event.get("data"),
                        event_id=last_seq,
                    )
                continue

            if latest_state.get("status") in {"success", "error"}:
                break

            yield ": keep-alive\n\n"
            time.sleep(1.0)

    response = Response(event_stream(), mimetype="text/event-stream")
    response.headers["Cache-Control"] = "no-cache"
    response.headers["X-Accel-Buffering"] = "no"
    response.headers["Content-Type"] = "text/event-stream; charset=utf-8"
    response.headers["Connection"] = "keep-alive"
    return response


@app.route("/aiPublish/task/confirm", methods=["POST"])
def confirm_ai_publish_task():
    payload = request.get_json(silent=True) or {}
    task_payload = payload.get("task") or {}
    try:
        bridge_payload = _build_ai_publish_confirm_payload(task_payload)
        task = _submit_publish_task("single", bridge_payload, run_publish_payload, tab_count=1)
        return jsonify({
            "code": 200,
            "msg": "发布任务已启动",
            "data": {
                "publishTaskId": task.get("taskId"),
                "task": task,
            },
        }), 200
    except PublishBridgeError as exc:
        return jsonify({
            "code": exc.status_code,
            "msg": str(exc),
            "data": None,
        }), exc.status_code


@app.route('/publishTasks/<task_id>/stream', methods=['GET'])
def stream_publish_task(task_id):
    task_state = _get_publish_task_state(task_id)
    if not task_state:
        return jsonify({
            "code": 404,
            "msg": "publish task not found",
            "data": None,
        }), 404

    def event_stream():
        initial_state = _get_publish_task_state(task_id)
        if not initial_state:
            yield _format_sse_event("task-error", {"message": "publish task not found"})
            return

        yield _format_sse_event("task-snapshot", _serialize_publish_task(initial_state), event_id="snapshot")
        last_seq = 0

        while True:
            latest_state = _get_publish_task_state(task_id)
            if not latest_state:
                yield _format_sse_event("task-error", {"message": "publish task not found"})
                break

            new_events = [event for event in latest_state.get("events", []) if int(event.get("seq", 0)) > last_seq]
            if new_events:
                for event in new_events:
                    last_seq = int(event.get("seq", 0))
                    yield _format_sse_event(
                        str(event.get("type") or "task-snapshot"),
                        event.get("data"),
                        event_id=last_seq,
                    )
                continue

            if latest_state.get("status") in {"success", "error", "paused"}:
                break

            yield ": keep-alive\n\n"
            time.sleep(1.0)

    response = Response(event_stream(), mimetype="text/event-stream")
    response.headers["Cache-Control"] = "no-cache"
    response.headers["X-Accel-Buffering"] = "no"
    response.headers["Content-Type"] = "text/event-stream; charset=utf-8"
    response.headers["Connection"] = "keep-alive"
    return response


def run_async_function(type,id,status_queue):
    match type:
        case '1':
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(xiaohongshu_cookie_gen(id, status_queue))
            loop.close()
        case '2':
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(get_tencent_cookie(id,status_queue))
            loop.close()
        case '3':
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(douyin_cookie_gen(id,status_queue))
            loop.close()
        case '4':
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(get_ks_cookie(id,status_queue))
            loop.close()

# SSE 流生成器函数
def sse_stream(status_queue):
    while True:
        if not status_queue.empty():
            msg = status_queue.get()
            yield f"data: {msg}\n\n"
        else:
            # 避免 CPU 占满
            time.sleep(0.1)

def run_async_function(type,id,status_queue):
    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        loop.run_until_complete(run_login_flow(type, id, status_queue))
    except Exception as exc:
        print(f"Login task crashed for type={type}, account={id}: {exc}")
        status_queue.put("500")
    finally:
        loop.close()


def sse_stream(status_queue):
    while True:
        if not status_queue.empty():
            msg = status_queue.get()
            yield f"data: {msg}\n\n"
            if msg in {"200", "500"}:
                break
        else:
            time.sleep(0.1)


def _login_sse_bridge():
    platform_type = request.args.get("type")
    account_name = request.args.get("id")

    status_queue = Queue()
    active_queues[account_name] = status_queue

    thread = threading.Thread(
        target=run_async_function,
        args=(platform_type, account_name, status_queue),
        daemon=True,
    )
    thread.start()

    def stream():
        try:
            yield from sse_stream(status_queue)
        finally:
            print(f"娓呯悊闃熷垪: {account_name}")
            active_queues.pop(account_name, None)

    response = Response(stream(), mimetype="text/event-stream")
    response.headers["Cache-Control"] = "no-cache"
    response.headers["X-Accel-Buffering"] = "no"
    response.headers["Content-Type"] = "text/event-stream; charset=utf-8"
    response.headers["Connection"] = "keep-alive"
    return response


@app.route("/login/start", methods=["POST"])
def login_start():
    data = request.get_json(silent=True) or {}
    platform_type = str(data.get("type") or "")
    account_name = data.get("id") or data.get("name") or ""

    if not account_name:
        return jsonify({"code": 400, "msg": "账号名称不能为空", "data": None}), 400

    result = start_browser_login_session(platform_type, account_name)
    status_code = 200 if result.get("started") else 400
    return jsonify({"code": status_code, "msg": result.get("message"), "data": result}), status_code


@app.route("/account/open", methods=["POST"])
def open_account_browser():
    data = request.get_json(silent=True) or {}

    try:
        account_id = int(data.get("id"))
    except (TypeError, ValueError):
        return jsonify({"code": 400, "msg": "账号 ID 无效", "data": None}), 400

    database_path = Path(BASE_DIR / "db" / "database.db")
    ensure_user_info_schema_at_path(database_path)

    with sqlite3.connect(database_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            """
            SELECT id, type, filePath, userName
            FROM user_info
            WHERE id = ?
            """,
            (account_id,),
        ).fetchone()

    if row is None:
        return jsonify({"code": 404, "msg": "账号不存在", "data": None}), 404

    cookie_file = Path(BASE_DIR / "cookiesFile" / row["filePath"])
    result = start_account_browser_session(
        int(row["id"]),
        str(row["type"]),
        row["userName"],
        cookie_file,
    )
    status_code = 200 if result.get("started") else 400
    return jsonify({"code": status_code, "msg": result.get("message"), "data": result}), status_code


@app.route("/login/confirm", methods=["POST"])
def login_confirm():
    data = request.get_json(silent=True) or {}
    platform_type = str(data.get("type") or "")
    account_name = data.get("id") or data.get("name") or ""

    if not account_name:
        return jsonify({"code": 400, "msg": "账号名称不能为空", "data": None}), 400

    result = confirm_browser_login_session(platform_type, account_name)
    return jsonify({"code": 200, "msg": result.get("message"), "data": result}), 200


def _login_start_v2():
    data = request.get_json(silent=True) or {}
    platform_type = str(data.get("type") or "")
    session_id = str(data.get("sessionId") or data.get("id") or data.get("name") or "").strip()
    account_name = str(data.get("accountName") or data.get("name") or "").strip()
    account_id = data.get("accountId")

    try:
        account_id = int(account_id) if account_id is not None else None
    except (TypeError, ValueError):
        return jsonify({"code": 400, "msg": "账号 ID 无效", "data": None}), 400

    if not session_id:
        return jsonify({"code": 400, "msg": "缺少登录会话 ID", "data": None}), 400

    kwargs = {}
    if account_id is not None:
        kwargs["account_id"] = account_id
    if account_name:
        kwargs["account_name"] = account_name

    result = start_browser_login_session(platform_type, session_id, **kwargs)
    status_code = 200 if result.get("started") else 400
    return jsonify({"code": status_code, "msg": result.get("message"), "data": result}), status_code


def _login_confirm_v2():
    data = request.get_json(silent=True) or {}
    platform_type = str(data.get("type") or "")
    session_id = str(data.get("sessionId") or data.get("id") or data.get("name") or "").strip()
    account_name = str(data.get("accountName") or data.get("name") or "").strip()
    account_id = data.get("accountId")

    try:
        account_id = int(account_id) if account_id is not None else None
    except (TypeError, ValueError):
        return jsonify({"code": 400, "msg": "账号 ID 无效", "data": None}), 400

    if not session_id:
        return jsonify({"code": 400, "msg": "缺少登录会话 ID", "data": None}), 400

    kwargs = {}
    if account_id is not None:
        kwargs["account_id"] = account_id
    if account_name:
        kwargs["account_name"] = account_name

    result = confirm_browser_login_session(platform_type, session_id, **kwargs)
    return jsonify({"code": 200, "msg": result.get("message"), "data": result}), 200


app.view_functions["login_start"] = _login_start_v2
app.view_functions["login_confirm"] = _login_confirm_v2
app.view_functions["login"] = _login_sse_bridge

if __name__ == '__main__':
    app.run(host='0.0.0.0' ,port=5409)
