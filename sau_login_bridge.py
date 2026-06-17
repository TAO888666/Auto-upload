from __future__ import annotations

import asyncio
import threading
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from queue import Queue
from typing import Awaitable, Callable

from conf import BASE_DIR, LOCAL_CHROME_PATH
from patchright.async_api import async_playwright
from uploader.douyin_uploader.main import douyin_cookie_gen
from uploader.ks_uploader.main import KUAISHOU_LOGIN_URL
from uploader.ks_uploader.main import get_ks_cookie
from uploader.ks_uploader.main import _extract_ks_qrcode_src
from uploader.tencent_uploader.main import TENCENT_LOGIN_URL
from uploader.tencent_uploader.main import get_tencent_cookie as tencent_cookie_gen
from uploader.xiaohongshu_uploader.main import XHS_LOGIN_URL
from uploader.xiaohongshu_uploader.main import xiaohongshu_cookie_gen
from uploader.xiaohongshu_uploader.main import _open_xhs_qrcode_panel
from utils.account_profile import fetch_account_profile_from_cookie
from utils.base_social_media import set_init_script
from utils.user_info_db import UNSET, save_user_info_record

PLATFORM_TYPE_MAP = {
    "1": 1,
    "2": 2,
    "3": 3,
    "4": 4,
}
HEADED_LOGIN_PLATFORM_TYPES = {"1", "2", "3", "4"}


@dataclass
class BrowserRuntime:
    playwright: object
    browser: object
    context: object
    page: object


@dataclass
class BrowserLoginSession:
    platform_type: str
    account_type: int
    account_file: Path
    cookie_auth: Callable[[str], Awaitable[bool]]
    account_name: str = ""
    account_id: int | None = None
    ready_event: threading.Event = field(default_factory=threading.Event)
    loop: asyncio.AbstractEventLoop | None = None
    runtime: BrowserRuntime | None = None
    thread: threading.Thread | None = None
    error: str | None = None
    session_id: str = ""


@dataclass
class OpenedAccountSession:
    account_id: int
    platform_type: str
    account_name: str
    account_file: Path
    ready_event: threading.Event = field(default_factory=threading.Event)
    loop: asyncio.AbstractEventLoop | None = None
    runtime: BrowserRuntime | None = None
    thread: threading.Thread | None = None
    error: str | None = None


BROWSER_LOGIN_SESSIONS: dict[str, BrowserLoginSession] = {}
ACCOUNT_BROWSER_SESSIONS: dict[int, OpenedAccountSession] = {}


async def _queue_qrcode(status_queue: Queue, payload: dict) -> None:
    image_data_url = payload.get("image_data_url")
    if image_data_url:
        status_queue.put(image_data_url)


def _build_account_cookie_path() -> Path:
    cookie_dir = Path(BASE_DIR) / "cookiesFile"
    cookie_dir.mkdir(parents=True, exist_ok=True)
    return cookie_dir / f"{uuid.uuid1()}.json"


def _save_user_info(
    account_type: int,
    account_file: Path,
    account_name: str,
    *,
    account_id: int | None = None,
    avatar_url=UNSET,
) -> dict:
    database_path = Path(BASE_DIR) / "db" / "database.db"
    database_path.parent.mkdir(parents=True, exist_ok=True)
    return save_user_info_record(
        database_path,
        account_type,
        account_file,
        account_name,
        account_id=account_id,
        avatar_url=avatar_url,
    )

def _build_fallback_account_name(session: BrowserLoginSession) -> str:
    suffix = (session.session_id or "account")[:8]
    return f"account_{session.account_type}_{suffix}"


async def fetch_avatar_url_from_cookie(
    account_type: int,
    account_file: str | Path,
    account_name: str = "",
) -> str | None:
    profile = await fetch_account_profile_from_cookie(
        account_type,
        account_file,
        account_name=account_name,
    )
    return profile.get("avatarUrl")


