from __future__ import annotations

import argparse
import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed
import shutil
import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable

from conf import BASE_DIR

SCHEDULE_FORMAT = "%Y-%m-%d %H:%M"
VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".wmv", ".flv", ".mkv", ".m4v"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"}
PLATFORM_BY_TYPE = {
    1: "xiaohongshu",
    2: "weixin",
    3: "douyin",
    4: "kuaishou",
}
PLATFORM_TYPE_BY_NAME = {name: type_code for type_code, name in PLATFORM_BY_TYPE.items()}
REUSABLE_PUBLISH_PLATFORMS = {"douyin", "kuaishou", "xiaohongshu", "weixin"}
REUSABLE_PUBLISH_ACTIONS = {"upload-video", "upload-note"}
MAX_REUSABLE_CONSECUTIVE_FAILURES = 2


class PublishBridgeError(RuntimeError):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def _coerce_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _normalize_tags(raw_tags) -> list[str]:
    if not raw_tags:
        return []

    candidates = raw_tags.split(",") if isinstance(raw_tags, str) else raw_tags
    tags: list[str] = []
    for tag in candidates:
        cleaned = str(tag).strip().lstrip("#")
        if cleaned:
            tags.append(cleaned)
    return tags


def _normalize_titles(payload: dict, work_count: int) -> list[str]:
    raw_titles = payload.get("titles")
    if raw_titles is None:
        title = str(payload.get("title") or "").strip()
        if not title:
            raise PublishBridgeError("标题不能为空")
        return [title] * work_count if work_count > 1 else [title]

    titles = [str(item).strip() for item in raw_titles if str(item).strip()]
    if len(titles) != work_count:
        raise PublishBridgeError(f"标题行数必须和作品数一致：当前 {work_count} 个作品，需要 {work_count} 行标题")
    return titles


def _normalize_contents(payload: dict, work_count: int) -> list[str]:
    raw_contents = payload.get("contents")
    if raw_contents is None:
        content = str(payload.get("content") or payload.get("desc") or payload.get("description") or "").strip()
        return [content] * work_count if work_count > 1 else [content]

    if isinstance(raw_contents, str):
        contents = [line.strip() for line in raw_contents.splitlines() if line.strip()]
    else:
        contents = [str(item).strip() for item in raw_contents if str(item).strip()]

    if len(contents) != work_count:
        raise PublishBridgeError(f"文案行数必须和作品数一致：当前 {work_count} 个作品，需要 {work_count} 行文案")
    return contents


def _resolve_platform(platform_type) -> str:
    type_code = _coerce_int(platform_type, -1)
    platform = PLATFORM_BY_TYPE.get(type_code)
    if not platform:
        raise PublishBridgeError(f"不支持的平台类型: {platform_type}")
    return platform


def _resolve_media_path(file_path: str | Path, base_dir: Path) -> Path:
    candidate = Path(file_path)
    resolved = candidate if candidate.is_absolute() else base_dir / "videoFile" / candidate
    if not resolved.exists():
        raise PublishBridgeError(f"素材文件不存在: {resolved}")
    return resolved


def _is_video_path(file_path: Path) -> bool:
    return file_path.suffix.lower() in VIDEO_EXTENSIONS


def _is_image_path(file_path: Path) -> bool:
    return file_path.suffix.lower() in IMAGE_EXTENSIONS


def _parse_daily_time(raw_time) -> tuple[int, int]:
    if isinstance(raw_time, (int, float)):
        return int(raw_time), 0

    text = str(raw_time).strip()
    if not text:
        raise PublishBridgeError("发布时间不能为空")

    try:
        hour_text, minute_text = text.split(":", 1)
        hour = int(hour_text)
        minute = int(minute_text)
    except ValueError as exc:
        raise PublishBridgeError(f"无法解析发布时间: {raw_time}") from exc

    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise PublishBridgeError(f"发布时间超出范围: {raw_time}")
    return hour, minute


def _normalize_schedule_value(raw_time) -> str:
    if isinstance(raw_time, datetime):
        return raw_time.strftime(SCHEDULE_FORMAT)

    text = str(raw_time or "").strip()
    if not text:
        raise PublishBridgeError("scheduleTime 不能为空")

    for parser in (
        lambda value: datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None),
        lambda value: datetime.strptime(value, "%Y-%m-%d %H:%M:%S"),
        lambda value: datetime.strptime(value, "%Y-%m-%d %H:%M"),
        lambda value: datetime.strptime(value, "%Y/%m/%d %H:%M:%S"),
        lambda value: datetime.strptime(value, "%Y/%m/%d %H:%M"),
    ):
        try:
            return parser(text).strftime(SCHEDULE_FORMAT)
        except ValueError:
            continue

    raise PublishBridgeError(f"无法解析 scheduleTime: {raw_time}")


