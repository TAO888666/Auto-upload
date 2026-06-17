import unittest

from uploader.douyin_uploader.main import DouYinBaseUploader


class FakeLocator:
    def __init__(self, name: str, count: int = 0, children=None):
        self.name = name
        self._count = count
        self._children = children or {}
        self.clicked = 0
        self.waited = 0

    @property
    def first(self):
        return self

    async def count(self):
        return self._count

    async def click(self):
        self.clicked += 1

    async def wait_for(self, **kwargs):
        self.waited += 1

    def locator(self, selector):
        return self._children.get(selector, FakeLocator(selector))


class FakePage:
    def __init__(self, *, texts=None, roles=None, selectors=None):
        self._texts = texts or {}
        self._roles = roles or {}
        self._selectors = selectors or {}
        self.wait_timeouts = []

    def get_by_text(self, text, exact=False):
        return self._texts.get((text, exact), self._texts.get(text, FakeLocator(text)))

    def get_by_role(self, role, name=None):
        return self._roles.get((role, name), FakeLocator(f"{role}:{name}"))

    def locator(self, selector):
        return self._selectors.get(selector, FakeLocator(selector))

    async def wait_for_timeout(self, timeout_ms):
        self.wait_timeouts.append(timeout_ms)


class DouyinSelfDeclarationTests(unittest.IsolatedAsyncioTestCase):
    async def test_apply_self_declaration_selects_ai_generated_content(self):
        trigger = FakeLocator("请选择自主声明", count=1)
        ai_option = FakeLocator("内容由AI生成", count=1)
        confirm_button = FakeLocator("确定", count=1)
        dialog = FakeLocator(
            "dialog",
            count=1,
            children={
                'label.semi-radio:has-text("内容由AI生成")': ai_option,
                'button:has-text("确定")': confirm_button,
            },
        )
        page = FakePage(
            texts={
                ("请选择自主声明", True): trigger,
            },
            selectors={
                'div.semi-modal-content:visible': dialog,
            },
        )
        uploader = DouYinBaseUploader(
            publish_date=0,
            account_file="cookie.json",
            self_declaration=True,
        )

        await uploader.apply_self_declaration(page)

        self.assertEqual(trigger.clicked, 1)
        self.assertEqual(ai_option.clicked, 1)
        self.assertEqual(confirm_button.clicked, 1)
        self.assertEqual(page.wait_timeouts, [300, 500])

    async def test_apply_self_declaration_skips_when_trigger_missing(self):
        page = FakePage()
        uploader = DouYinBaseUploader(
            publish_date=0,
            account_file="cookie.json",
            self_declaration=True,
        )

        await uploader.apply_self_declaration(page)

        self.assertEqual(page.wait_timeouts, [])

    async def test_handle_missing_self_declaration_modal_adds_ai_generated_declaration(self):
        missing_title = FakeLocator("未添加自主声明", count=1)
        add_button = FakeLocator("添加声明", count=1)
        ai_option = FakeLocator("内容由AI生成", count=1)
        confirm_button = FakeLocator("确定", count=1)
        dialog = FakeLocator(
            "dialog",
            count=1,
            children={
                'button:has-text("添加声明")': add_button,
                'label.semi-radio:has-text("内容由AI生成")': ai_option,
                'button:has-text("确定")': confirm_button,
            },
        )
        page = FakePage(
            selectors={
                'h5.semi-modal-title:has-text("未添加自主声明")': missing_title,
                'div.semi-modal-content:visible': dialog,
            },
        )
        uploader = DouYinBaseUploader(
            publish_date=0,
            account_file="cookie.json",
            self_declaration=False,
        )

        handled = await uploader.handle_missing_self_declaration_modal(page)

        self.assertTrue(handled)
        self.assertEqual(add_button.clicked, 1)
        self.assertEqual(ai_option.clicked, 1)
        self.assertEqual(confirm_button.clicked, 1)
        self.assertEqual(page.wait_timeouts, [300, 500])

    async def test_handle_missing_self_declaration_modal_returns_false_when_modal_missing(self):
        page = FakePage()
        uploader = DouYinBaseUploader(
            publish_date=0,
            account_file="cookie.json",
            self_declaration=False,
        )

        handled = await uploader.handle_missing_self_declaration_modal(page)

        self.assertFalse(handled)
        self.assertEqual(page.wait_timeouts, [])


if __name__ == "__main__":
    unittest.main()