async def _resolve_browser_login_profile(session: BrowserLoginSession, account_file: Path) -> dict:
    profile = {"name": None, "avatarUrl": None}
    try:
        cookie_profile = await fetch_account_profile_from_cookie(
            session.account_type,
            account_file,
            account_name=session.account_name,
        )
        if not profile.get("name") and cookie_profile.get("name"):
            profile["name"] = cookie_profile["name"]
        if not profile.get("avatarUrl") and cookie_profile.get("avatarUrl"):
            profile["avatarUrl"] = cookie_profile["avatarUrl"]
    except Exception:
        pass

    return profile


def _session_key(session_id: str) -> str:
    return str(session_id or "").strip()


def _legacy_browser_login_key(platform_type: str, account_name: str) -> str:
    return _session_key(f"{platform_type}:{account_name}")


def _get_browser_login_session(
    session_id: str,
    *,
    platform_type: str = "",
    account_name: str = "",
) -> BrowserLoginSession | None:
    session = BROWSER_LOGIN_SESSIONS.get(_session_key(session_id))
    if session is not None:
        return session

    if platform_type and not account_name:
        legacy_key = _legacy_browser_login_key(platform_type, session_id)
        session = BROWSER_LOGIN_SESSIONS.get(legacy_key)
        if session is not None:
            return session
        session = BROWSER_LOGIN_SESSIONS.get((platform_type, session_id))
        if session is not None:
            return session

    if platform_type and account_name:
        legacy_key = _legacy_browser_login_key(platform_type, account_name)
        session = BROWSER_LOGIN_SESSIONS.get(legacy_key)
        if session is not None:
            return session
        session = BROWSER_LOGIN_SESSIONS.get((platform_type, account_name))
        if session is not None:
            return session

    return None


def _build_browser_launch_kwargs() -> dict:
    launch_kwargs = {
        "headless": False,
        "args": ["--start-maximized"],
    }
    if LOCAL_CHROME_PATH:
        launch_kwargs["executable_path"] = LOCAL_CHROME_PATH
    else:
        launch_kwargs["channel"] = "chrome"
    return launch_kwargs


async def _open_browser_runtime(start_url: str, prepare_page=None) -> BrowserRuntime:
    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(**_build_browser_launch_kwargs())
    context = await browser.new_context(no_viewport=True)
    context = await set_init_script(context)
    page = await context.new_page()
    await page.goto(start_url)
    if prepare_page is not None:
        await prepare_page(page)
    try:
        await page.bring_to_front()
    except Exception:
        pass
    return BrowserRuntime(playwright=playwright, browser=browser, context=context, page=page)


async def _open_authenticated_browser_runtime(start_url: str, account_file: Path, prepare_page=None) -> BrowserRuntime:
    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(**_build_browser_launch_kwargs())
    context = await browser.new_context(no_viewport=True, storage_state=str(account_file))
    context = await set_init_script(context)
    page = await context.new_page()
    await page.goto(start_url)
    if prepare_page is not None:
        await prepare_page(page)
    try:
        await page.bring_to_front()
    except Exception:
        pass
    return BrowserRuntime(playwright=playwright, browser=browser, context=context, page=page)


async def _prepare_douyin_page(page) -> None:
    try:
        await page.wait_for_timeout(1000)
    except Exception:
        pass


async def _prepare_xiaohongshu_page(page) -> None:
    try:
        await _open_xhs_qrcode_panel(page)
    except Exception:
        pass


async def _prepare_kuaishou_page(page) -> None:
    try:
        await _extract_ks_qrcode_src(page)
    except Exception:
        pass


async def _cookie_auth_by_profile_api(account_type: int, account_file: str) -> bool:
    profile = await fetch_account_profile_from_cookie(account_type, Path(account_file))
    return bool(profile.get("isValid"))


async def _xiaohongshu_cookie_auth_by_profile_api(account_file: str) -> bool:
    return await _cookie_auth_by_profile_api(1, account_file)


async def _tencent_cookie_auth_by_profile_api(account_file: str) -> bool:
    return await _cookie_auth_by_profile_api(2, account_file)


async def _douyin_cookie_auth_by_profile_api(account_file: str) -> bool:
    return await _cookie_auth_by_profile_api(3, account_file)


