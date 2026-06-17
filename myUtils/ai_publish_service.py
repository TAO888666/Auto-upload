from __future__ import annotations

import base64
from concurrent.futures import ThreadPoolExecutor
import json
import mimetypes
import ntpath
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
from functools import lru_cache
from pathlib import Path
from typing import Iterable

import requests

DEFAULT_AI_PUBLISH_CONFIG = {
    "provider": "deepseek",
    "api_key": "",
    "api_base": "https://api.deepseek.com/v1",
    "model": "deepseek-chat",
}

PROVIDER_MODEL_OPTIONS = {
    "deepseek": ["deepseek-chat", "deepseek-reasoner"],
    "openai": ["gpt-4.1-mini", "gpt-4.1", "gpt-4o-mini"],
    "gemini": ["gemini-2.5-flash", "gemini-2.5-pro"],
    "qwen": ["qwen-plus", "qwen-turbo", "qwen-max"],
    "ark": [],
    "custom": [],
}

PLATFORM_LABEL_BY_TYPE = {
    1: "xiaohongshu",
    2: "weixin",
    3: "douyin",
    4: "kuaishou",
}

BASE_SYSTEM_PROMPT = """
你是发布AI 助手。

默认情况下，你应该像正常中文助手一样自然聊天，可以回答通用问题、项目问题，也可以结合用户发送的图片进行理解和讨论。

只有当用户明确提出“发布、定时发布、安排发布、发布到某个平台或账号”这类需求时，你再进入发布助手模式，帮助用户整理发布任务需要的信息。

要求：
- 始终使用中文回答。
- 正常聊天时，不要强行把话题往发布任务上引。
- 涉及发布时，可以帮助梳理账号、素材、标题、文案、发布时间等信息。
- 不要编造不存在的账号、素材或时间。
- 不要声称已经执行发布，除非系统真的已经进入发布流程并返回结果。
- 回答尽量自然、简洁、清楚。
""".strip()

TASK_ANALYZER_PROMPT = """
你要把对话转成可执行的发布任务预览 JSON。

必须遵守：
- 只输出 JSON，不要输出 markdown，不要解释。
- 如果当前只是普通聊天，没有形成发布意图，返回 {"intent":"chat"}。
- 如果存在发布意图，返回 {"intent":"publish", ...}。
- 只能从给定的账号和素材中选择；不要编造新名字。
- 如果用户在对话里明确给了本地绝对路径，且它已经出现在 availableContext.materials 中，可以直接把它作为 works 使用。
- 如果信息不足，也要尽量返回部分结果，并把缺失字段写入 missingFields。

JSON 结构：
{
  "intent": "chat" | "publish",
  "ready": true | false,
  "missingFields": ["accounts", "works", "title", "scheduleTime"],
  "accounts": [{"id": 3, "platform": "douyin", "name": "千聊官号"}],
  "works": [{"id": 12, "name": "A作品.mp4", "kind": "video", "filePath": "uuid_A作品.mp4"}],
  "title": "标题",
  "content": "文案",
  "tags": ["标签1", "标签2"],
  "scheduleType": "now" | "scheduled",
  "scheduleTime": "2026-05-23 21:00:00"
}
""".strip()

PUBLISH_CENTER_COPY_PROMPT = """
你是发布中心文案助手。
你会根据用户给出的作品素材，生成可直接填写到发布中心里的标题和文案。

必须遵守：
- 只输出 JSON，不要输出 markdown，不要解释。
- JSON 格式固定为 {"title":"标题","content":"文案"}。
- 标题和文案都必须使用中文。
- 标题简洁自然，适合直接发布，不要加序号、书名号或额外说明。
- 文案写成可直接发布的正文，不要输出标签列表，不要解释你的思路。
- 不要编造作品里没有出现的信息。
- 不要直接照抄或拼接音频转录稿；必须先提炼作品的核心主题，再改写成适合发布的短文案。
- 如果目标平台包含抖音或快手，文案应简短有钩子，优先使用“开头一句话吸引注意 + 一个核心价值点 + 一个评论/互动引导”的结构，通常控制在 80 到 150 个中文字符。
- 如果素材内容很长或包含多个段落，只选择最主要的一个主题生成文案，不要把所有转录内容都塞进正文。
- 如果素材转录文本中存在明显的语音识别错误、同音字错别字或专有名词误写，请根据上下文自动纠正后再生成标题和文案。
- 纠错只能用于恢复原意，不要借纠错扩写、改写或添加素材中没有的信息。
- 对品牌名、产品名、课程名、人名等专有名词要特别谨慎，优先保持上下文中最合理、最一致的写法。
""".strip()

LOCAL_VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".wmv", ".flv", ".mkv", ".m4v", ".webm"}
WINDOWS_ABSOLUTE_VIDEO_PATH_RE = re.compile(
    r'([A-Za-z]:(?:\\|/)[^\r\n]*?\.(?:mp4|avi|mov|wmv|flv|mkv|m4v|webm))',
    re.IGNORECASE,
)
LOCAL_VIDEO_FRAME_COUNT = 4
LOCAL_VIDEO_FRAME_MAX_WIDTH = 1280
LOCAL_AUDIO_SAMPLE_RATE = 16000
LOCAL_WHISPER_MODEL_NAME = "base"
LOCAL_WHISPER_DEVICE = "auto"
LOCAL_WHISPER_COMPUTE_TYPE = "int8"
LOCAL_TRANSCRIPT_MAX_CHARS = 4000
PUBLISH_CENTER_COPY_MAX_CONCURRENCY = 30


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _bundled_ffmpeg_dir() -> Path:
    return _project_root() / "tools" / "ffmpeg"


def _bundled_vendor_python_dir() -> Path:
    return _project_root() / "vendor" / "python"


def _bundled_whisper_model_dir() -> Path:
    return _project_root() / "vendor" / "models" / "faster-whisper-base"


def _config_file(base_dir: Path) -> Path:
    return Path(base_dir) / "gui_config.json"


def load_ai_publish_config(base_dir: Path) -> dict:
    config_path = _config_file(base_dir)
    if not config_path.exists():
        return dict(DEFAULT_AI_PUBLISH_CONFIG)

    try:
        raw_config = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return dict(DEFAULT_AI_PUBLISH_CONFIG)

    config = dict(DEFAULT_AI_PUBLISH_CONFIG)
    config["provider"] = str(raw_config.get("provider") or config["provider"]).strip() or config["provider"]
    config["api_key"] = str(raw_config.get("api_key") or config["api_key"]).strip()
    config["api_base"] = str(raw_config.get("api_base") or config["api_base"]).strip() or config["api_base"]
    config["model"] = str(raw_config.get("model") or config["model"]).strip() or config["model"]
    return config


