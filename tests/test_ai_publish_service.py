import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import requests

from myUtils.ai_publish_service import (
    analyze_publish_task,
    generate_publish_center_copy,
    normalize_chat_messages,
    request_chat_completion_text,
    stream_chat_completion,
)


class FakeJsonResponse:
    def __init__(self, payload):
        self.encoding = None
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class FakeStreamResponse:
    def __init__(self):
        self.encoding = None

    def raise_for_status(self):
        return None

    def iter_lines(self, decode_unicode=False):
        payload = json.dumps(
            {"choices": [{"delta": {"content": "你好"}}]},
            ensure_ascii=False,
        )
        if decode_unicode and self.encoding == "utf-8":
            yield f"data: {payload}"
            yield "data: [DONE]"
            return

        mojibake_payload = json.dumps(
            {"choices": [{"delta": {"content": "ä½ å¥½"}}]},
            ensure_ascii=False,
        )
        yield f"data: {mojibake_payload}"
        yield "data: [DONE]"


class FakeArkStreamResponse:
    def __init__(self):
        self.encoding = None

    def raise_for_status(self):
        return None

    def iter_lines(self, decode_unicode=False):
        payloads = [
            {"type": "response.output_text.delta", "delta": "你"},
            {"type": "response.output_text.delta", "delta": "好"},
            {"type": "response.completed", "response": {"output_text": "你好"}},
        ]
        for payload in payloads:
            yield f"data: {json.dumps(payload, ensure_ascii=False)}"


class FakeErrorResponse:
    def __init__(self, payload, *, status_code=400, reason="Bad Request"):
        self.encoding = None
        self._payload = payload
        self.status_code = status_code
        self.reason = reason
        self.text = json.dumps(payload, ensure_ascii=False)

    def raise_for_status(self):
        raise requests.HTTPError(
            f"{self.status_code} Client Error: {self.reason}",
            response=self,
        )

    def json(self):
        return self._payload


class AiPublishServiceAttachmentTests(unittest.TestCase):
    def test_normalize_chat_messages_keeps_local_path_only_attachment(self):
        normalized = normalize_chat_messages(
            [
                {
                    "role": "user",
                    "content": "帮我看看这个视频",
                    "attachments": [
                        {
                            "localPath": r"D:\social-auto-upload\videoFile\demo.mp4",
                            "mimeType": "video/mp4",
                            "originalName": "demo.mp4",
                        }
                    ],
                }
            ]
        )

        self.assertEqual(len(normalized), 1)
        self.assertEqual(len(normalized[0]["attachments"]), 1)
        self.assertEqual(
            normalized[0]["attachments"][0]["localPath"],
            r"D:\social-auto-upload\videoFile\demo.mp4",
        )

    def test_generate_publish_center_copy_formats_blank_line_separated_result(self):
        request_payloads = []

        def fake_request_chat_completion_text(*args, **kwargs):
            request_payloads.append(kwargs["messages"])
            prompt_text = kwargs["messages"][1]["content"]
            if "lesson-a.mp4" in prompt_text:
                return json.dumps({"title": "标题A", "content": "文案A"}, ensure_ascii=False)
            if "lesson-b.mp4" in prompt_text:
                return json.dumps({"title": "标题B", "content": "文案B"}, ensure_ascii=False)
            raise AssertionError(f"unexpected prompt: {prompt_text}")

        def fake_build_publish_center_work_context(*args, **kwargs):
            work = args[1]
            work_name = work["name"]
            if work_name == "lesson-a.mp4":
                return (
                    "lesson-a.mp4",
                    [
                        {
                            "mimeType": "image/jpeg",
                            "dataUrl": "data:image/jpeg;base64,AAA",
                            "localPath": r"D:\frames\lesson-a-01.jpg",
                            "originalName": "lesson-a-01.jpg",
                            "sizeBytes": 123,
                        }
                    ],
                    "音频转录A",
                )
            if work_name == "lesson-b.mp4":
                return (
                    "lesson-b.mp4",
                    [
                        {
                            "mimeType": "image/jpeg",
                            "dataUrl": "data:image/jpeg;base64,BBB",
                            "localPath": r"D:\frames\lesson-b-01.jpg",
                            "originalName": "lesson-b-01.jpg",
                            "sizeBytes": 456,
                        }
                    ],
                    "音频转录B",
                )
            raise AssertionError(f"unexpected work: {work_name}")

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
            base_dir = Path(tmp_dir)
            with patch("myUtils.ai_publish_service.request_chat_completion_text", side_effect=fake_request_chat_completion_text), patch(
                "myUtils.ai_publish_service._build_publish_center_work_context",
                side_effect=fake_build_publish_center_work_context,
            ):
                result = generate_publish_center_copy(
                    {
                        "provider": "ark",
                        "api_key": "sk-demo",
                        "api_base": "https://ark.cn-beijing.volces.com/api/v3",
                        "model": "doubao-seed-2-0-mini-260428",
                    },
                    works=[
                        {"kind": "video", "name": "lesson-a.mp4", "filePaths": ["lesson-a.mp4"]},
                        {"kind": "video", "name": "lesson-b.mp4", "filePaths": ["lesson-b.mp4"]},
                    ],
                    base_dir=base_dir,
                    platforms=["douyin"],
                    account_names=["千聊官号"],
                    model="doubao-seed-2-0-mini-260428",
                )

        self.assertEqual(result["titles"], ["标题A", "标题B"])
        self.assertEqual(result["contents"], ["文案A", "文案B"])
        self.assertEqual(result["titleText"], "标题A\n\n标题B")
        self.assertEqual(result["contentText"], "文案A\n\n文案B")
        self.assertEqual(len(result["items"]), 2)
        self.assertEqual(len(request_payloads), 2)
        payload_by_work_name = {
            next(
                line.split("：", 1)[1]
                for line in messages[1]["content"].splitlines()
                if line.startswith("作品名称：")
            ): messages
            for messages in request_payloads
        }
        self.assertEqual(
            payload_by_work_name["lesson-a.mp4"][1]["attachments"][0]["dataUrl"],
            "data:image/jpeg;base64,AAA",
        )
        self.assertIn("音频转录A", payload_by_work_name["lesson-a.mp4"][1]["content"])