def _build_schedule_values(
    file_count: int,
    enable_timer,
    videos_per_day,
    daily_times,
    start_days,
    now_provider: Callable[[], datetime],
    explicit_schedule_time=None,
    explicit_schedule_times=None,
) -> list[str | None]:
    raw_explicit_values = explicit_schedule_times
    if raw_explicit_values is None and explicit_schedule_time:
        raw_explicit_values = [explicit_schedule_time]

    if raw_explicit_values:
        if not isinstance(raw_explicit_values, list):
            raw_explicit_values = [raw_explicit_values]
        normalized_values = [_normalize_schedule_value(item) for item in raw_explicit_values if str(item or "").strip()]
        if len(normalized_values) == 1 and file_count > 1:
            return normalized_values * file_count
        if len(normalized_values) != file_count:
            raise PublishBridgeError(f"scheduleTime 数量必须和作品数量一致：当前 {file_count} 个作品，需要 {file_count} 个时间点")
        return normalized_values

    if not enable_timer:
        return [None] * file_count

    current_time = now_provider()
    per_day = max(_coerce_int(videos_per_day, 1), 1)
    parsed_times = [_parse_daily_time(item) for item in (daily_times or ["10:00"])]
    if per_day > len(parsed_times):
        raise PublishBridgeError("每天发布时间点数量少于每天发布数量")

    normalized_start_days = max(_coerce_int(start_days, 0), 0)
    schedule_values: list[str | None] = []

    if normalized_start_days == 0 and file_count > 0:
        schedule_values.append(None)
        for index in range(1, file_count):
            scheduled_index = index - 1
            day_offset = scheduled_index // per_day + 1
            hour, minute = parsed_times[scheduled_index % per_day]
            publish_at = current_time.replace(hour=hour, minute=minute, second=0, microsecond=0) + timedelta(days=day_offset)
            schedule_values.append(publish_at.strftime(SCHEDULE_FORMAT))
        return schedule_values

    for index in range(file_count):
        day_offset = index // per_day + normalized_start_days
        hour, minute = parsed_times[index % per_day]
        publish_at = current_time.replace(hour=hour, minute=minute, second=0, microsecond=0) + timedelta(days=day_offset)
        schedule_values.append(publish_at.strftime(SCHEDULE_FORMAT))
    return schedule_values


def _lookup_account_name_from_db(platform: str, legacy_account_path: str | Path, base_dir: Path) -> str | None:
    database_path = base_dir / "db" / "database.db"
    if not database_path.exists():
        return None

    account_type = PLATFORM_TYPE_BY_NAME.get(platform)
    if account_type is None:
        return None

    legacy_name = Path(legacy_account_path).name
    try:
        with sqlite3.connect(database_path) as conn:
            cursor = conn.cursor()
            try:
                row = cursor.execute(
                    """
                    SELECT userName
                    FROM user_info
                    WHERE type = ? AND filePath = ?
                    ORDER BY id ASC
                    LIMIT 1
                    """,
                    (account_type, legacy_name),
                ).fetchone()
            finally:
                cursor.close()
    except sqlite3.Error:
        return None

    if not row:
        return None

    account_name = str(row[0] or "").strip()
    return account_name or None


def prepare_account_cookie_for_cli(
    platform: str,
    legacy_account_path: str | Path,
    base_dir: Path = BASE_DIR,
    account_name: str | None = None,
) -> str:
    legacy_path = Path(legacy_account_path)
    stem = legacy_path.stem
    prefix = f"{platform}_"

    resolved_account_name = str(account_name or "").strip()
    if not resolved_account_name:
        resolved_account_name = _lookup_account_name_from_db(platform, legacy_path.name, base_dir) or ""
    if not resolved_account_name:
        resolved_account_name = stem[len(prefix):] if stem.startswith(prefix) else stem

    candidates: list[Path] = []
    if legacy_path.is_absolute():
        candidates.append(legacy_path)
    else:
        candidates.append(base_dir / "cookiesFile" / legacy_path)
        candidates.append(base_dir / "cookies" / legacy_path)
        candidates.append(base_dir / "cookies" / f"{platform}_{resolved_account_name}.json")

    source_path = next((candidate for candidate in candidates if candidate.exists()), None)
    if source_path is None:
        raise PublishBridgeError(f"账号 Cookie 不存在: {legacy_account_path}")

    runtime_cookie = base_dir / "cookies" / f"{platform}_{resolved_account_name}.json"
    runtime_cookie.parent.mkdir(parents=True, exist_ok=True)
    if source_path.resolve() != runtime_cookie.resolve():
        shutil.copy2(source_path, runtime_cookie)
    return resolved_account_name


def _load_accounts_from_db(account_ids: list[int], base_dir: Path) -> list[dict]:
    database_path = base_dir / "db" / "database.db"
    if not database_path.exists():
        raise PublishBridgeError("账号数据库不存在，无法按账号自动识别平台", status_code=500)

    normalized_ids: list[int] = []
    for account_id in account_ids:
        try:
            normalized_ids.append(int(account_id))
        except (TypeError, ValueError) as exc:
            raise PublishBridgeError(f"无效的账号 ID: {account_id}") from exc

    if not normalized_ids:
        return []

    placeholders = ",".join("?" for _ in normalized_ids)
    try:
        with sqlite3.connect(database_path) as conn:
            cursor = conn.cursor()
            try:
                rows = cursor.execute(
                    f"""
                    SELECT id, type, filePath, userName
                    FROM user_info
                    WHERE id IN ({placeholders})
                    """,
                    normalized_ids,
                ).fetchall()
            finally:
                cursor.close()
    except sqlite3.Error as exc:
        raise PublishBridgeError(f"读取账号信息失败: {exc}", status_code=500) from exc

    row_map = {
        int(row[0]): {
            "id": int(row[0]),
            "type": int(row[1]),
            "filePath": str(row[2] or "").strip(),
            "userName": str(row[3] or "").strip(),
        }
        for row in rows
    }

    missing_ids = [account_id for account_id in normalized_ids if account_id not in row_map]
    if missing_ids:
        raise PublishBridgeError(f"未找到账号信息: {missing_ids}")

    return [row_map[account_id] for account_id in normalized_ids]