async def _kuaishou_cookie_auth_by_profile_api(account_file: str) -> bool:
    return await _cookie_auth_by_profile_api(4, account_file)


async def _launch_douyin_runtime() -> BrowserRuntime:
    return await _open_browser_runtime("https://creator.douyin.com/", prepare_page=_prepare_douyin_page)


async def _launch_xiaohongshu_runtime() -> BrowserRuntime:
    return await _open_browser_runtime(XHS_LOGIN_URL, prepare_page=_prepare_xiaohongshu_page)


async def _launch_kuaishou_runtime() -> BrowserRuntime:
    return await _open_browser_runtime(KUAISHOU_LOGIN_URL, prepare_page=_prepare_kuaishou_page)


async def _launch_tencent_runtime() -> BrowserRuntime:
    return await _open_browser_runtime(TENCENT_LOGIN_URL)


async def _launch_opened_douyin_runtime(account_file: Path) -> BrowserRuntime:
    return await _open_authenticated_browser_runtime(
        "https://creator.douyin.com/",
        account_file,
        prepare_page=_prepare_douyin_page,
    )


async def _launch_opened_xiaohongshu_runtime(account_file: Path) -> BrowserRuntime:
    return await _open_authenticated_browser_runtime(XHS_LOGIN_URL, account_file)


async def _launch_opened_kuaishou_runtime(account_file: Path) -> BrowserRuntime:
    return await _open_authenticated_browser_runtime("https://cp.kuaishou.com/", account_file)


async def _launch_opened_tencent_runtime(account_file: Path) -> BrowserRuntime:
    return await _open_authenticated_browser_runtime(TENCENT_LOGIN_URL, account_file)


BROWSER_LOGIN_LAUNCHERS: dict[str, tuple[Callable[[], Awaitable[BrowserRuntime]], Callable[[str], Awaitable[bool]]]] = {
    "1": (_launch_xiaohongshu_runtime, _xiaohongshu_cookie_auth_by_profile_api),
    "2": (_launch_tencent_runtime, _tencent_cookie_auth_by_profile_api),
    "3": (_launch_douyin_runtime, _douyin_cookie_auth_by_profile_api),
    "4": (_launch_kuaishou_runtime, _kuaishou_cookie_auth_by_profile_api),
}

ACCOUNT_BROWSER_LAUNCHERS: dict[str, Callable[[Path], Awaitable[BrowserRuntime]]] = {
    "1": _launch_opened_xiaohongshu_runtime,
    "2": _launch_opened_tencent_runtime,
    "3": _launch_opened_douyin_runtime,
    "4": _launch_opened_kuaishou_runtime,
}


async def _confirm_browser_session(session: BrowserLoginSession) -> dict:
    if session.runtime is None:
        return {"confirmed": False, "message": "浏览器登录会话尚未准备好，请稍后再试。", "terminal": True}

    try:
        await session.runtime.context.storage_state(path=str(session.account_file))
        is_valid = await session.cookie_auth(str(session.account_file))
    except Exception as exc:
        return {"confirmed": False, "message": f"登录校验失败：{exc}", "terminal": True}

    if not is_valid:
        return {
            "confirmed": False,
            "message": "尚未检测到登录成功，请确认你已经在浏览器中完成扫码和授权，再点一次“我已完成扫码”。",
            "terminal": False,
        }

    return {
        "confirmed": True,
        "message": "登录成功",
        "terminal": True,
        "account_file": str(session.account_file),
    }


async def _shutdown_browser_session(session: BrowserLoginSession) -> None:
    runtime = session.runtime
    if runtime is None:
        return

    closers = [
        getattr(runtime.page, "close", None),
        getattr(runtime.context, "close", None),
        getattr(runtime.browser, "close", None),
        getattr(runtime.playwright, "stop", None),
    ]
    for closer in closers:
        if closer is None:
            continue
        try:
            result = closer()
            if asyncio.iscoroutine(result):
                await result
        except Exception:
            pass