class FakeFileStatusResponse:
    def __init__(self, payload):
        self.encoding = None
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class AiPublishServiceTests(unittest.TestCase):
    @staticmethod
    def _mojibake(text: str) -> str:
        return text.encode("utf-8").decode("latin1")

    def test_stream_chat_completion_forces_utf8_decoding(self):
        response = FakeStreamResponse()
        with patch("myUtils.ai_publish_service.requests.post", return_value=response):
            chunks = list(
                stream_chat_completion(
                    {
                        "api_key": "sk-demo",
                        "api_base": "https://example.com/v1",
                        "model": "demo-model",
                    },
                    messages=[{"role": "user", "content": "你好"}],
                )
            )

        self.assertEqual(chunks, ["你好"])

    def test_request_chat_completion_text_repairs_utf8_latin1_mojibake(self):
        broken_text = self._mojibake("你好呀～如果有发布任务需要安排，都可以告诉我哦。")

        with patch(
            "myUtils.ai_publish_service.requests.post",
            return_value=FakeJsonResponse({"output_text": broken_text}),
        ):
            text = request_chat_completion_text(
                {
                    "provider": "ark",
                    "api_key": "sk-demo",
                    "api_base": "https://ark.cn-beijing.volces.com/api/v3",
                    "model": "doubao-seed-2-0-mini-260428",
                },
                messages=[{"role": "user", "content": "你好"}],
                temperature=0,
            )

        self.assertEqual(text, "你好呀～如果有发布任务需要安排，都可以告诉我哦。")

    def test_request_chat_completion_text_repairs_mixed_chinese_and_mojibake(self):
        broken_suffix = self._mojibake("我是 social-auto-upload 的 AI 发布助手。")
        mixed_text = f"目前{broken_suffix}"

        with patch(
            "myUtils.ai_publish_service.requests.post",
            return_value=FakeJsonResponse({"output_text": mixed_text}),
        ):
            text = request_chat_completion_text(
                {
                    "provider": "ark",
                    "api_key": "sk-demo",
                    "api_base": "https://ark.cn-beijing.volces.com/api/v3",
                    "model": "doubao-seed-2-0-mini-260428",
                },
                messages=[{"role": "user", "content": "你是谁"}],
                temperature=0,
            )

        self.assertEqual(text, "目前我是 social-auto-upload 的 AI 发布助手。")

    def test_request_chat_completion_text_uses_ark_responses_api_for_volces_base(self):
        request_call = {}

        def fake_post(url, headers=None, json=None, timeout=None, **kwargs):
            request_call["url"] = url
            request_call["headers"] = headers
            request_call["json"] = json
            request_call["timeout"] = timeout
            return FakeJsonResponse({"output_text": "连接成功"})

        with patch("myUtils.ai_publish_service.requests.post", side_effect=fake_post):
            text = request_chat_completion_text(
                {
                    "provider": "custom",
                    "api_key": "sk-demo",
                    "api_base": "https://ark.cn-beijing.volces.com/api/v3/responses",
                    "model": "doubao-seed-2-0-mini-260428",
                },
                messages=[
                    {"role": "system", "content": "你是一个中文助手"},
                    {"role": "user", "content": "你好"},
                ],
                temperature=0,
            )

        self.assertEqual(text, "连接成功")
        self.assertEqual(
            request_call["url"],
            "https://ark.cn-beijing.volces.com/api/v3/responses",
        )
        self.assertEqual(
            request_call["json"],
            {
                "model": "doubao-seed-2-0-mini-260428",
                "input": [{"role": "user", "content": "你好"}],
                "instructions": "你是一个中文助手",
                "temperature": 0,
                "stream": False,
            },
        )

    def test_stream_chat_completion_parses_ark_response_deltas(self):
        request_call = {}

        def fake_post(url, headers=None, json=None, timeout=None, **kwargs):
            request_call["url"] = url
            request_call["json"] = json
            return FakeArkStreamResponse()

        with patch("myUtils.ai_publish_service.requests.post", side_effect=fake_post):
            chunks = list(
                stream_chat_completion(
                    {
                        "provider": "custom",
                        "api_key": "sk-demo",
                        "api_base": "https://ark.cn-beijing.volces.com/api/v3",
                        "model": "doubao-seed-2-0-mini-260428",
                    },
                    messages=[
                        {"role": "system", "content": "你是一个中文助手"},
                        {"role": "user", "content": "你好"},
                    ],
                )
            )

        self.assertEqual(
            request_call["url"],
            "https://ark.cn-beijing.volces.com/api/v3/responses",
        )
        self.assertEqual(
            request_call["json"],
            {
                "model": "doubao-seed-2-0-mini-260428",
                "input": [{"role": "user", "content": "你好"}],
                "instructions": "你是一个中文助手",
                "temperature": 0.4,
                "stream": True,
            },
        )
        self.assertEqual(chunks, ["你", "好"])

    def test_stream_chat_completion_repairs_ark_mojibake_deltas(self):
        broken_hello = self._mojibake("你好")

        class FakeBrokenArkStreamResponse:
            def __init__(self):
                self.encoding = None

            def raise_for_status(self):
                return None

            def iter_lines(self, decode_unicode=False):
                yield f"data: {json.dumps({'type': 'response.output_text.delta', 'delta': broken_hello}, ensure_ascii=False)}"

        with patch(
            "myUtils.ai_publish_service.requests.post",
            return_value=FakeBrokenArkStreamResponse(),
        ):
            chunks = list(
                stream_chat_completion(
                    {
                        "provider": "ark",
                        "api_key": "sk-demo",
                        "api_base": "https://ark.cn-beijing.volces.com/api/v3",
                        "model": "doubao-seed-2-0-mini-260428",
                    },
                    messages=[{"role": "user", "content": "你好"}],
                )
            )

        self.assertEqual("".join(chunks), "你好")

    def test_stream_chat_completion_repairs_mixed_ark_mojibake_delta(self):
        mixed_delta = f"目前{self._mojibake('我是 social-auto-upload 的 AI 发布助手。')}"

        class FakeBrokenMixedArkStreamResponse:
            def __init__(self):
                self.encoding = None

            def raise_for_status(self):
                return None

            def iter_lines(self, decode_unicode=False):
                yield f"data: {json.dumps({'type': 'response.output_text.delta', 'delta': mixed_delta}, ensure_ascii=False)}"

        with patch(
            "myUtils.ai_publish_service.requests.post",
            return_value=FakeBrokenMixedArkStreamResponse(),
        ):
            chunks = list(
                stream_chat_completion(
                    {
                        "provider": "ark",
                        "api_key": "sk-demo",
                        "api_base": "https://ark.cn-beijing.volces.com/api/v3",
                        "model": "doubao-seed-2-0-mini-260428",
                    },
                    messages=[{"role": "user", "content": "你是谁"}],
                )
            )

        self.assertEqual("".join(chunks), "目前我是 social-auto-upload 的 AI 发布助手。")

    def test_request_chat_completion_text_uses_openai_multimodal_messages_for_images(self):
        request_call = {}

        def fake_post(url, headers=None, json=None, timeout=None, **kwargs):
            request_call["url"] = url
            request_call["json"] = json
            return FakeJsonResponse({"choices": [{"message": {"content": "ok"}}]})

        with patch("myUtils.ai_publish_service.requests.post", side_effect=fake_post):
            text = request_chat_completion_text(
                {
                    "provider": "openai",
                    "api_key": "sk-demo",
                    "api_base": "https://api.openai.com/v1",
                    "model": "gpt-4.1-mini",
                },
                messages=[
                    {
                        "role": "user",
                        "content": "帮我看看这张图",
                        "attachments": [
                            {
                                "mimeType": "image/png",
                                "dataUrl": "data:image/png;base64,AAA",
                            }
                        ],
                    }
                ],
                temperature=0,
            )

        self.assertEqual(text, "ok")
        self.assertEqual(
            request_call["json"]["messages"],
            [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "帮我看看这张图"},
                        {
                            "type": "image_url",
                            "image_url": {"url": "data:image/png;base64,AAA", "detail": "auto"},
                        },
                    ],
                }
            ],
        )

    def test_request_chat_completion_text_uses_ark_multimodal_input_for_images(self):
        request_call = {}

        def fake_post(url, headers=None, json=None, timeout=None, **kwargs):
            request_call["url"] = url
            request_call["json"] = json
            return FakeJsonResponse({"output_text": "ok"})

        with patch("myUtils.ai_publish_service.requests.post", side_effect=fake_post):
            text = request_chat_completion_text(
                {
                    "provider": "ark",
                    "api_key": "sk-demo",
                    "api_base": "https://ark.cn-beijing.volces.com/api/v3",
                    "model": "doubao-seed-2-0-mini-260428",
                },
                messages=[
                    {
                        "role": "user",
                        "content": "帮我看看这张图",
                        "attachments": [
                            {
                                "mimeType": "image/png",
                                "dataUrl": "data:image/png;base64,AAA",
                            }
                        ],
                    }
                ],
                temperature=0,
            )

        self.assertEqual(text, "ok")
        self.assertEqual(
            request_call["json"]["input"],
            [
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": "帮我看看这张图"},
                        {"type": "input_image", "image_url": "data:image/png;base64,AAA"},
                    ],
                }
            ],
        )

    def test_request_chat_completion_text_uses_ark_file_input_for_audio_and_files_api_for_video(self):
        request_calls = []
        status_calls = []

        def fake_post(url, headers=None, json=None, timeout=None, data=None, files=None, **kwargs):
            request_calls.append(
                {
                    "url": url,
                    "headers": headers,
                    "json": json,
                    "data": data,
                    "files": files,
                    "timeout": timeout,
                }
            )
            if url.endswith("/files"):
                return FakeJsonResponse({"id": "file_video_123"})
            return FakeJsonResponse({"output_text": "ok"})

        def fake_get(url, headers=None, timeout=None, **kwargs):
            status_calls.append({"url": url, "headers": headers, "timeout": timeout})
            return FakeFileStatusResponse({"id": "file_video_123", "status": "processed"})

        with (
            patch("myUtils.ai_publish_service.requests.post", side_effect=fake_post),
            patch("myUtils.ai_publish_service.requests.get", side_effect=fake_get),
        ):
            text = request_chat_completion_text(
                {
                    "provider": "ark",
                    "api_key": "sk-demo",
                    "api_base": "https://ark.cn-beijing.volces.com/api/v3",
                    "model": "doubao-seed-2-0-mini-260428",
                },
                messages=[
                    {
                        "role": "user",
                        "content": "帮我看看这段音频和视频里说了什么",
                        "attachments": [
                            {
                                "mimeType": "audio/mpeg",
                                "dataUrl": "data:audio/mpeg;base64,AAA",
                                "originalName": "voice.mp3",
                            },
                            {
                                "mimeType": "video/mp4",
                                "dataUrl": "data:video/mp4;base64,QkJC",
                                "originalName": "clip.mp4",
                            },
                        ],
                    }
                ],
                temperature=0,
            )

        self.assertEqual(text, "ok")
        self.assertEqual(status_calls[0]["url"], "https://ark.cn-beijing.volces.com/api/v3/files/file_video_123")
        self.assertEqual(
            request_calls[1]["json"]["input"],
            [
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": "帮我看看这段音频和视频里说了什么"},
                        {
                            "type": "input_file",
                            "filename": "voice.mp3",
                            "file_data": "data:audio/mpeg;base64,AAA",
                        },
                        {
                            "type": "input_video",
                            "file_id": "file_video_123",
                        },
                    ],
                }
            ],
        )

    def test_request_chat_completion_text_uploads_ark_video_via_files_api(self):
        request_calls = []
        status_calls = []

        def fake_post(url, headers=None, json=None, timeout=None, data=None, files=None, **kwargs):
            request_calls.append(
                {
                    "url": url,
                    "headers": headers,
                    "json": json,
                    "data": data,
                    "files": files,
                    "timeout": timeout,
                }
            )
            if url.endswith("/files"):
                return FakeJsonResponse({"id": "file_video_123"})
            return FakeJsonResponse({"output_text": "ok"})

        def fake_get(url, headers=None, timeout=None, **kwargs):
            status_calls.append({"url": url, "headers": headers, "timeout": timeout})
            return FakeFileStatusResponse({"id": "file_video_123", "status": "processed"})

        with (
            patch("myUtils.ai_publish_service.requests.post", side_effect=fake_post),
            patch("myUtils.ai_publish_service.requests.get", side_effect=fake_get),
        ):
            text = request_chat_completion_text(
                {
                    "provider": "ark",
                    "api_key": "sk-demo",
                    "api_base": "https://ark.cn-beijing.volces.com/api/v3",
                    "model": "doubao-seed-2-0-mini-260428",
                },
                messages=[
                    {
                        "role": "user",
                        "content": "帮我看看这段视频讲了什么",
                        "attachments": [
                            {
                                "mimeType": "video/mp4",
                                "dataUrl": "data:video/mp4;base64,QkJC",
                                "originalName": "clip.mp4",
                            }
                        ],
                    }
                ],
                temperature=0,
            )

        self.assertEqual(text, "ok")
        self.assertEqual(len(request_calls), 2)
        self.assertEqual(request_calls[0]["url"], "https://ark.cn-beijing.volces.com/api/v3/files")
        self.assertEqual(request_calls[0]["data"], {"purpose": "user_data"})
        self.assertEqual(request_calls[0]["files"]["file"], ("clip.mp4", b"BBB", "video/mp4"))
        self.assertEqual(status_calls[0]["url"], "https://ark.cn-beijing.volces.com/api/v3/files/file_video_123")
        self.assertEqual(
            request_calls[1]["json"]["input"],
            [
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": "帮我看看这段视频讲了什么"},
                        {"type": "input_video", "file_id": "file_video_123"},
                    ],
                }
            ],
        )

    def test_stream_chat_completion_uploads_ark_video_via_files_api(self):
        request_calls = []
        status_calls = []

        def fake_post(url, headers=None, json=None, timeout=None, data=None, files=None, **kwargs):
            request_calls.append(
                {
                    "url": url,
                    "headers": headers,
                    "json": json,
                    "data": data,
                    "files": files,
                    "timeout": timeout,
                }
            )
            if url.endswith("/files"):
                return FakeJsonResponse({"id": "file_video_123"})
            return FakeArkStreamResponse()

        def fake_get(url, headers=None, timeout=None, **kwargs):
            status_calls.append({"url": url, "headers": headers, "timeout": timeout})
            return FakeFileStatusResponse({"id": "file_video_123", "status": "processed"})

        with (
            patch("myUtils.ai_publish_service.requests.post", side_effect=fake_post),
            patch("myUtils.ai_publish_service.requests.get", side_effect=fake_get),
        ):
            chunks = list(
                stream_chat_completion(
                    {
                        "provider": "ark",
                        "api_key": "sk-demo",
                        "api_base": "https://ark.cn-beijing.volces.com/api/v3",
                        "model": "doubao-seed-2-0-mini-260428",
                    },
                    messages=[
                        {
                            "role": "user",
                            "content": "视频说了什么",
                            "attachments": [
                                {
                                    "mimeType": "video/mp4",
                                    "dataUrl": "data:video/mp4;base64,QkJC",
                                    "originalName": "clip.mp4",
                                }
                            ],
                        }
                    ],
                )
            )

        self.assertEqual(chunks, ["你", "好"])
        self.assertEqual(len(request_calls), 2)
        self.assertEqual(request_calls[0]["url"], "https://ark.cn-beijing.volces.com/api/v3/files")
        self.assertEqual(request_calls[0]["data"], {"purpose": "user_data"})
        self.assertEqual(request_calls[0]["files"]["file"], ("clip.mp4", b"BBB", "video/mp4"))
        self.assertEqual(status_calls[0]["url"], "https://ark.cn-beijing.volces.com/api/v3/files/file_video_123")
        self.assertEqual(
            request_calls[1]["json"]["input"],
            [
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": "视频说了什么"},
                        {"type": "input_video", "file_id": "file_video_123"},
                    ],
                }
            ],
        )

    def test_request_chat_completion_text_waits_until_ark_video_file_processed(self):
        request_calls = []
        status_payloads = [
            {"id": "file_video_123", "status": "processing"},
            {"id": "file_video_123", "status": "processed"},
        ]

        def fake_post(url, headers=None, json=None, timeout=None, data=None, files=None, **kwargs):
            request_calls.append(
                {
                    "url": url,
                    "headers": headers,
                    "json": json,
                    "data": data,
                    "files": files,
                    "timeout": timeout,
                }
            )
            if url.endswith("/files"):
                return FakeJsonResponse({"id": "file_video_123"})
            return FakeJsonResponse({"output_text": "ok"})

        def fake_get(url, headers=None, timeout=None, **kwargs):
            return FakeFileStatusResponse(status_payloads.pop(0))

        with (
            patch("myUtils.ai_publish_service.requests.post", side_effect=fake_post),
            patch("myUtils.ai_publish_service.requests.get", side_effect=fake_get) as mocked_get,
            patch("myUtils.ai_publish_service.time.sleep") as mocked_sleep,
        ):
            text = request_chat_completion_text(
                {
                    "provider": "ark",
                    "api_key": "sk-demo",
                    "api_base": "https://ark.cn-beijing.volces.com/api/v3",
                    "model": "doubao-seed-2-0-mini-260428",
                },
                messages=[
                    {
                        "role": "user",
                        "content": "帮我看看这段视频讲了什么",
                        "attachments": [
                            {
                                "mimeType": "video/mp4",
                                "dataUrl": "data:video/mp4;base64,QkJC",
                                "originalName": "clip.mp4",
                            }
                        ],
                    }
                ],
                temperature=0,
            )

        self.assertEqual(text, "ok")
        self.assertEqual(mocked_get.call_count, 2)
        mocked_sleep.assert_called_once()

    def test_request_chat_completion_text_returns_friendly_timeout_for_ark_video_upload(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
            video_path = Path(tmp_dir) / "clip.mp4"
            video_path.write_bytes(b"BBB")

            def fake_post(url, headers=None, json=None, timeout=None, data=None, files=None, **kwargs):
                if url.endswith("/files"):
                    raise requests.ConnectionError("Connection aborted.", TimeoutError("The write operation timed out"))
                return FakeJsonResponse({"output_text": "ok"})

            with patch("myUtils.ai_publish_service.requests.post", side_effect=fake_post):
                with self.assertRaisesRegex(RuntimeError, "视频上传到豆包 Files API 超时"):
                    request_chat_completion_text(
                        {
                            "provider": "ark",
                            "api_key": "sk-demo",
                            "api_base": "https://ark.cn-beijing.volces.com/api/v3",
                            "model": "doubao-seed-2-0-mini-260428",
                        },
                        messages=[
                            {
                                "role": "user",
                                "content": "帮我看看这段视频讲了什么",
                                "attachments": [
                                    {
                                        "mimeType": "video/mp4",
                                        "localPath": str(video_path),
                                        "originalName": "clip.mp4",
                                    }
                                ],
                            }
                        ],
                        temperature=0,
                    )

    def test_analyze_publish_task_supports_local_windows_absolute_video_path(self):
        request_payloads = []
        local_path = r"C:\Users\10300\Desktop\测试.mp4"

        def fake_request_chat_completion_text(*args, **kwargs):
            request_payloads.append(kwargs["messages"])
            return json.dumps(
                {
                    "intent": "publish",
                    "ready": False,
                    "missingFields": ["works", "tags"],
                    "accounts": [{"id": 3, "platform": "douyin", "name": "千聊官号"}],
                    "works": [],
                    "title": "千聊和海豚知道哪个卖课更容易成交",
                    "content": "成交容易度取决于两个东西，用户下单的路径长度和你的利润空间。",
                    "tags": [],
                    "scheduleType": "now",
                    "scheduleTime": "",
                },
                ensure_ascii=False,
            )

        with patch("myUtils.ai_publish_service.request_chat_completion_text", side_effect=fake_request_chat_completion_text):
            preview = analyze_publish_task(
                {
                    "provider": "ark",
                    "api_key": "sk-demo",
                    "api_base": "https://ark.cn-beijing.volces.com/api/v3",
                    "model": "doubao-seed-2-0-mini-260428",
                },
                messages=[
                    {
                        "role": "user",
                        "content": f"发到抖音千聊官号，视频素材 {local_path}，标题用千聊和海豚知道哪个卖课更容易成交，立即发布",
                    }
                ],
                assistant_text="我已经帮你整理好发布任务。",
                context={
                    "accounts": [{"id": 3, "platform": "douyin", "name": "千聊官号"}],
                    "materials": [],
                },
                model="doubao-seed-2-0-mini-260428",
            )

        self.assertIsNotNone(preview)
        self.assertEqual(preview["ready"], True)
        self.assertEqual(preview["missingFields"], [])
        self.assertEqual(
            preview["works"],
            [{"name": "测试.mp4", "kind": "video", "filePath": local_path}],
        )

        available_context = json.loads(request_payloads[0][1]["content"])["availableContext"]
        self.assertEqual(
            available_context["materials"],
            [{"id": f"local:{local_path}", "name": "测试.mp4", "filePath": local_path, "kind": "video"}],
        )

    def test_request_chat_completion_text_ignores_assistant_history_for_ark_responses(self):
        request_call = {}

        def fake_post(url, headers=None, json=None, timeout=None, **kwargs):
            request_call["url"] = url
            request_call["json"] = json
            return FakeJsonResponse({"output_text": "ok"})

        with patch("myUtils.ai_publish_service.requests.post", side_effect=fake_post):
            text = request_chat_completion_text(
                {
                    "provider": "ark",
                    "api_key": "sk-demo",
                    "api_base": "https://ark.cn-beijing.volces.com/api/v3",
                    "model": "doubao-seed-2-0-mini-260428",
                },
                messages=[
                    {"role": "system", "content": "你是一个中文助手"},
                    {"role": "assistant", "content": "你好，我是助手"},
                    {"role": "user", "content": "HI"},
                ],
                temperature=0,
            )

        self.assertEqual(text, "ok")
        self.assertEqual(
            request_call["json"]["input"],
            [{"role": "user", "content": "HI"}],
        )

    def test_request_chat_completion_text_includes_api_error_detail(self):
        with patch(
            "myUtils.ai_publish_service.requests.post",
            return_value=FakeErrorResponse(
                {
                    "error": {
                        "message": "视频文件输入格式不受支持",
                        "code": "invalid_input",
                    }
                }
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "视频文件输入格式不受支持"):
                request_chat_completion_text(
                    {
                        "provider": "ark",
                        "api_key": "sk-demo",
                        "api_base": "https://ark.cn-beijing.volces.com/api/v3",
                        "model": "doubao-seed-2-0-mini-260428",
                    },
                    messages=[{"role": "user", "content": "帮我看看这段视频"}],
                    temperature=0,
                )

    def test_stream_chat_completion_includes_api_error_detail(self):
        with patch(
            "myUtils.ai_publish_service.requests.post",
            return_value=FakeErrorResponse(
                {
                    "error": {
                        "message": "当前模型暂不支持 video input_file",
                        "code": "invalid_request",
                    }
                }
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "当前模型暂不支持 video input_file"):
                list(
                    stream_chat_completion(
                        {
                            "provider": "ark",
                            "api_key": "sk-demo",
                            "api_base": "https://ark.cn-beijing.volces.com/api/v3",
                            "model": "doubao-seed-2-0-mini-260428",
                        },
                        messages=[{"role": "user", "content": "视频讲了什么"}],
                    )
                )


if __name__ == "__main__":
    unittest.main()