def _resolve_publish_accounts(payload: dict, base_dir: Path) -> list[dict]:
    account_ids = payload.get("accountIds") or []
    if account_ids:
        account_rows = _load_accounts_from_db(account_ids, base_dir)
        resolved_accounts: list[dict] = []
        for row in account_rows:
            platform = _resolve_platform(row["type"])
            resolved_accounts.append(
                {
                    "id": row["id"],
                    "platform": platform,
                    "account_name": prepare_account_cookie_for_cli(
                        platform,
                        row["filePath"],
                        base_dir=base_dir,
                        account_name=row["userName"],
                    ),
                    "file_path": row["filePath"],
                }
            )
        return resolved_accounts

    raw_accounts = payload.get("accountList") or []
    if not raw_accounts:
        raise PublishBridgeError("账号列表不能为空")

    platform = _resolve_platform(payload.get("type"))
    return [
        {
            "platform": platform,
            "account_name": prepare_account_cookie_for_cli(platform, legacy_account_path, base_dir=base_dir),
            "file_path": str(legacy_account_path),
        }
        for legacy_account_path in raw_accounts
    ]


def _build_video_command(
    *,
    platform: str,
    account_name: str,
    media_path: Path,
    title: str,
    payload: dict,
    schedule_value: str | None,
    tags: list[str],
    headless_enabled: bool,
) -> list[str]:
    command = [
        platform,
        "upload-video",
        "--account",
        account_name,
        "--file",
        str(media_path),
        "--title",
        title,
    ]

    description = str(payload.get("desc") or payload.get("description") or "").strip()
    if description:
        command.extend(["--desc", description])

    if tags:
        command.extend(["--tags", ",".join(tags)])

    if schedule_value:
        command.extend(["--schedule", schedule_value])

    if not headless_enabled:
        command.append("--headed")

    if platform == "douyin":
        product_link = str(payload.get("productLink") or "").strip()
        product_title = str(payload.get("productTitle") or "").strip()
        if product_link:
            command.extend(["--product-link", product_link])
        if product_title:
            command.extend(["--product-title", product_title])
        if payload.get("douyinSelfDeclaration"):
            command.append("--self-declaration")

    if platform == "weixin" and payload.get("isDraft"):
        command.append("--draft")

    return command


def _build_note_command(
    *,
    platform: str,
    account_name: str,
    media_paths: list[Path],
    title: str,
    payload: dict,
    note_content: str,
    schedule_value: str | None,
    tags: list[str],
    headless_enabled: bool,
) -> list[str]:
    if platform == "weixin":
        raise PublishBridgeError("视频号目前不支持图文发布")

    command = [
        platform,
        "upload-note",
        "--account",
        account_name,
        "--images",
        *[str(path) for path in media_paths],
        "--title",
        title,
    ]

    if note_content:
        command.extend(["--note", note_content])

    if tags:
        command.extend(["--tags", ",".join(tags)])

    if schedule_value:
        command.extend(["--schedule", schedule_value])

    if not headless_enabled:
        command.append("--headed")

    if platform == "douyin" and payload.get("douyinSelfDeclaration"):
        command.append("--self-declaration")

    return command


def _is_headless_enabled(payload: dict) -> bool:
    value = payload.get("headless")
    if value is None:
        return True
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"headed", "false", "0", "no", "off"}:
            return False
        if normalized in {"headless", "true", "1", "yes", "on"}:
            return True
    return bool(value)


def _build_media_label(media_paths: list[Path]) -> str:
    if not media_paths:
        return ""

    if len(media_paths) == 1:
        return media_paths[0].name

    return f"{media_paths[0].name} 等 {len(media_paths)} 项"