def _browser_login_worker(
    session: BrowserLoginSession,
    launcher: Callable[[], Awaitable[BrowserRuntime]],
) -> None:
    loop = asyncio.new_event_loop()
    session.loop = loop
    asyncio.set_event_loop(loop)

    try:
        session.runtime = loop.run_until_complete(launcher())
    except Exception as exc:
        session.error = str(exc)
        session.ready_event.set()
        loop.close()
        return

    session.ready_event.set()

    try:
        loop.run_forever()
    finally:
        pending = [task for task in asyncio.all_tasks(loop) if not task.done()]
        for task in pending:
            task.cancel()
        if pending:
            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        loop.close()


def _opened_account_browser_worker(
    session: OpenedAccountSession,
    launcher: Callable[[Path], Awaitable[BrowserRuntime]],
) -> None:
    loop = asyncio.new_event_loop()
    session.loop = loop
    asyncio.set_event_loop(loop)

    try:
        session.runtime = loop.run_until_complete(launcher(session.account_file))
        try:
            session.runtime.browser.on(
                "disconnected",
                lambda *_: loop.call_soon_threadsafe(loop.stop),
            )
        except Exception:
            pass
    except Exception as exc:
        session.error = str(exc)
        session.ready_event.set()
        loop.close()
        return

    session.ready_event.set()

    try:
        loop.run_forever()
    finally:
        ACCOUNT_BROWSER_SESSIONS.pop(session.account_id, None)
        pending = [task for task in asyncio.all_tasks(loop) if not task.done()]
        for task in pending:
            task.cancel()
        if pending:
            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        loop.run_until_complete(_shutdown_browser_session(session))
        loop.close()


def close_browser_login_session(session_id: str) -> dict:
    key = _session_key(session_id)
    session = BROWSER_LOGIN_SESSIONS.pop(key, None)
    if session is None:
        session = BROWSER_LOGIN_SESSIONS.pop(session_id, None)
    if not session:
        return {"closed": False}

    if session.loop is not None and session.runtime is not None:
        future = asyncio.run_coroutine_threadsafe(_shutdown_browser_session(session), session.loop)
        try:
            future.result(timeout=30)
        except Exception:
            pass
        session.loop.call_soon_threadsafe(session.loop.stop)

    legacy_key = _legacy_browser_login_key(session.platform_type, session.account_name)
    if legacy_key != key:
        BROWSER_LOGIN_SESSIONS.pop(legacy_key, None)

    return {"closed": True, "sessionId": session.session_id}


def close_account_browser_session(account_id: int) -> dict:
    session = ACCOUNT_BROWSER_SESSIONS.pop(int(account_id), None)
    if not session:
        return {"closed": False}

    if session.loop is not None:
        if session.runtime is not None:
            future = asyncio.run_coroutine_threadsafe(_shutdown_browser_session(session), session.loop)
            try:
                future.result(timeout=30)
            except Exception:
                pass
        session.loop.call_soon_threadsafe(session.loop.stop)

    return {"closed": True}


def start_browser_login_session(
    platform_type: str,
    session_id: str,
    *,
    account_id: int | None = None,
    account_name: str = "",
) -> dict:
    platform_type = str(platform_type)
    account_type = PLATFORM_TYPE_MAP.get(platform_type)
    launcher_entry = BROWSER_LOGIN_LAUNCHERS.get(platform_type)

    if account_type is None or launcher_entry is None:
        return {"started": False, "message": "当前平台暂不支持浏览器确认登录。"}

    close_browser_login_session(platform_type, account_name)

    launcher, cookie_auth = launcher_entry
    session = BrowserLoginSession(
        platform_type=platform_type,
        account_type=account_type,
        account_name=account_name,
        account_file=_build_account_cookie_path(),
        cookie_auth=cookie_auth,
    )
    BROWSER_LOGIN_SESSIONS[_session_key(platform_type, account_name)] = session

    thread = threading.Thread(
        target=_browser_login_worker,
        args=(session, launcher),
        daemon=True,
    )
    session.thread = thread
    thread.start()
    session.ready_event.wait(timeout=30)

    if session.error:
        BROWSER_LOGIN_SESSIONS.pop(_session_key(platform_type, account_name), None)
        return {"started": False, "message": f"浏览器启动失败：{session.error}"}

    if session.runtime is None:
        close_browser_login_session(platform_type, account_name)
        return {"started": False, "message": "浏览器启动超时，请重试。"}

    return {"started": True, "message": "浏览器已打开，请扫码后点击“我已完成扫码”。"}


