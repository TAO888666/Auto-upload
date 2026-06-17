import inspect
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from conf import LOCAL_CHROME_PATH
from patchright.async_api import async_playwright

import uploader.douyin_uploader.main as douyin_main
from uploader.douyin_uploader.main import _extract_douyin_qrcode_src, douyin_cookie_gen


PNG_DATA_URL = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO9WnZ0AAAAASUVORK5CYII="
)


class _AsyncPlaywrightContext:
    def __init__(self, playwright):
        self._playwright = playwright

    async def __aenter__(self):
        return self._playwright

    async def __aexit__(self, exc_type, exc, tb):
        return False


class FakeLocator:
    def __init__(self, name, count=0, src=None, visible=True, children=None, wait_error=None):
        self.name = name
        self._count = count
        self._src = src
        self._visible = visible
        self._children = children or {}
        self._wait_error = wait_error

    @property
    def first(self):
        return self

    def locator(self, selector):
        return self._children.get(selector, FakeLocator(selector))

    async def count(self):
        return self._count

    async def wait_for(self, **kwargs):
        if self._wait_error:
            raise self._wait_error
        return None

    async def get_attribute(self, name):
        if name == "src":
            return self._src
        return None

    async def is_visible(self):
        return self._count > 0 and self._visible

    async def click(self):
        return None


class FakePage:
    def __init__(self, *, texts=None, roles=None, selectors=None, url="https://creator.douyin.com/"):
        self._texts = texts or {}
        self._roles = roles or {}
        self._selectors = selectors or {}
        self.url = url

    def get_by_text(self, text, exact=False):
        return self._texts.get((text, exact), self._texts.get(text, FakeLocator(text)))

    def get_by_role(self, role, name=None):
        return self._roles.get((role, name), FakeLocator(f"{role}:{name}"))

    def locator(self, selector):
        return self._selectors.get(selector, FakeLocator(selector))