def _normalize_works(payload: dict, base_dir: Path) -> list[dict]:
    raw_works = payload.get("works")
    if raw_works:
        if not isinstance(raw_works, list):
            raise PublishBridgeError("作品列表格式不正确")

        normalized_works: list[dict] = []
        for index, raw_work in enumerate(raw_works):
            if not isinstance(raw_work, dict):
                raise PublishBridgeError(f"第 {index + 1} 个作品格式不正确")

            kind = str(raw_work.get("kind") or "").strip().lower()
            if kind == "video":
                raw_file_path = raw_work.get("filePath")
                if not raw_file_path:
                    raise PublishBridgeError(f"第 {index + 1} 个视频作品缺少文件路径")
                media_path = _resolve_media_path(raw_file_path, base_dir)
                if not _is_video_path(media_path):
                    raise PublishBridgeError(f"第 {index + 1} 个作品不是视频文件: {media_path.name}")
                normalized_works.append({"kind": "video", "media_paths": [media_path]})
                continue

            if kind == "note":
                raw_file_paths = raw_work.get("filePaths") or []
                if not raw_file_paths:
                    raise PublishBridgeError(f"第 {index + 1} 个图文作品缺少图片文件")
                media_paths = [_resolve_media_path(item, base_dir) for item in raw_file_paths]
                if not all(_is_image_path(path) for path in media_paths):
                    raise PublishBridgeError(f"第 {index + 1} 个图文作品包含非图片文件")
                normalized_works.append({"kind": "note", "media_paths": media_paths})
                continue

            raise PublishBridgeError(f"第 {index + 1} 个作品类型不支持: {raw_work.get('kind')}")
        return normalized_works

    raw_files = payload.get("fileList") or []
    if not raw_files:
        raise PublishBridgeError("文件列表不能为空")

    media_paths = [_resolve_media_path(item, base_dir) for item in raw_files]
    non_video_files = [path for path in media_paths if not _is_video_path(path)]
    if non_video_files:
        raise PublishBridgeError(f"当前版本只支持视频发布，暂不支持该素材类型: {non_video_files[0].name}")

    return [{"kind": "video", "media_paths": [path]} for path in media_paths]


def build_publish_plan(
    payload: dict,
    *,
    base_dir: Path = BASE_DIR,
    now_provider: Callable[[], datetime] = datetime.now,
    order_offset: int = 0,
    task_index: int = 0,
) -> list[dict]:
    if not isinstance(payload, dict):
        raise PublishBridgeError("鍙戝竷璇锋眰蹇呴』鏄?JSON 瀵硅薄")

    works = _normalize_works(payload, base_dir)
    titles = _normalize_titles(payload, len(works))
    contents = _normalize_contents(payload, len(works))
    tags = _normalize_tags(payload.get("tags"))
    schedule_values = _build_schedule_values(
        file_count=len(works),
        enable_timer=payload.get("enableTimer"),
        videos_per_day=payload.get("videosPerDay"),
        daily_times=payload.get("dailyTimes"),
        start_days=payload.get("startDays"),
        now_provider=now_provider,
        explicit_schedule_time=payload.get("scheduleTime"),
        explicit_schedule_times=payload.get("scheduleTimes"),
    )
    publish_accounts = _resolve_publish_accounts(payload, base_dir)
    headless_enabled = _is_headless_enabled(payload)

    items: list[dict] = []
    order_index = order_offset
    for index, work in enumerate(works):
        schedule_value = schedule_values[index]
        current_title = titles[index]
        current_content = contents[index]
        for publish_account in publish_accounts:
            if work["kind"] == "video":
                per_work_payload = dict(payload)
                per_work_payload["desc"] = current_content
                per_work_payload["description"] = current_content
                command = _build_video_command(
                    platform=publish_account["platform"],
                    account_name=publish_account["account_name"],
                    media_path=work["media_paths"][0],
                    title=current_title,
                    payload=per_work_payload,
                    schedule_value=schedule_value,
                    tags=tags,
                    headless_enabled=headless_enabled,
                )
            else:
                command = _build_note_command(
                    platform=publish_account["platform"],
                    account_name=publish_account["account_name"],
                    media_paths=work["media_paths"],
                    title=current_title,
                    payload=payload,
                    note_content=current_content,
                    schedule_value=schedule_value,
                    tags=tags,
                    headless_enabled=headless_enabled,
                )

            items.append(
                {
                    "itemId": f"item-{order_index}",
                    "orderIndex": order_index,
                    "taskIndex": task_index,
                    "kind": work["kind"],
                    "platform": publish_account["platform"],
                    "platformType": PLATFORM_TYPE_BY_NAME.get(publish_account["platform"]),
                    "accountId": publish_account.get("id"),
                    "accountName": publish_account["account_name"],
                    "filePath": publish_account.get("file_path"),
                    "title": current_title,
                    "content": current_content,
                    "mediaLabel": _build_media_label(work["media_paths"]),
                    "mediaPaths": [str(path) for path in work["media_paths"]],
                    "scheduleValue": schedule_value,
                    "command": command,
                }
            )
            order_index += 1

    return items


def build_publish_batch_plan(
    payloads: list[dict],
    *,
    base_dir: Path = BASE_DIR,
    now_provider: Callable[[], datetime] = datetime.now,
) -> list[dict]:
    if not isinstance(payloads, list):
        raise PublishBridgeError("鎵归噺鍙戝竷璇锋眰蹇呴』鏄?JSON 鏁扮粍")

    items: list[dict] = []
    order_offset = 0
    for task_index, payload in enumerate(payloads):
        task_items = build_publish_plan(
            payload,
            base_dir=base_dir,
            now_provider=now_provider,
            order_offset=order_offset,
            task_index=task_index,
        )
        items.extend(task_items)
        order_offset += len(task_items)
    return items