def start_account_browser_session(
    account_id: int,
    platform_type: str,
    account_name: str,
    account_file: Path,
) -> dict:
    platform_type = str(platform_type)
    launcher = ACCOUNT_BROWSER_LAUNCHERS.get(platform_type)
    if launcher is None:
        return {"started": False, "message": "当前平台暂不支持打开账号浏览器。"}

    if not account_file.exists():
        return {"started": False, "message": "当前账号的 Cookie 文件不存在，请先重新登录。"}

    close_account_browser_session(account_id)

    session = OpenedAccountSession(
        account_id=int(account_id),
        platform_type=platform_type,
        account_name=account_name,
        account_file=account_file,
    )
    ACCOUNT_BROWSER_SESSIONS[session.account_id] = session

    thread = threading.Thread(
        target=_opened_account_browser_worker,
        args=(session, launcher),
        daemon=True,
    )
    session.thread = thread
    thread.start()
    session.ready_event.wait(timeout=30)

    if session.error:
        ACCOUNT_BROWSER_SESSIONS.pop(session.account_id, None)
        return {"started": False, "message": f"账号浏览器启动失败：{session.error}"}

    if session.runtime is None:
        close_account_browser_session(session.account_id)
        return {"started": False, "message": "账号浏览器启动超时，请重试。"}

    return {"started": True, "message": f"已打开 {account_name} 的浏览器窗口。"}


def confirm_browser_login_session(
    platform_type: str,
    session_id: str,
    *,
    account_id: int | None = None,
    account_name: str = "",
) -> dict:
    session = BROWSER_LOGIN_SESSIONS.get(_session_key(platform_type, account_name))
    if session is None or session.loop is None:
        return {"confirmed": False, "message": "未找到进行中的登录会话，请重新点击添加账号。"}

    future = asyncio.run_coroutine_threadsafe(_confirm_browser_session(session), session.loop)
    result = future.result(timeout=60)

    if result.get("confirmed"):
        account_file = Path(result.get("account_file") or session.account_file)
        try:
            avatar_url = asyncio.run_coroutine_threadsafe(
                _resolve_browser_login_avatar_url(session, account_file),
                session.loop,
            ).result(timeout=30)
        except Exception:
            avatar_url = UNSET
        if avatar_url is None:
            avatar_url = UNSET
        _save_user_info(
            session.account_type,
            account_file,
            session.account_name,
            avatar_url=avatar_url,
        )
        close_browser_login_session(platform_type, account_name)
        return result

    if result.get("terminal"):
        close_browser_login_session(platform_type, account_name)

    return result


def confirm_browser_login_session(
    platform_type: str,
    session_id: str,
    *,
    account_id: int | None = None,
    account_name: str = "",
) -> dict:
    session = _get_browser_login_session(session_id, platform_type=platform_type, account_name=account_name)
    if session is None or session.loop is None:
        return {"confirmed": False, "message": "链路未找到，请重新添加账号"}

    if account_id is not None:
        session.account_id = int(account_id)
    if account_name:
        session.account_name = str(account_name)

    future = asyncio.run_coroutine_threadsafe(_confirm_browser_session(session), session.loop)
    result = future.result(timeout=60)

    if result.get("confirmed"):
        account_file = Path(result.get("account_file") or session.account_file)
        try:
            profile = asyncio.run_coroutine_threadsafe(
                _resolve_browser_login_profile(session, account_file),
                session.loop,
            ).result(timeout=30)
        except Exception:
            profile = {"name": None, "avatarUrl": None}
        if isinstance(profile, str):
            profile = {"name": None, "avatarUrl": profile}
        elif not isinstance(profile, dict):
            profile = {"name": None, "avatarUrl": None}

        resolved_account_name = profile.get("name") or session.account_name or _build_fallback_account_name(session)
        avatar_url = profile.get("avatarUrl", UNSET)
        if avatar_url is None:
            avatar_url = UNSET

        saved_account = _save_user_info(
            session.account_type,
            account_file,
            resolved_account_name,
            account_id=session.account_id,
            avatar_url=avatar_url,
        )
        result["account"] = saved_account
        close_browser_login_session(session_id)
        return result

    if result.get("terminal"):
        close_browser_login_session(session_id)

    return result