class DouyinLoginQrcodeTests(unittest.IsolatedAsyncioTestCase):
    async def test_extract_douyin_qrcode_src_does_not_wait_for_missing_scan_tab(self):
        missing_scan_tab = FakeLocator(
            "scan-tab",
            count=0,
            wait_error=AssertionError("should not wait on missing scan login tab"),
        )
        visible_qrcode = FakeLocator("qrcode", count=1, src=PNG_DATA_URL)
        page = FakePage(
            texts={("扫码登录", True): missing_scan_tab},
            roles={("img", "二维码"): visible_qrcode},
        )

        src = await douyin_main._extract_douyin_qrcode_src(page)

        self.assertEqual(src, PNG_DATA_URL)

    async def test_extract_douyin_qrcode_src_uses_visible_qrcode_image_without_scan_tab(self):
        html = f"""
        <!doctype html>
        <html lang="zh-CN">
          <body>
            <main>
              <section>
                <p>请使用抖音 App 扫码登录</p>
                <img alt="二维码" src="{PNG_DATA_URL}" />
              </section>
            </main>
          </body>
        </html>
        """

        with tempfile.TemporaryDirectory() as tmp_dir:
            html_path = Path(tmp_dir) / "douyin-login.html"
            html_path.write_text(html, encoding="utf-8")

            async with async_playwright() as playwright:
                launch_kwargs = {"headless": True}
                if LOCAL_CHROME_PATH:
                    launch_kwargs["executable_path"] = LOCAL_CHROME_PATH
                else:
                    launch_kwargs["channel"] = "chrome"

                browser = await playwright.chromium.launch(**launch_kwargs)
                try:
                    page = await browser.new_page()
                    await page.goto(html_path.as_uri())
                    src = await _extract_douyin_qrcode_src(page)
                finally:
                    await browser.close()

        self.assertEqual(src, PNG_DATA_URL)

    async def test_douyin_cookie_gen_headed_waits_for_login_without_extracting_qrcode(self):
        page = SimpleNamespace(
            url="https://creator.douyin.com/creator-micro/home",
            goto=AsyncMock(),
        )
        context = SimpleNamespace(
            new_page=AsyncMock(return_value=page),
            storage_state=AsyncMock(),
            close=AsyncMock(),
        )
        browser = SimpleNamespace(
            new_context=AsyncMock(return_value=context),
            close=AsyncMock(),
        )
        playwright = SimpleNamespace(
            chromium=SimpleNamespace(
                launch=AsyncMock(return_value=browser),
            )
        )

        with patch(
            "uploader.douyin_uploader.main.async_playwright",
            return_value=_AsyncPlaywrightContext(playwright),
        ):
            with patch(
                "uploader.douyin_uploader.main.set_init_script",
                new=AsyncMock(side_effect=lambda current_context: current_context),
            ):
                with patch(
                    "uploader.douyin_uploader.main._extract_douyin_qrcode_src",
                    new=AsyncMock(side_effect=AssertionError("headed login should not extract qrcode")),
                ) as mock_extract:
                    with patch(
                        "uploader.douyin_uploader.main._is_douyin_login_completed",
                        new=AsyncMock(return_value=True),
                    ):
                        with patch(
                            "uploader.douyin_uploader.main.cookie_auth",
                            new=AsyncMock(return_value=True),
                        ):
                            with patch(
                                "uploader.douyin_uploader.main.remove_qrcode_file",
                                return_value=False,
                            ):
                                result = await douyin_cookie_gen(
                                    "account.json",
                                    headless=False,
                                    poll_interval=0,
                                )

        self.assertTrue(result["success"])
        self.assertIsNone(result["qrcode"])
        mock_extract.assert_not_awaited()
        context.storage_state.assert_awaited_once_with(path="account.json")

    async def test_wait_for_douyin_login_accepts_unlimited_wait(self):
        page = FakePage(url="https://creator.douyin.com/creator-micro/home")
        qrcode_info = {"image_path": "qrcode.png", "image_data_url": PNG_DATA_URL}

        with patch(
            "uploader.douyin_uploader.main._is_douyin_login_completed",
            new=AsyncMock(side_effect=[False, False, True]),
        ) as mock_completed:
            with patch("uploader.douyin_uploader.main.asyncio.sleep", new=AsyncMock()) as mock_sleep:
                result = await douyin_main._wait_for_douyin_login(
                    page,
                    "account.json",
                    qrcode_info,
                    poll_interval=3,
                    max_checks=None,
                )

        self.assertTrue(result["success"])
        self.assertEqual(mock_completed.await_count, 3)
        self.assertEqual(mock_sleep.await_count, 2)

    async def test_wait_for_douyin_login_accepts_cookie_validation_without_page_transition(self):
        page = FakePage(url="https://creator.douyin.com/")
        context = SimpleNamespace(storage_state=AsyncMock())
        qrcode_info = {"image_path": "qrcode.png", "image_data_url": PNG_DATA_URL}

        with patch(
            "uploader.douyin_uploader.main._is_douyin_login_completed",
            new=AsyncMock(side_effect=[False, False]),
        ) as mock_completed:
            with patch(
                "uploader.douyin_uploader.main.cookie_auth",
                new=AsyncMock(side_effect=[False, True]),
            ) as mock_cookie_auth:
                with patch("uploader.douyin_uploader.main.asyncio.sleep", new=AsyncMock()) as mock_sleep:
                    result = await douyin_main._wait_for_douyin_login(
                        page,
                        "account.json",
                        qrcode_info,
                        context=context,
                        poll_interval=3,
                        max_checks=3,
                    )

        self.assertTrue(result["success"])
        self.assertEqual(mock_completed.await_count, 2)
        self.assertEqual(mock_cookie_auth.await_count, 2)
        context.storage_state.assert_awaited_with(path="account.json")
        self.assertEqual(mock_sleep.await_count, 1)

    def test_douyin_cookie_gen_defaults_to_unlimited_login_wait(self):
        max_checks = inspect.signature(douyin_main.douyin_cookie_gen).parameters["max_checks"]
        self.assertIsNone(max_checks.default)

    def test_douyin_main_source_keeps_single_login_helper_definitions(self):
        source = Path(douyin_main.__file__).read_text(encoding="utf-8")
        helper_names = [
            "_open_douyin_scan_login_tab",
            "_find_douyin_qrcode_locator",
            "_extract_douyin_qrcode_src",
            "_save_douyin_qrcode",
            "_is_douyin_login_completed",
            "_wait_for_douyin_login",
            "douyin_cookie_gen",
        ]

        for helper_name in helper_names:
            with self.subTest(helper_name=helper_name):
                self.assertEqual(source.count(f"async def {helper_name}("), 1)

    def test_douyin_main_source_does_not_keep_known_mojibake_markers(self):
        source = Path(douyin_main.__file__).read_text(encoding="utf-8")
        mojibake_markers = [
            "閹殿偆鐖滈惂璇茬秿",
            "娴滃瞼娣惍",
            "閺堫亝澹橀崚",
        ]

        for marker in mojibake_markers:
            with self.subTest(marker=marker):
                self.assertNotIn(marker, source)


if __name__ == "__main__":
    unittest.main()