def build_publish_commands(
    payload: dict,
    *,
    base_dir: Path = BASE_DIR,
    now_provider: Callable[[], datetime] = datetime.now,
) -> list[list[str]]:
    return [
        list(item["command"])
        for item in build_publish_plan(
            payload,
            base_dir=base_dir,
            now_provider=now_provider,
        )
    ]

    if not isinstance(payload, dict):
        raise PublishBridgeError("发布请求必须是 JSON 对象")

    works = _normalize_works(payload, base_dir)
    titles = _normalize_titles(payload, len(works))
    contents = _normalize_contents(payload, len(works))
    tags = _normalize_tags(payload.get("tags"))
    schedule_values = _build_schedule_values(
        file_count=len(works),
        enable_timer=payload.get("enableTimer"),
        videos_per_day=payload.get("videosPerDay"),
        daily_times=payload.get("dailyTimes"),
        start_days=payload.get("startDays"),
        now_provider=now_provider,
        explicit_schedule_time=payload.get("scheduleTime"),
        explicit_schedule_times=payload.get("scheduleTimes"),
    )
    publish_accounts = _resolve_publish_accounts(payload, base_dir)
    headless_enabled = _is_headless_enabled(payload)

    commands: list[list[str]] = []
    for index, work in enumerate(works):
        schedule_value = schedule_values[index]
        current_title = titles[index]
        current_content = contents[index]
        for publish_account in publish_accounts:
            if work["kind"] == "video":
                per_work_payload = dict(payload)
                per_work_payload["desc"] = current_content
                per_work_payload["description"] = current_content
                commands.append(
                    _build_video_command(
                        platform=publish_account["platform"],
                        account_name=publish_account["account_name"],
                        media_path=work["media_paths"][0],
                        title=current_title,
                        payload=per_work_payload,
                        schedule_value=schedule_value,
                        tags=tags,
                        headless_enabled=headless_enabled,
                    )
                )
                continue

            commands.append(
                _build_note_command(
                    platform=publish_account["platform"],
                    account_name=publish_account["account_name"],
                    media_paths=work["media_paths"],
                    title=current_title,
                    payload=payload,
                    note_content=current_content,
                    schedule_value=schedule_value,
                    tags=tags,
                    headless_enabled=headless_enabled,
                )
            )
    return commands


def _resolve_cli_script(base_dir: Path) -> Path:
    candidate = base_dir / "sau_cli.py"
    if candidate.exists():
        return candidate
    return Path(__file__).with_name("sau_cli.py")


def _extract_account_name(command: list[str]) -> str:
    try:
        account_index = command.index("--account")
    except ValueError as exc:
        raise PublishBridgeError("发布命令缺少 --account 参数", status_code=500) from exc

    try:
        return str(command[account_index + 1])
    except IndexError as exc:
        raise PublishBridgeError("发布命令中的 --account 参数不完整", status_code=500) from exc