def save_ai_publish_config(payload: dict, base_dir: Path) -> dict:
    current = load_ai_publish_config(base_dir)
    config_path = _config_file(base_dir)
    file_payload = {}
    if config_path.exists():
        try:
            file_payload = json.loads(config_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            file_payload = {}

    provider = str(payload.get("provider") or current["provider"]).strip() or current["provider"]
    api_base = str(payload.get("apiBase") or payload.get("api_base") or current["api_base"]).strip() or current["api_base"]
    default_model = str(payload.get("defaultModel") or payload.get("model") or current["model"]).strip() or current["model"]
    api_key = payload.get("apiKey")
    if api_key is None:
        api_key = payload.get("api_key")

    if api_key is None or str(api_key).strip() == "":
        api_key = current["api_key"]
    else:
        api_key = str(api_key).strip()

    file_payload["provider"] = provider
    file_payload["api_base"] = api_base
    file_payload["api_key"] = api_key
    file_payload["model"] = default_model

    config_path.write_text(
        json.dumps(file_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return load_ai_publish_config(base_dir)


def serialize_ai_publish_config(config: dict) -> dict:
    api_key = str(config.get("api_key") or "").strip()
    masked_api_key = ""
    if api_key:
        masked_api_key = f"{api_key[:3]}****{api_key[-4:]}" if len(api_key) > 7 else "****"

    return {
        "provider": str(config.get("provider") or DEFAULT_AI_PUBLISH_CONFIG["provider"]),
        "apiBase": str(config.get("api_base") or DEFAULT_AI_PUBLISH_CONFIG["api_base"]),
        "defaultModel": str(config.get("model") or DEFAULT_AI_PUBLISH_CONFIG["model"]),
        "hasApiKey": bool(api_key),
        "maskedApiKey": masked_api_key,
    }


def build_model_options(config: dict) -> dict:
    provider = _resolve_provider(config)
    default_model = str(config.get("model") or DEFAULT_AI_PUBLISH_CONFIG["model"]).strip() or DEFAULT_AI_PUBLISH_CONFIG["model"]
    options = list(PROVIDER_MODEL_OPTIONS.get(provider, []))
    if default_model and default_model not in options:
        options.insert(0, default_model)

    models = [{"id": model_name, "label": model_name} for model_name in options]
    return {
        "models": models,
        "defaultModel": default_model,
    }


def _resolve_provider(config: dict) -> str:
    provider = str(config.get("provider") or DEFAULT_AI_PUBLISH_CONFIG["provider"]).strip().lower()
    api_base = str(config.get("api_base") or "").strip().lower()
    if provider in {"ark", "doubao", "volcengine", "bytedance"}:
        return "ark"
    if "volces.com" in api_base or "volcengine.com" in api_base:
        return "ark"
    return provider or DEFAULT_AI_PUBLISH_CONFIG["provider"]


def _normalized_api_base(config: dict) -> str:
    api_base = str(config.get("api_base") or "").strip().rstrip("/")
    if not api_base:
        raise ValueError("AI API Base URL 不能为空")

    normalized = api_base
    suffixes = ("/chat/completions", "/responses")
    changed = True
    while changed:
        changed = False
        lowered = normalized.lower()
        for suffix in suffixes:
            if lowered.endswith(suffix):
                normalized = normalized[: -len(suffix)].rstrip("/")
                changed = True
                break
    return normalized


def _request_url(config: dict) -> str:
    api_base = _normalized_api_base(config)
    if _resolve_provider(config) == "ark":
        return f"{api_base}/responses"
    return f"{api_base}/chat/completions"


def _request_headers(config: dict) -> dict:
    return {
        **_request_auth_headers(config),
        "Content-Type": "application/json",
    }


def _request_auth_headers(config: dict) -> dict:
    api_key = str(config.get("api_key") or "").strip()
    if not api_key:
        raise ValueError("AI API Key 不能为空")
    return {
        "Authorization": f"Bearer {api_key}",
    }


def _file_upload_url(config: dict) -> str:
    return f"{_normalized_api_base(config)}/files"


def _file_detail_url(config: dict, file_id: str) -> str:
    return f"{_file_upload_url(config)}/{file_id}"


def normalize_chat_attachments(attachments: Iterable[dict]) -> list[dict]:
    normalized_attachments = []
    for attachment in attachments or []:
        if not isinstance(attachment, dict):
            continue
        data_url = str(attachment.get("dataUrl") or attachment.get("data_url") or "").strip()
        relative_path = str(attachment.get("relativePath") or attachment.get("relative_path") or "").strip()
        local_path = str(attachment.get("localPath") or attachment.get("local_path") or "").strip()
        mime_type = str(attachment.get("mimeType") or attachment.get("mime_type") or "").strip()
        if not data_url and not relative_path and not local_path:
            continue
        normalized_attachments.append(
            {
                "dataUrl": data_url,
                "relativePath": relative_path,
                "localPath": local_path,
                "mimeType": mime_type,
                "originalName": str(attachment.get("originalName") or attachment.get("original_name") or "").strip(),
                "sizeBytes": int(attachment.get("sizeBytes") or attachment.get("size_bytes") or 0),
            }
        )
    return normalized_attachments


def normalize_chat_messages(messages: Iterable[dict]) -> list[dict]:
    normalized_messages = []
    for message in messages or []:
        if not isinstance(message, dict):
            continue
        role = str(message.get("role") or "").strip()
        content = str(message.get("content") or "").strip()
        attachments = normalize_chat_attachments(message.get("attachments") or [])
        if role not in {"system", "user", "assistant"}:
            continue
        if not content and not attachments:
            continue
        normalized_messages.append({"role": role, "content": content, "attachments": attachments})
    return normalized_messages


def normalize_messages(messages: Iterable[dict]) -> list[dict]:
    normalized_messages = []
    for message in normalize_chat_messages(messages):
        if not message.get("content"):
            continue
        normalized_messages.append({"role": message["role"], "content": message["content"]})
    return normalized_messages


def _build_openai_message_content(message: dict):
    attachments = list(message.get("attachments") or [])
    if not attachments:
        return message.get("content") or ""

    content_parts = []
    if message.get("content"):
        content_parts.append({"type": "text", "text": message["content"]})
    for attachment in attachments:
        mime_type = str(attachment.get("mimeType") or "").strip().lower()
        if mime_type.startswith("image/"):
            content_parts.append(
                {
                    "type": "image_url",
                    "image_url": {
                        "url": attachment["dataUrl"],
                        "detail": "auto",
                    },
                }
            )
            continue
        raise ValueError("当前 provider 仅 ark 支持音频和视频附件")
    return content_parts


def _build_attachment_filename(attachment: dict, mime_type: str) -> str:
    original_name = str(attachment.get("originalName") or "").strip()
    fallback_suffix = mimetypes.guess_extension(mime_type) or ""
    if original_name:
        return original_name

    base_name = "attachment"
    if mime_type.startswith("audio/"):
        base_name = "audio"
    elif mime_type.startswith("video/"):
        base_name = "video"
    elif mime_type.startswith("image/"):
        base_name = "image"
    return f"{base_name}{fallback_suffix}"


def _decode_attachment_data_url(data_url: str) -> tuple[str, bytes]:
    normalized_data_url = str(data_url or "").strip()
    if not normalized_data_url.startswith("data:") or "," not in normalized_data_url:
        raise ValueError("Ark 文件上传需要有效的 dataUrl")

    header, encoded = normalized_data_url.split(",", 1)
    mime_type = header[5:].split(";", 1)[0].strip().lower() or "application/octet-stream"
    try:
        file_bytes = base64.b64decode(encoded, validate=False)
    except (ValueError, TypeError) as exc:
        raise ValueError("Ark 文件上传的 dataUrl 无法解析") from exc
    if not file_bytes:
        raise ValueError("Ark 文件上传内容为空")
    return mime_type, file_bytes


def _upload_ark_file(config: dict, attachment: dict, *, purpose: str) -> str:
    mime_type = str(attachment.get("mimeType") or "").strip().lower()
    filename = _build_attachment_filename(attachment, mime_type)
    local_path = str(attachment.get("localPath") or "").strip()

    if local_path:
        file_path = Path(local_path)
        if not file_path.exists():
            raise ValueError(f"作品文件不存在: {filename}")
        if not mime_type:
            mime_type = "application/octet-stream"

        try:
            with file_path.open("rb") as file_stream:
                response = requests.post(
                    _file_upload_url(config),
                    headers=_request_auth_headers(config),
                    data={"purpose": purpose},
                    files={"file": (filename, file_stream, mime_type)},
                    timeout=(120, 1800),
                )
        except Exception as exc:
            error_text = str(exc or "").lower()
            is_timeout = (
                isinstance(exc, requests.Timeout)
                or isinstance(exc, TimeoutError)
                or "timed out" in error_text
                or "timeout" in error_text
            )
            if is_timeout:
                raise RuntimeError("视频上传到豆包 Files API 超时，请先用单个视频测试，或压缩视频体积后重试") from exc
            raise

        response.encoding = "utf-8"
        _raise_for_status_with_detail(response)
        payload = response.json()
        file_id = str(payload.get("id") or payload.get("file_id") or "").strip()
        if not file_id:
            raise RuntimeError("Ark Files API 上传成功但未返回 file_id")
        _wait_for_ark_file_ready(config, file_id)
        return file_id

    if local_path:
        file_path = Path(local_path)
        if not file_path.exists():
            raise ValueError(f"Ark 文件上传失败，本地文件不存在：{filename}")
        file_bytes = file_path.read_bytes()
    else:
        decoded_mime_type, file_bytes = _decode_attachment_data_url(attachment.get("dataUrl") or "")
        if not mime_type:
            mime_type = decoded_mime_type

    if not mime_type:
        mime_type = "application/octet-stream"

    response = requests.post(
        _file_upload_url(config),
        headers=_request_auth_headers(config),
        data={"purpose": purpose},
        files={"file": (filename, file_bytes, mime_type)},
        timeout=(120, 1800),
    )
    response.encoding = "utf-8"
    _raise_for_status_with_detail(response)
    payload = response.json()
    file_id = str(payload.get("id") or payload.get("file_id") or "").strip()
    if not file_id:
        raise RuntimeError("Ark Files API 上传成功但未返回 file_id")
    _wait_for_ark_file_ready(config, file_id)
    return file_id


def _extract_ark_file_status(payload) -> str:
    if not isinstance(payload, dict):
        return ""

    for key in ("status", "state"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip().lower()

    data = payload.get("data")
    if isinstance(data, dict):
        return _extract_ark_file_status(data)
    return ""


def _wait_for_ark_file_ready(
    config: dict,
    file_id: str,
    *,
    max_attempts: int = 180,
    poll_interval_seconds: float = 2.0,
) -> None:
    pending_statuses = {"processing", "pending", "queued", "in_progress", "uploaded"}
    ready_statuses = {"processed", "ready", "succeeded", "success", "completed"}
    failed_statuses = {"failed", "error", "cancelled", "deleted", "expired"}

    for attempt in range(max_attempts):
        response = requests.get(
            _file_detail_url(config, file_id),
            headers=_request_auth_headers(config),
            timeout=(10, 120),
        )
        response.encoding = "utf-8"
        _raise_for_status_with_detail(response)
        payload = response.json()
        status = _extract_ark_file_status(payload)
        if status in ready_statuses:
            return
        if status in failed_statuses:
            raise RuntimeError(f"Ark 文件处理失败，当前状态：{status}")
        if status and status not in pending_statuses:
            return
        if attempt < max_attempts - 1:
            time.sleep(poll_interval_seconds)

    raise RuntimeError("Ark 文件处理超时，请稍后重试")


def _build_ark_message_content(config: dict, message: dict):
    attachments = list(message.get("attachments") or [])
    if not attachments:
        return message.get("content") or ""

    content_parts = []
    if message.get("content"):
        content_parts.append({"type": "input_text", "text": message["content"]})
    for attachment in attachments:
        mime_type = str(attachment.get("mimeType") or "").strip().lower()
        if mime_type.startswith("image/"):
            content_parts.append({"type": "input_image", "image_url": attachment["dataUrl"]})
            continue

        if mime_type.startswith("video/"):
            content_parts.append(
                {
                    "type": "input_video",
                    "file_id": _upload_ark_file(config, attachment, purpose="user_data"),
                }
            )
            continue

        original_name = _build_attachment_filename(attachment, mime_type)
        content_parts.append(
            {
                "type": "input_file",
                "filename": original_name,
                "file_data": attachment["dataUrl"],
            }
        )
    return content_parts


def _count_cjk_chars(text: str) -> int:
    return sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")


def _count_suspicious_mojibake_chars(text: str) -> int:
    return sum(1 for ch in text if 0x80 <= ord(ch) <= 0xFF or ch == "�")


def _repair_possible_mojibake_segment(text: str) -> str:
    if not isinstance(text, str) or not text:
        return text

    if _count_suspicious_mojibake_chars(text) == 0:
        return text

    try:
        candidate = bytes(ord(ch) for ch in text).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return text

    if _count_cjk_chars(candidate) > _count_cjk_chars(text):
        return candidate

    if _count_suspicious_mojibake_chars(candidate) < _count_suspicious_mojibake_chars(text):
        return candidate

    return text


def _repair_possible_mojibake_text(text: str) -> str:
    if not isinstance(text, str) or not text:
        return text

    whole_text_candidate = _repair_possible_mojibake_segment(text)
    if whole_text_candidate != text:
        return whole_text_candidate

    if _count_suspicious_mojibake_chars(text) == 0:
        return text

    repaired_chunks: list[str] = []
    byte_run: list[str] = []

    def flush_byte_run() -> None:
        if not byte_run:
            return
        repaired_chunks.append(_repair_possible_mojibake_segment("".join(byte_run)))
        byte_run.clear()

    for ch in text:
        if ord(ch) <= 0xFF:
            byte_run.append(ch)
            continue
        flush_byte_run()
        repaired_chunks.append(ch)

    flush_byte_run()
    return "".join(repaired_chunks)


def _build_responses_payload(
    config: dict,
    messages: list[dict],
    *,
    model: str,
    temperature: float,
    stream: bool,
) -> dict:
    instructions = "\n\n".join(
        message["content"]
        for message in messages
        if message.get("role") == "system" and str(message.get("content") or "").strip()
    ).strip()
    input_messages = []
    for message in messages:
        if message.get("role") != "user":
            continue
        if not str(message.get("content") or "").strip() and not list(message.get("attachments") or []):
            continue
        input_messages.append(
            {
                "role": message["role"],
                "content": _build_ark_message_content(config, message),
            }
        )

    payload = {
        "model": model,
        "input": input_messages,
        "temperature": temperature,
        "stream": stream,
    }
    if instructions:
        payload["instructions"] = instructions
    return payload


def _build_request_payload(
    config: dict,
    *,
    messages: list[dict],
    model: str,
    temperature: float,
    stream: bool,
    response_format: dict | None = None,
) -> dict:
    normalized_messages = normalize_chat_messages(messages)
    if _resolve_provider(config) == "ark":
        return _build_responses_payload(
            config,
            normalized_messages,
            model=model,
            temperature=temperature,
            stream=stream,
        )

    payload = {
        "model": model,
        "messages": [
            {
                "role": message["role"],
                "content": _build_openai_message_content(message),
            }
            for message in normalized_messages
        ],
        "temperature": temperature,
        "stream": stream,
    }
    if response_format:
        payload["response_format"] = response_format
    return payload


def _extract_response_text(data: dict) -> str:
    if not isinstance(data, dict):
        return ""

    output_text = data.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return _repair_possible_mojibake_text(output_text.strip())

    choices = data.get("choices") or []
    if choices:
        return _repair_possible_mojibake_text(
            str((((choices[0] or {}).get("message") or {}).get("content") or "")).strip()
        )

    texts = []
    for item in data.get("output") or []:
        if not isinstance(item, dict):
            continue
        for content_item in item.get("content") or []:
            if not isinstance(content_item, dict):
                continue
            text_value = content_item.get("text")
            if isinstance(text_value, str) and text_value:
                texts.append(text_value)
                continue
            fallback_value = content_item.get("value")
            if isinstance(fallback_value, str) and fallback_value:
                texts.append(fallback_value)
    return _repair_possible_mojibake_text("".join(texts).strip())


def _extract_error_detail(payload) -> str:
    if isinstance(payload, str):
        return payload.strip()

    if isinstance(payload, dict):
        error_payload = payload.get("error")
        if isinstance(error_payload, dict):
            message = str(
                error_payload.get("message")
                or error_payload.get("msg")
                or error_payload.get("detail")
                or ""
            ).strip()
            code = str(error_payload.get("code") or "").strip()
            if message and code:
                return f"{message} ({code})"
            if message:
                return message
            if code:
                return code
        elif isinstance(error_payload, str) and error_payload.strip():
            return error_payload.strip()

        for key in ("message", "msg", "detail", "error_message", "errorMessage"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

        for value in payload.values():
            detail = _extract_error_detail(value)
            if detail:
                return detail

    if isinstance(payload, list):
        for item in payload:
            detail = _extract_error_detail(item)
            if detail:
                return detail

    return ""


def _raise_for_status_with_detail(response) -> None:
    try:
        response.raise_for_status()
        return
    except requests.HTTPError as exc:
        detail = ""
        try:
            detail = _extract_error_detail(response.json())
        except (AttributeError, ValueError, TypeError, json.JSONDecodeError):
            detail = ""

        if not detail:
            raw_text = getattr(response, "text", "")
            if isinstance(raw_text, bytes):
                encoding = getattr(response, "encoding", None) or "utf-8"
                try:
                    raw_text = raw_text.decode(encoding, errors="replace")
                except (LookupError, AttributeError):
                    raw_text = raw_text.decode("utf-8", errors="replace")
            detail = str(raw_text or "").strip()

        status_code = getattr(response, "status_code", None)
        reason = str(getattr(response, "reason", "") or "").strip()
        if status_code and reason:
            prefix = f"API 请求失败（{status_code} {reason}）"
        elif status_code:
            prefix = f"API 请求失败（{status_code}）"
        elif reason:
            prefix = f"API 请求失败（{reason}）"
        else:
            prefix = "API 请求失败"

        if detail:
            raise RuntimeError(f"{prefix}: {detail}") from exc
        raise RuntimeError(str(exc)) from exc


def _extract_stream_chunk(config: dict, payload: dict, *, has_delta: bool) -> str:
    if _resolve_provider(config) == "ark":
        event_type = str(payload.get("type") or "").strip().lower()
        if event_type == "response.output_text.delta":
            return _repair_possible_mojibake_text(str(payload.get("delta") or ""))
        if not has_delta and event_type == "response.output_text.done":
            return _repair_possible_mojibake_text(str(payload.get("text") or ""))
        if not has_delta and event_type == "response.completed":
            return _extract_response_text(payload.get("response") or payload)
        return ""

    choices = payload.get("choices") or []
    if not choices:
        return ""
    return _repair_possible_mojibake_text(str((choices[0].get("delta") or {}).get("content") or ""))


def request_chat_completion_text(
    config: dict,
    *,
    messages: list[dict],
    model: str | None = None,
    temperature: float = 0.3,
    response_format: dict | None = None,
    timeout: tuple[int, int] = (10, 120),
) -> str:
    resolved_model = str(model or config.get("model") or DEFAULT_AI_PUBLISH_CONFIG["model"])
    payload = _build_request_payload(
        config,
        messages=messages,
        model=resolved_model,
        temperature=temperature,
        stream=False,
        response_format=response_format,
    )

    response = requests.post(
        _request_url(config),
        headers=_request_headers(config),
        json=payload,
        timeout=timeout,
    )
    response.encoding = "utf-8"
    _raise_for_status_with_detail(response)
    data = response.json()
    return _extract_response_text(data)


def stream_chat_completion(config: dict, *, messages: list[dict], model: str | None = None):
    resolved_model = str(model or config.get("model") or DEFAULT_AI_PUBLISH_CONFIG["model"])
    payload = _build_request_payload(
        config,
        messages=messages,
        model=resolved_model,
        temperature=0.4,
        stream=True,
    )
    response = requests.post(
        _request_url(config),
        headers=_request_headers(config),
        json=payload,
        stream=True,
        timeout=(10, 600),
    )
    response.encoding = "utf-8"
    _raise_for_status_with_detail(response)

    has_delta = False
    for line in response.iter_lines(decode_unicode=True):
        if not line:
            continue
        if not str(line).startswith("data:"):
            continue
        raw_data = str(line)[5:].strip()
        if not raw_data or raw_data == "[DONE]":
            continue
        try:
            payload = json.loads(raw_data)
        except json.JSONDecodeError:
            continue

        delta = _extract_stream_chunk(config, payload, has_delta=has_delta)
        if delta:
            has_delta = True
            yield str(delta)


def test_ai_publish_connection(config: dict, *, model: str | None = None) -> dict:
    started_at = time.time()
    request_chat_completion_text(
        config,
        model=model,
        messages=[
            {"role": "system", "content": "你是一个连接测试助手。"},
            {"role": "user", "content": "请回复：连接成功"},
        ],
        temperature=0,
    )
    latency_ms = int((time.time() - started_at) * 1000)
    return {
        "provider": str(config.get("provider") or DEFAULT_AI_PUBLISH_CONFIG["provider"]),
        "model": str(model or config.get("model") or DEFAULT_AI_PUBLISH_CONFIG["model"]),
        "latencyMs": latency_ms,
    }


def load_ai_publish_context(base_dir: Path) -> dict:
    database_path = Path(base_dir) / "db" / "database.db"
    accounts = []
    materials = []
    if not database_path.exists():
        return {"accounts": accounts, "materials": materials}

    with sqlite3.connect(database_path) as conn:
        conn.row_factory = sqlite3.Row
        try:
            account_rows = conn.execute(
                """
                SELECT id, type, filePath, userName, status
                FROM user_info
                ORDER BY id ASC
                """
            ).fetchall()
        except sqlite3.Error:
            account_rows = []

        for row in account_rows:
            accounts.append(
                {
                    "id": int(row["id"]),
                    "platform": PLATFORM_LABEL_BY_TYPE.get(int(row["type"]), "unknown"),
                    "name": str(row["userName"] or "").strip(),
                    "filePath": str(row["filePath"] or "").strip(),
                    "status": int(row["status"] or 0),
                }
            )

        try:
            material_rows = conn.execute(
                """
                SELECT id, filename, file_path
                FROM file_records
                ORDER BY id ASC
                """
            ).fetchall()
        except sqlite3.Error:
            material_rows = []

        for row in material_rows:
            filename = str(row["filename"] or "").strip()
            file_path = str(row["file_path"] or "").strip()
            suffix = Path(filename or file_path).suffix.lower()
            kind = "video" if suffix in {".mp4", ".avi", ".mov", ".wmv", ".flv", ".mkv", ".m4v"} else "note"
            materials.append(
                {
                    "id": int(row["id"]),
                    "name": filename,
                    "filePath": file_path,
                    "kind": kind,
                }
            )

    return {"accounts": accounts, "materials": materials}


def _dedupe_material_candidates(materials: Iterable[dict]) -> list[dict]:
    deduped = []
    seen_keys = set()
    for material in materials or []:
        if not isinstance(material, dict):
            continue
        file_path = str(material.get("filePath") or "").strip()
        name = str(material.get("name") or "").strip()
        key = (file_path.lower(), name.lower())
        if not file_path or key in seen_keys:
            continue
        seen_keys.add(key)
        deduped.append(
            {
                "id": material.get("id"),
                "name": name or ntpath.basename(file_path.replace("/", "\\")) or file_path,
                "filePath": file_path,
                "kind": str(material.get("kind") or "video").strip().lower() or "video",
            }
        )
    return deduped


def _extract_local_video_paths_from_text(text: str) -> list[str]:
    normalized_text = str(text or "")
    paths = []
    seen = set()
    for match in WINDOWS_ABSOLUTE_VIDEO_PATH_RE.findall(normalized_text):
        candidate = str(match or "").strip().rstrip("\"',，。；;、）)]}>")
        if not candidate:
            continue
        if Path(candidate).suffix.lower() not in LOCAL_VIDEO_EXTENSIONS:
            continue
        key = candidate.lower()
        if key in seen:
            continue
        seen.add(key)
        paths.append(candidate)
    return paths


def _build_message_local_material_candidates(messages: Iterable[dict]) -> list[dict]:
    materials = []
    for message in normalize_chat_messages(messages):
        if message.get("role") != "user":
            continue

        for attachment in message.get("attachments") or []:
            local_path = str(attachment.get("localPath") or attachment.get("filePath") or "").strip()
            mime_type = str(attachment.get("mimeType") or "").strip().lower()
            if not local_path or not (mime_type.startswith("video/") or Path(local_path).suffix.lower() in LOCAL_VIDEO_EXTENSIONS):
                continue
            materials.append(
                {
                    "id": f"local:{local_path}",
                    "name": str(attachment.get("originalName") or "").strip() or ntpath.basename(local_path.replace("/", "\\")) or local_path,
                    "filePath": local_path,
                    "kind": "video",
                }
            )

        for local_path in _extract_local_video_paths_from_text(message.get("content") or ""):
            materials.append(
                {
                    "id": f"local:{local_path}",
                    "name": ntpath.basename(local_path.replace("/", "\\")) or local_path,
                    "filePath": local_path,
                    "kind": "video",
                }
            )

    return _dedupe_material_candidates(materials)


def _normalize_publish_preview(
    parsed: dict,
    available_materials: list[dict],
    *,
    local_material_candidates: list[dict] | None = None,
) -> dict:
    accounts = [item for item in (parsed.get("accounts") or []) if isinstance(item, dict)]
    title = str(parsed.get("title") or "").strip()
    content = str(parsed.get("content") or "").strip()
    tags = [str(item).strip() for item in (parsed.get("tags") or []) if str(item).strip()]
    schedule_type = "scheduled" if str(parsed.get("scheduleType") or "").strip().lower() == "scheduled" else "now"
    schedule_time = str(parsed.get("scheduleTime") or "").strip()

    material_by_id = {}
    material_by_name = {}
    for material in available_materials or []:
        file_path = str(material.get("filePath") or "").strip()
        if not file_path:
            continue
        material_id = str(material.get("id") or "").strip()
        material_name = str(material.get("name") or "").strip().lower()
        if material_id:
            material_by_id[material_id] = material
        if material_name:
            material_by_name[material_name] = material

    normalized_works = []
    for item in (parsed.get("works") or []):
        if not isinstance(item, dict):
            continue

        kind = str(item.get("kind") or "video").strip().lower() or "video"
        file_path = str(item.get("filePath") or "").strip()
        work_name = str(item.get("name") or "").strip()
        if not file_path:
            material = material_by_id.get(str(item.get("id") or "").strip()) or material_by_name.get(work_name.lower())
            if material:
                file_path = str(material.get("filePath") or "").strip()
                if not work_name:
                    work_name = str(material.get("name") or "").strip()
                if kind == "video":
                    kind = str(material.get("kind") or "video").strip().lower() or "video"
        if kind == "video" and file_path:
            normalized_works.append(
                {
                    "name": work_name or ntpath.basename(file_path.replace("/", "\\")) or file_path,
                    "kind": "video",
                    "filePath": file_path,
                }
            )

    preferred_materials = local_material_candidates or available_materials
    if not normalized_works and len(preferred_materials) == 1:
        material = preferred_materials[0]
        file_path = str(material.get("filePath") or "").strip()
        if file_path:
            normalized_works.append(
                {
                    "name": str(material.get("name") or "").strip() or ntpath.basename(file_path.replace("/", "\\")) or file_path,
                    "kind": "video",
                    "filePath": file_path,
                }
            )

    missing_fields = []
    if not accounts:
        missing_fields.append("accounts")
    if not normalized_works:
        missing_fields.append("works")
    if not title:
        missing_fields.append("title")
    if schedule_type == "scheduled" and not schedule_time:
        missing_fields.append("scheduleTime")

    return {
        "intent": "publish",
        "ready": not missing_fields,
        "missingFields": missing_fields,
        "accounts": accounts,
        "works": normalized_works,
        "title": title,
        "content": content,
        "tags": tags,
        "scheduleType": schedule_type,
        "scheduleTime": schedule_time,
    }


def _extract_json_candidate(text: str) -> dict | None:
    if not text:
        return None

    stripped = text.strip()
    candidates = [stripped]
    if "```json" in stripped:
        for block in stripped.split("```json")[1:]:
            candidate = block.split("```", 1)[0].strip()
            if candidate:
                candidates.append(candidate)
    elif "```" in stripped:
        for block in stripped.split("```")[1:]:
            candidate = block.split("```", 1)[0].strip()
            if candidate:
                candidates.append(candidate)

    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


def analyze_publish_task(
    config: dict,
    *,
    messages: list[dict],
    assistant_text: str,
    context: dict,
    model: str | None = None,
) -> dict | None:
    local_material_candidates = _build_message_local_material_candidates(messages)
    available_materials = _dedupe_material_candidates([*(context.get("materials") or []), *local_material_candidates])
    context_payload = {
        "accounts": context.get("accounts") or [],
        "materials": available_materials,
    }
    prompt_messages = [
        {"role": "system", "content": TASK_ANALYZER_PROMPT},
        {
            "role": "user",
            "content": json.dumps(
                {
                    "conversation": normalize_messages(messages),
                    "assistantReply": assistant_text,
                    "availableContext": context_payload,
                },
                ensure_ascii=False,
            ),
        },
    ]

    raw_text = ""
    try:
        raw_text = request_chat_completion_text(
            config,
            model=model,
            messages=prompt_messages,
            temperature=0,
            response_format={"type": "json_object"},
        )
    except Exception:
        raw_text = request_chat_completion_text(
            config,
            model=model,
            messages=prompt_messages,
            temperature=0,
        )

    parsed = _extract_json_candidate(raw_text)
    if not parsed:
        return None

    intent = str(parsed.get("intent") or "chat").strip().lower()
    if intent != "publish":
        return None

    return _normalize_publish_preview(
        parsed,
        available_materials,
        local_material_candidates=local_material_candidates,
    )


def _resolve_publish_center_work_path(base_dir: Path, raw_file_path: str) -> Path:
    normalized_path = str(raw_file_path or "").strip()
    if not normalized_path:
        raise ValueError("作品文件路径不能为空")

    if Path(normalized_path).is_absolute():
        candidate = Path(normalized_path).resolve()
    else:
        work_dir = (Path(base_dir) / "videoFile").resolve()
        candidate = (work_dir / normalized_path).resolve()
        try:
            candidate.relative_to(work_dir)
        except ValueError as exc:
            raise ValueError(f"作品文件路径无效: {normalized_path}") from exc

    if not candidate.exists():
        raise ValueError(f"作品文件不存在: {normalized_path}")
    return candidate


def _build_publish_center_attachment(file_path: Path) -> dict:
    mime_type = str(mimetypes.guess_type(file_path.name)[0] or "").strip().lower() or "application/octet-stream"
    data_url = ""
    if mime_type.startswith("image/"):
        encoded = base64.b64encode(file_path.read_bytes()).decode("ascii")
        data_url = f"data:{mime_type};base64,{encoded}"

    return {
        "localPath": str(file_path),
        "dataUrl": data_url,
        "mimeType": mime_type,
        "originalName": file_path.name,
        "sizeBytes": int(file_path.stat().st_size),
    }


def _find_local_command(command_name: str) -> str | None:
    bundled_dir = _bundled_ffmpeg_dir()
    bundled_candidates = [bundled_dir / command_name]
    if not command_name.lower().endswith(".exe"):
        bundled_candidates.append(bundled_dir / f"{command_name}.exe")
    for candidate in bundled_candidates:
        if candidate.exists():
            return str(candidate)

    resolved = shutil.which(command_name)
    if resolved:
        return resolved

    if not command_name.lower().endswith(".exe"):
        resolved = shutil.which(f"{command_name}.exe")
        if resolved:
            return resolved
    return None


def _require_local_command(command_name: str, display_name: str) -> str:
    resolved = _find_local_command(command_name)
    if resolved:
        return resolved
    bundled_dir = _bundled_ffmpeg_dir()
    raise RuntimeError(f"未找到 {display_name}，请先安装并加入 PATH，或放到项目目录 {bundled_dir} 后再使用视频 AI 生成")


def _run_local_media_command(command: list[str], *, error_prefix: str) -> subprocess.CompletedProcess[str]:
    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            creationflags=creation_flags,
        )
    except OSError as exc:
        raise RuntimeError(f"{error_prefix}: {exc}") from exc

    if completed.returncode == 0:
        return completed

    detail = str(completed.stderr or completed.stdout or "").strip()
    if not detail:
        detail = f"退出码 {completed.returncode}"
    raise RuntimeError(f"{error_prefix}: {detail}")


def _probe_video_duration_seconds(video_path: Path) -> float | None:
    ffprobe_path = _require_local_command("ffprobe", "ffprobe")
    completed = _run_local_media_command(
        [
            ffprobe_path,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(video_path),
        ],
        error_prefix=f"读取视频时长失败（{video_path.name}）",
    )
    raw_duration = str(completed.stdout or "").strip()
    if not raw_duration or raw_duration.lower() == "n/a":
        return None

    try:
        duration_seconds = float(raw_duration)
    except ValueError:
        return None
    return max(duration_seconds, 0.0)


def _build_video_frame_timestamps(
    duration_seconds: float | None,
    *,
    frame_count: int = LOCAL_VIDEO_FRAME_COUNT,
) -> list[float]:
    if not duration_seconds or duration_seconds <= 0.2:
        return [0.0]

    target_count = max(1, int(frame_count))
    max_timestamp = max(duration_seconds - 0.1, 0.0)
    timestamps = []
    seen = set()

    for index in range(target_count):
        fraction = (index + 1) / (target_count + 1)
        timestamp = max(0.0, min(max_timestamp, duration_seconds * fraction))
        rounded_timestamp = round(timestamp, 3)
        dedupe_key = int(rounded_timestamp * 1000)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        timestamps.append(rounded_timestamp)

    return timestamps or [0.0]


def _extract_video_frame_at_timestamp(
    ffmpeg_path: str,
    *,
    video_path: Path,
    output_path: Path,
    timestamp_seconds: float,
) -> None:
    _run_local_media_command(
        [
            ffmpeg_path,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-ss",
            f"{timestamp_seconds:.3f}",
            "-i",
            str(video_path),
            "-frames:v",
            "1",
            "-vf",
            f"scale={LOCAL_VIDEO_FRAME_MAX_WIDTH}:{LOCAL_VIDEO_FRAME_MAX_WIDTH}:force_original_aspect_ratio=decrease",
            "-q:v",
            "2",
            str(output_path),
        ],
        error_prefix=f"抽取视频关键帧失败（{video_path.name}）",
    )
    if not output_path.exists() or output_path.stat().st_size <= 0:
        raise RuntimeError(f"抽取视频关键帧失败（{video_path.name}）: 未生成有效图片")


def _extract_video_frames(video_path: Path, output_dir: Path) -> list[Path]:
    ffmpeg_path = _require_local_command("ffmpeg", "FFmpeg")
    duration_seconds = _probe_video_duration_seconds(video_path)
    timestamps = _build_video_frame_timestamps(duration_seconds)
    frame_paths: list[Path] = []
    errors: list[str] = []

    for index, timestamp_seconds in enumerate(timestamps, start=1):
        frame_path = output_dir / f"frame-{index:02d}.jpg"
        try:
            _extract_video_frame_at_timestamp(
                ffmpeg_path,
                video_path=video_path,
                output_path=frame_path,
                timestamp_seconds=timestamp_seconds,
            )
        except RuntimeError as exc:
            errors.append(str(exc))
            continue
        frame_paths.append(frame_path)

    if frame_paths:
        return frame_paths

    fallback_frame_path = output_dir / "frame-01.jpg"
    try:
        _extract_video_frame_at_timestamp(
            ffmpeg_path,
            video_path=video_path,
            output_path=fallback_frame_path,
            timestamp_seconds=0.0,
        )
    except RuntimeError:
        pass
    else:
        return [fallback_frame_path]

    error_message = errors[0] if errors else f"抽取视频关键帧失败（{video_path.name}）"
    raise RuntimeError(error_message)


def _video_has_audio_stream(video_path: Path) -> bool:
    ffprobe_path = _require_local_command("ffprobe", "ffprobe")
    completed = _run_local_media_command(
        [
            ffprobe_path,
            "-v",
            "error",
            "-select_streams",
            "a:0",
            "-show_entries",
            "stream=codec_type",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(video_path),
        ],
        error_prefix=f"检测视频音轨失败（{video_path.name}）",
    )
    return bool(str(completed.stdout or "").strip())


def _extract_video_audio(video_path: Path, output_path: Path) -> None:
    ffmpeg_path = _require_local_command("ffmpeg", "FFmpeg")
    _run_local_media_command(
        [
            ffmpeg_path,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(video_path),
            "-vn",
            "-ac",
            "1",
            "-ar",
            str(LOCAL_AUDIO_SAMPLE_RATE),
            str(output_path),
        ],
        error_prefix=f"提取视频音频失败（{video_path.name}）",
    )
    if not output_path.exists() or output_path.stat().st_size <= 0:
        raise RuntimeError(f"提取视频音频失败（{video_path.name}）: 未生成有效音频文件")


def _ensure_bundled_vendor_python_path() -> None:
    vendor_dir = _bundled_vendor_python_dir()
    if not vendor_dir.exists():
        return

    vendor_dir_text = str(vendor_dir)
    normalized_existing_paths = {str(Path(item).resolve()) for item in sys.path if item}
    if str(vendor_dir.resolve()) not in normalized_existing_paths:
        sys.path.insert(0, vendor_dir_text)


@lru_cache(maxsize=1)
def _load_local_whisper_model():
    _ensure_bundled_vendor_python_path()

    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        vendor_dir = _bundled_vendor_python_dir()
        raise RuntimeError(f"未安装 faster-whisper，请先安装依赖，或放到项目目录 {vendor_dir} 后再使用视频 AI 生成") from exc

    attempted_devices = [LOCAL_WHISPER_DEVICE]
    if LOCAL_WHISPER_DEVICE == "auto":
        attempted_devices.append("cpu")

    model_source: str | Path = LOCAL_WHISPER_MODEL_NAME
    bundled_model_dir = _bundled_whisper_model_dir()
    if bundled_model_dir.exists():
        model_source = bundled_model_dir

    last_error: Exception | None = None
    for device in attempted_devices:
        try:
            return WhisperModel(
                str(model_source),
                device=device,
                compute_type=LOCAL_WHISPER_COMPUTE_TYPE,
            )
        except Exception as exc:  # pragma: no cover - depends on local runtime
            last_error = exc
            continue

    raise RuntimeError(f"Whisper 模型加载失败: {last_error}") from last_error


def _transcribe_audio_with_whisper(audio_path: Path) -> str:
    whisper_model = _load_local_whisper_model()
    try:
        segments, _ = whisper_model.transcribe(
            str(audio_path),
            language="zh",
            vad_filter=True,
            beam_size=1,
            condition_on_previous_text=False,
        )
    except Exception as exc:
        raise RuntimeError(f"Whisper 转录失败（{audio_path.name}）: {exc}") from exc

    transcript_segments: list[str] = []
    total_chars = 0
    for segment in segments:
        segment_text = str(getattr(segment, "text", "") or "").strip()
        if not segment_text:
            continue

        remaining_chars = LOCAL_TRANSCRIPT_MAX_CHARS - total_chars
        if remaining_chars <= 0:
            break

        clipped_text = segment_text[:remaining_chars]
        transcript_segments.append(clipped_text)
        total_chars += len(clipped_text)

    return "\n".join(transcript_segments).strip()


def _build_publish_center_video_context(video_path: Path) -> tuple[list[dict], str]:
    with tempfile.TemporaryDirectory(prefix="publish_center_ai_") as temp_dir:
        temp_path = Path(temp_dir)
        frames_dir = temp_path / "frames"
        frames_dir.mkdir(parents=True, exist_ok=True)

        frame_paths = _extract_video_frames(video_path, frames_dir)
        attachments = [_build_publish_center_attachment(frame_path) for frame_path in frame_paths]
        if not attachments:
            raise RuntimeError(f"未能从视频中提取到关键帧: {video_path.name}")

        if not _video_has_audio_stream(video_path):
            return attachments, "该视频未检测到音频流，请以关键帧内容为主。"

        audio_path = temp_path / "audio.wav"
        _extract_video_audio(video_path, audio_path)
        transcript = _transcribe_audio_with_whisper(audio_path)
        if transcript:
            return attachments, f"音频转录（可能有少量误差，请结合画面理解）：\n{transcript}"
        return attachments, "未识别到清晰的音频转录，请以关键帧内容为主。"


def _normalize_publish_center_work_paths(work: dict) -> list[str]:
    kind = str(work.get("kind") or "video").strip().lower() or "video"
    if kind == "note":
        return [str(item).strip() for item in (work.get("filePaths") or []) if str(item).strip()]

    file_path = str(work.get("filePath") or "").strip()
    if file_path:
        return [file_path]
    return [str(item).strip() for item in (work.get("filePaths") or []) if str(item).strip()]


def _build_publish_center_work_context(
    config: dict,
    work: dict,
    *,
    base_dir: Path,
) -> tuple[str, list[dict], str]:
    _ = config

    kind = str(work.get("kind") or "video").strip().lower() or "video"
    file_paths = _normalize_publish_center_work_paths(work)
    if not file_paths:
        raise ValueError("作品文件不能为空")

    resolved_paths = [_resolve_publish_center_work_path(base_dir, raw_path) for raw_path in file_paths]
    if kind == "video":
        attachments, analysis_text = _build_publish_center_video_context(resolved_paths[0])
    else:
        attachments = [_build_publish_center_attachment(file_path) for file_path in resolved_paths]
        analysis_text = ""

    if kind == "note" and any(not str(item.get("mimeType") or "").startswith("image/") for item in attachments):
        raise ValueError("图文作品中存在不是图片的文件，暂时无法生成文案")

    work_name = str(work.get("name") or "").strip()
    if not work_name:
        work_name = resolved_paths[0].name
    return work_name, attachments, analysis_text


def _build_publish_center_user_prompt(
    *,
    work_name: str,
    work_kind: str,
    work_index: int,
    work_count: int,
    platforms: list[str],
    account_names: list[str],
    analysis_text: str = "",
) -> str:
    platform_text = "、".join([str(item).strip() for item in platforms if str(item).strip()]) or "未指定"
    account_text = "、".join([str(item).strip() for item in account_names if str(item).strip()]) or "未指定"
    kind_label = "图文" if work_kind == "note" else "视频"
    prompt_lines = [
        "请基于我提供的作品素材，生成可直接填写到发布中心里的标题和文案。",
        f"当前作品序号：第 {work_index} / {work_count} 个",
        f"作品类型：{kind_label}",
        f"作品名称：{work_name}",
        f"目标平台：{platform_text}",
        f"目标账号：{account_text}",
    ]

    if work_kind == "video":
        prompt_lines.append("作品画面的关键帧图片已作为附件提供。")
        if analysis_text:
            prompt_lines.append("以下是本地预处理得到的辅助信息，请结合附件图片一起理解：")
            prompt_lines.append(analysis_text)

    prompt_lines.append('请只返回 JSON：{"title":"...","content":"..."}')
    return "\n".join(prompt_lines)


def _parse_publish_center_copy_response(raw_text: str) -> dict:
    parsed = _extract_json_candidate(raw_text)
    if not parsed:
        raise RuntimeError("AI 返回结果不是有效的 JSON")

    title = _repair_possible_mojibake_text(str(parsed.get("title") or "").strip())
    content = _repair_possible_mojibake_text(str(parsed.get("content") or "").strip())
    if not title or not content:
        raise RuntimeError("AI 返回的标题或文案为空")
    return {
        "title": title,
        "content": content,
    }


def _generate_publish_center_copy_item(
    config: dict,
    *,
    work: dict,
    work_index: int,
    work_count: int,
    base_dir: Path,
    platforms: list[str],
    account_names: list[str],
    model: str | None = None,
) -> dict:
    work_kind = str(work.get("kind") or "video").strip().lower() or "video"
    work_name, attachments, analysis_text = _build_publish_center_work_context(
        config,
        work,
        base_dir=base_dir,
    )
    messages = [
        {"role": "system", "content": PUBLISH_CENTER_COPY_PROMPT},
        {
            "role": "user",
            "content": _build_publish_center_user_prompt(
                work_name=work_name,
                work_kind=work_kind,
                work_index=work_index,
                work_count=work_count,
                platforms=platforms,
                account_names=account_names,
                analysis_text=analysis_text,
            ),
            "attachments": attachments,
        },
    ]

    raw_text = ""
    try:
        raw_text = request_chat_completion_text(
            config,
            model=model,
            messages=messages,
            temperature=0.4,
            response_format={"type": "json_object"},
        )
    except Exception:
        raw_text = request_chat_completion_text(
            config,
            model=model,
            messages=messages,
            temperature=0.4,
        )

    parsed = _parse_publish_center_copy_response(raw_text)
    return {
        "name": work_name,
        "kind": work_kind,
        "title": parsed["title"],
        "content": parsed["content"],
    }


def generate_publish_center_copy(
    config: dict,
    *,
    works: Iterable[dict],
    base_dir: Path,
    platforms: Iterable[str] | None = None,
    account_names: Iterable[str] | None = None,
    model: str | None = None,
) -> dict:
    normalized_works = [item for item in works or [] if isinstance(item, dict)]
    if not normalized_works:
        raise ValueError("至少需要一个作品才能生成标题和文案")

    resolved_base_dir = Path(base_dir)
    normalized_platforms = [str(item).strip() for item in (platforms or []) if str(item).strip()]
    normalized_account_names = [str(item).strip() for item in (account_names or []) if str(item).strip()]
    indexed_works = list(enumerate(normalized_works, start=1))
    max_workers = min(PUBLISH_CENTER_COPY_MAX_CONCURRENCY, len(indexed_works))

    if max_workers <= 1:
        items = [
            _generate_publish_center_copy_item(
                config,
                work=work,
                work_index=index,
                work_count=len(indexed_works),
                base_dir=resolved_base_dir,
                platforms=normalized_platforms,
                account_names=normalized_account_names,
                model=model,
            )
            for index, work in indexed_works
        ]
    else:
        with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="publish-copy") as executor:
            futures = [
                executor.submit(
                    _generate_publish_center_copy_item,
                    config,
                    work=work,
                    work_index=index,
                    work_count=len(indexed_works),
                    base_dir=resolved_base_dir,
                    platforms=normalized_platforms,
                    account_names=normalized_account_names,
                    model=model,
                )
                for index, work in indexed_works
            ]
            items = [future.result() for future in futures]

    titles = [item["title"] for item in items]
    contents = [item["content"] for item in items]
    return {
        "items": items,
        "titles": titles,
        "contents": contents,
        "titleText": "\n\n".join(titles),
        "contentText": "\n\n".join(contents),
    }