def start_browser_login_session(
    platform_type: str,
    session_id: str,
    *,
    account_id: int | None = None,
    account_name: str = "",
) -> dict:
    platform_type = str(platform_type)
    account_type = PLATFORM_TYPE_MAP.get(platform_type)
    launcher_entry = BROWSER_LOGIN_LAUNCHERS.get(platform_type)
    session_id = _session_key(session_id)

    if account_type is None or launcher_entry is None:
        return {"started": False, "message": "当前平台暂不支持浏览器确认登录"}
    if not session_id:
        return {"started": False, "message": "缺少登录会话 ID"}

    close_browser_login_session(session_id)

    launcher, cookie_auth = launcher_entry
    session = BrowserLoginSession(
        session_id=session_id,
        platform_type=platform_type,
        account_type=account_type,
        account_file=_build_account_cookie_path(),
        cookie_auth=cookie_auth,
        account_name=str(account_name or ""),
        account_id=int(account_id) if account_id is not None else None,
    )
    BROWSER_LOGIN_SESSIONS[session_id] = session
    if account_name:
        BROWSER_LOGIN_SESSIONS[_legacy_browser_login_key(platform_type, account_name)] = session

    thread = threading.Thread(
        target=_browser_login_worker,
        args=(session, launcher),
        daemon=True,
    )
    session.thread = thread
    thread.start()
    session.ready_event.wait(timeout=30)

    if session.error:
        BROWSER_LOGIN_SESSIONS.pop(session_id, None)
        if account_name:
            BROWSER_LOGIN_SESSIONS.pop(_legacy_browser_login_key(platform_type, account_name), None)
        return {"started": False, "message": f"浏览器启动失败：{session.error}"}

    if session.runtime is None:
        close_browser_login_session(session_id)
        return {"started": False, "message": "浏览器启动超时，请重试"}

    return {
        "started": True,
        "message": "浏览器已打开，请扫码后点击“我已完成扫码”。",
        "sessionId": session.session_id,
    }


async def run_login_flow(platform_type: str, account_name: str, status_queue: Queue) -> None:
    platform_type = str(platform_type)

    runner_map = {
        "1": xiaohongshu_cookie_gen,
        "2": tencent_cookie_gen,
        "3": douyin_cookie_gen,
        "4": get_ks_cookie,
    }
    login_runner = runner_map.get(platform_type)
    account_type = PLATFORM_TYPE_MAP.get(platform_type)

    if not login_runner or account_type is None:
        status_queue.put("500")
        return

    account_file = _build_account_cookie_path()

    try:
        result = await login_runner(
            str(account_file),
            qrcode_callback=lambda payload: _queue_qrcode(status_queue, payload),
            headless=True,
        )
    except Exception as exc:
        print(f"Login flow failed for type={platform_type}, account={account_name}: {exc}")
        status_queue.put("500")
        return

    if result and result.get("success"):
        saved_account_file = Path(result.get("account_file") or account_file)
        try:
            profile = await fetch_account_profile_from_cookie(
                account_type,
                saved_account_file,
                account_name=account_name,
            )
        except Exception:
            profile = {"name": None, "avatarUrl": None}
        resolved_account_name = profile.get("name") or account_name
        avatar_url = profile.get("avatarUrl", UNSET)
        if avatar_url is None:
            avatar_url = UNSET
        _save_user_info(
            account_type,
            saved_account_file,
            resolved_account_name,
            avatar_url=avatar_url,
        )
        status_queue.put("200")
        return

    status_queue.put("500")