def _run_single_command(
    command: list[str],
    *,
    cli_script: Path,
    base_dir: Path,
    runner,
) -> dict:
    full_command = [sys.executable, str(cli_script), *command]
    completed = runner(
        args=full_command,
        cwd=str(base_dir),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return {
        "command": full_command,
        "returncode": completed.returncode,
        "stdout": (completed.stdout or "").strip(),
        "stderr": (completed.stderr or "").strip(),
    }


def _emit_publish_progress(progress_callback, event: dict) -> None:
    if callable(progress_callback):
        progress_callback(event)


def _build_command_result(
    item: dict,
    *,
    cli_script: Path,
    returncode: int,
    stdout: str = "",
    stderr: str = "",
) -> dict:
    return {
        "command": [sys.executable, str(cli_script), *list(item.get("command") or [])],
        "returncode": returncode,
        "stdout": stdout.strip(),
        "stderr": stderr.strip(),
    }


def _parse_publish_cli_args(command: list[str]) -> argparse.Namespace:
    from sau_cli import build_parser

    try:
        return build_parser().parse_args(command)
    except SystemExit as exc:
        raise PublishBridgeError(f"Unable to parse publish command: {' '.join(command)}", status_code=500) from exc


def _is_reusable_publish_args(args: argparse.Namespace) -> bool:
    if args.platform not in REUSABLE_PUBLISH_PLATFORMS:
        return False
    if args.action not in REUSABLE_PUBLISH_ACTIONS:
        return False
    if args.platform == "weixin" and args.action != "upload-video":
        return False
    return True


def _parse_reusable_publish_items(items: list[dict]) -> list[tuple[dict, argparse.Namespace]] | None:
    parsed_items: list[tuple[dict, argparse.Namespace]] = []
    for item in items:
        command = list(item.get("command") or [])
        if len(command) < 2:
            return None
        args = _parse_publish_cli_args(command)
        if not _is_reusable_publish_args(args):
            return None
        parsed_items.append((item, args))
    return parsed_items


async def _ensure_reusable_account_ready(platform: str, account_file: Path) -> None:
    from sau_cli import douyin_setup, ks_setup, weixin_setup, xiaohongshu_setup

    setup_map = {
        "douyin": douyin_setup,
        "kuaishou": ks_setup,
        "xiaohongshu": xiaohongshu_setup,
        "weixin": weixin_setup,
    }
    setup = setup_map[platform]
    is_ready = await setup(str(account_file), handle=False)
    if not is_ready:
        raise RuntimeError(
            f"{platform} cookie is missing or expired: {account_file}. Please log in again before publishing."
        )


async def _open_reusable_publish_context(playwright, platform: str, account_file: Path, headless: bool):
    from conf import LOCAL_CHROME_PATH
    from utils.base_social_media import set_init_script

    if platform == "douyin":
        browser = await playwright.chromium.launch(headless=headless, channel="chrome")
        context = await browser.new_context(
            storage_state=str(account_file),
            permissions=["geolocation"],
        )
        context = await set_init_script(context)
        return browser, context

    if platform == "kuaishou":
        if LOCAL_CHROME_PATH:
            browser = await playwright.chromium.launch(
                headless=headless,
                executable_path=LOCAL_CHROME_PATH,
            )
        else:
            browser = await playwright.chromium.launch(headless=headless, channel="chrome")
        context = await browser.new_context(storage_state=str(account_file))
        context = await set_init_script(context)
        return browser, context

    if platform == "xiaohongshu":
        browser = await playwright.chromium.launch(headless=headless, channel="chrome")
        context = await browser.new_context(
            permissions=["geolocation"],
            storage_state=str(account_file),
        )
        context = await set_init_script(context)
        return browser, context

    if platform == "weixin":
        from uploader.tencent_uploader.main import _build_launch_kwargs

        browser = await playwright.chromium.launch(**_build_launch_kwargs(headless=headless))
        context = await browser.new_context(
            storage_state=str(account_file),
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        )
        return browser, context

    raise PublishBridgeError(f"Reusable publish does not support platform: {platform}", status_code=500)


def _build_reusable_uploader(args: argparse.Namespace, account_file: Path):
    from sau_cli import parse_tags
    from uploader.douyin_uploader.main import (
        DOUYIN_PUBLISH_STRATEGY_IMMEDIATE,
        DOUYIN_PUBLISH_STRATEGY_SCHEDULED,
        DouYinNote,
        DouYinVideo,
    )
    from uploader.ks_uploader.main import (
        KUAISHOU_PUBLISH_STRATEGY_IMMEDIATE,
        KUAISHOU_PUBLISH_STRATEGY_SCHEDULED,
        KSNote,
        KSVideo,
    )
    from uploader.tencent_uploader.main import (
        TENCENT_PUBLISH_STRATEGY_IMMEDIATE,
        TENCENT_PUBLISH_STRATEGY_SCHEDULED,
        TencentVideo,
    )
    from uploader.xiaohongshu_uploader.main import (
        XIAOHONGSHU_PUBLISH_STRATEGY_IMMEDIATE,
        XIAOHONGSHU_PUBLISH_STRATEGY_SCHEDULED,
        XiaoHongShuNote,
        XiaoHongShuVideo,
    )

    tags = parse_tags(getattr(args, "tags", ""))

    if args.platform == "douyin":
        publish_strategy = (
            DOUYIN_PUBLISH_STRATEGY_SCHEDULED if args.schedule else DOUYIN_PUBLISH_STRATEGY_IMMEDIATE
        )
        if args.action == "upload-video":
            return DouYinVideo(
                args.title,
                str(args.file),
                tags,
                args.schedule or 0,
                str(account_file),
                desc=args.desc,
                thumbnail_portrait_path=str(args.thumbnail) if args.thumbnail else None,
                productLink=getattr(args, "product_link", ""),
                productTitle=getattr(args, "product_title", ""),
                self_declaration=getattr(args, "self_declaration", False),
                publish_strategy=publish_strategy,
                debug=args.debug,
                headless=args.headless,
            ), "upload_video_content"
        return DouYinNote(
            image_paths=[str(path) for path in args.images],
            title=args.title,
            note=args.note,
            tags=tags,
            publish_date=args.schedule or 0,
            account_file=str(account_file),
            self_declaration=getattr(args, "self_declaration", False),
            publish_strategy=publish_strategy,
            debug=args.debug,
            headless=args.headless,
        ), "upload_note_content"

    if args.platform == "kuaishou":
        publish_strategy = (
            KUAISHOU_PUBLISH_STRATEGY_SCHEDULED if args.schedule else KUAISHOU_PUBLISH_STRATEGY_IMMEDIATE
        )
        if args.action == "upload-video":
            return KSVideo(
                title=args.title,
                file_path=str(args.file),
                desc=args.desc,
                tags=tags,
                publish_date=args.schedule or 0,
                account_file=str(account_file),
                thumbnail_path=str(args.thumbnail) if args.thumbnail else None,
                publish_strategy=publish_strategy,
                debug=args.debug,
                headless=args.headless,
            ), "upload_video_content"
        return KSNote(
            image_paths=[str(path) for path in args.images],
            title=args.title,
            note=args.note,
            tags=tags,
            publish_date=args.schedule or 0,
            account_file=str(account_file),
            publish_strategy=publish_strategy,
            debug=args.debug,
            headless=args.headless,
        ), "upload_note_content"

    if args.platform == "xiaohongshu":
        publish_strategy = (
            XIAOHONGSHU_PUBLISH_STRATEGY_SCHEDULED if args.schedule else XIAOHONGSHU_PUBLISH_STRATEGY_IMMEDIATE
        )
        if args.action == "upload-video":
            return XiaoHongShuVideo(
                title=args.title,
                file_path=str(args.file),
                desc=args.desc,
                tags=tags,
                publish_date=args.schedule or 0,
                account_file=str(account_file),
                thumbnail_path=str(args.thumbnail) if args.thumbnail else None,
                publish_strategy=publish_strategy,
                debug=args.debug,
                headless=args.headless,
            ), "upload_video_content"
        return XiaoHongShuNote(
            image_paths=[str(path) for path in args.images],
            title=args.title,
            desc=args.note,
            note=args.note,
            tags=tags,
            publish_date=args.schedule or 0,
            account_file=str(account_file),
            publish_strategy=publish_strategy,
            debug=args.debug,
            headless=args.headless,
        ), "upload_note_content"

    if args.platform == "weixin" and args.action == "upload-video":
        publish_strategy = TENCENT_PUBLISH_STRATEGY_SCHEDULED if args.schedule else TENCENT_PUBLISH_STRATEGY_IMMEDIATE
        return TencentVideo(
            title=args.title,
            file_path=str(args.file),
            tags=tags,
            publish_date=args.schedule or 0,
            account_file=str(account_file),
            desc=args.desc,
            thumbnail_path=str(args.thumbnail) if args.thumbnail else None,
            is_draft=args.draft,
            publish_strategy=publish_strategy,
            debug=args.debug,
            headless=args.headless,
        ), "upload_video_content"

    raise PublishBridgeError(
        f"Reusable publish does not support command: {args.platform} {args.action}",
        status_code=500,
    )


async def _run_reusable_publish_item(args: argparse.Namespace, context) -> None:
    from uploader.douyin_uploader.main import DouYinNote
    from uploader.ks_uploader.main import KSNote, KUAISHOU_UPLOAD_URL, KUAISHOU_UPLOAD_URL_PATTERN

    from sau_cli import resolve_account_file

    account_file = resolve_account_file(args.platform, args.account)
    uploader, method_name = _build_reusable_uploader(args, account_file)
    await uploader.validate_upload_args()

    page = await context.new_page()
    try:
        if isinstance(uploader, DouYinNote):
            await page.goto("https://creator.douyin.com/creator-micro/content/upload")
            await page.wait_for_url("https://creator.douyin.com/creator-micro/content/upload")
        elif isinstance(uploader, KSNote):
            await page.goto(KUAISHOU_UPLOAD_URL)
            await page.wait_for_url(KUAISHOU_UPLOAD_URL_PATTERN)

        await getattr(uploader, method_name)(page)
    finally:
        await page.close()


async def _run_reusable_account_queue_async(
    parsed_items: list[tuple[dict, argparse.Namespace]],
    *,
    cli_script: Path,
    progress_callback=None,
    should_stop=None,
) -> list[tuple[int, dict]]:
    from patchright.async_api import async_playwright
    from sau_cli import resolve_account_file

    first_args = parsed_items[0][1]
    platform = first_args.platform
    account_file = resolve_account_file(platform, first_args.account)
    await _ensure_reusable_account_ready(platform, account_file)

    results: list[tuple[int, dict]] = []
    consecutive_failures = 0

    async with async_playwright() as playwright:
        browser, context = await _open_reusable_publish_context(
            playwright,
            platform,
            account_file,
            bool(getattr(first_args, "headless", True)),
        )
        try:
            for item, args in parsed_items:
                if callable(should_stop) and should_stop():
                    break

                _emit_publish_progress(
                    progress_callback,
                    {
                        "type": "item-started",
                        "itemId": item["itemId"],
                        "orderIndex": item["orderIndex"],
                    },
                )

                try:
                    await _run_reusable_publish_item(args, context)
                    await context.storage_state(path=account_file)
                    result = _build_command_result(
                        item,
                        cli_script=cli_script,
                        returncode=0,
                        stdout=f"Reusable publish succeeded: {item['itemId']}",
                    )
                    consecutive_failures = 0
                except Exception as exc:
                    result = _build_command_result(
                        item,
                        cli_script=cli_script,
                        returncode=1,
                        stderr=str(exc),
                    )
                    consecutive_failures += 1

                results.append((item["orderIndex"], result))
                _emit_publish_progress(
                    progress_callback,
                    {
                        "type": "item-finished",
                        "itemId": item["itemId"],
                        "orderIndex": item["orderIndex"],
                        "returncode": result["returncode"],
                        "stdout": result["stdout"],
                        "stderr": result["stderr"],
                    },
                )

                if consecutive_failures >= MAX_REUSABLE_CONSECUTIVE_FAILURES:
                    break
        finally:
            try:
                await context.close()
            except Exception:
                pass
            try:
                await browser.close()
            except Exception:
                pass

    return results


def _run_reusable_account_queue(
    parsed_items: list[tuple[dict, argparse.Namespace]],
    *,
    cli_script: Path,
    progress_callback=None,
    should_stop=None,
) -> list[tuple[int, dict]]:
    return asyncio.run(
        _run_reusable_account_queue_async(
            parsed_items,
            cli_script=cli_script,
            progress_callback=progress_callback,
            should_stop=should_stop,
        )
    )


def _run_account_queue(
    items: list[dict],
    *,
    cli_script: Path,
    base_dir: Path,
    runner,
    progress_callback=None,
    should_stop=None,
) -> list[tuple[int, dict]]:
    parsed_items = _parse_reusable_publish_items(items) if runner is subprocess.run else None
    if parsed_items:
        return _run_reusable_account_queue(
            parsed_items,
            cli_script=cli_script,
            progress_callback=progress_callback,
            should_stop=should_stop,
        )

    results: list[tuple[int, dict]] = []
    for item in items:
        if callable(should_stop) and should_stop():
            break

        _emit_publish_progress(
            progress_callback,
            {
                "type": "item-started",
                "itemId": item["itemId"],
                "orderIndex": item["orderIndex"],
            },
        )

        result = _run_single_command(
            item["command"],
            cli_script=cli_script,
            base_dir=base_dir,
            runner=runner,
        )
        results.append((item["orderIndex"], result))
        _emit_publish_progress(
            progress_callback,
            {
                "type": "item-finished",
                "itemId": item["itemId"],
                "orderIndex": item["orderIndex"],
                "returncode": result["returncode"],
                "stdout": result["stdout"],
                "stderr": result["stderr"],
            },
        )
        if result["returncode"] != 0:
            break
    return results


def _run_platform_queues(
    account_queues: dict[str, list[dict]],
    *,
    cli_script: Path,
    base_dir: Path,
    runner,
    progress_callback=None,
    should_stop=None,
) -> list[tuple[int, dict]]:
    if not account_queues:
        return []

    results: list[tuple[int, dict]] = []
    max_workers = min(4, len(account_queues))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(
                _run_account_queue,
                command_items,
                cli_script=cli_script,
                base_dir=base_dir,
                runner=runner,
                progress_callback=progress_callback,
                should_stop=should_stop,
            )
            for command_items in account_queues.values()
        ]
        for future in as_completed(futures):
            results.extend(future.result())
    return results


def run_publish_payload(
    payload: dict,
    *,
    base_dir: Path = BASE_DIR,
    now_provider: Callable[[], datetime] = datetime.now,
    runner=subprocess.run,
    progress_callback=None,
    precomputed_plan: list[dict] | None = None,
    should_stop=None,
) -> dict:
    plan_items = precomputed_plan or build_publish_plan(payload, base_dir=base_dir, now_provider=now_provider)
    if precomputed_plan is None:
        _emit_publish_progress(progress_callback, {"type": "plan-prepared", "items": plan_items})
    cli_script = _resolve_cli_script(base_dir)

    account_queues_by_platform: dict[str, dict[str, list[dict]]] = {}
    for item in plan_items:
        platform = str(item["platform"])
        account_name = str(item["accountName"])
        platform_queues = account_queues_by_platform.setdefault(platform, {})
        platform_queues.setdefault(account_name, []).append(item)

    ordered_results: list[tuple[int, dict]] = []
    max_platform_workers = max(1, len(account_queues_by_platform))
    with ThreadPoolExecutor(max_workers=max_platform_workers) as executor:
        futures = [
            executor.submit(
                _run_platform_queues,
                account_queues,
                cli_script=cli_script,
                base_dir=base_dir,
                runner=runner,
                progress_callback=progress_callback,
                should_stop=should_stop,
            )
            for account_queues in account_queues_by_platform.values()
        ]
        for future in as_completed(futures):
            ordered_results.extend(future.result())

    ordered_results.sort(key=lambda item: item[0])
    results = [result for _, result in ordered_results]
    first_failure = next((result for result in results if result["returncode"] != 0), None)
    if first_failure is not None:
        raise PublishBridgeError(
            first_failure["stderr"] or first_failure["stdout"] or "sau CLI publish failed",
            status_code=500,
        )

    return {
        "executed": len(results),
        "results": results,
        "items": [
            {
                key: value
                for key, value in item.items()
                if key != "command"
            }
            for item in plan_items
        ],
    }


def run_publish_plan_items(
    plan_items: list[dict],
    *,
    base_dir: Path = BASE_DIR,
    runner=subprocess.run,
    progress_callback=None,
    should_stop=None,
) -> dict:
    if not isinstance(plan_items, list):
        raise PublishBridgeError("publish plan items must be a list", status_code=500)

    normalized_items = []
    for item in plan_items:
        if not isinstance(item, dict):
            raise PublishBridgeError("publish plan item must be an object", status_code=500)
        normalized_items.append(dict(item))

    _emit_publish_progress(progress_callback, {"type": "plan-prepared", "items": normalized_items})

    return run_publish_payload(
        {},
        base_dir=base_dir,
        runner=runner,
        progress_callback=progress_callback,
        precomputed_plan=normalized_items,
        should_stop=should_stop,
    )


def run_publish_batch(
    payloads: list[dict],
    *,
    base_dir: Path = BASE_DIR,
    now_provider: Callable[[], datetime] = datetime.now,
    runner=subprocess.run,
    progress_callback=None,
    should_stop=None,
) -> dict:
    if not isinstance(payloads, list):
        raise PublishBridgeError("批量发布请求必须是 JSON 数组")

    planned_items = build_publish_batch_plan(payloads, base_dir=base_dir, now_provider=now_provider)
    batch_result = run_publish_payload(
        {},
        base_dir=base_dir,
        now_provider=now_provider,
        runner=runner,
        progress_callback=progress_callback,
        precomputed_plan=planned_items,
        should_stop=should_stop,
    )

    return {
        "tasks": len(payloads),
        "executed": batch_result["executed"],
        "results": batch_result["results"],
        "items": batch_result["items"],
    }
