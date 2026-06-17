from __future__ import annotations

import json
import re
from pathlib import Path

import httpx

DOUYIN_PC_USER_INFO_URL = "https://creator.douyin.com/aweme/v1/creator/pc/user/info/"
DOUYIN_CREATOR_USER_INFO_URL = "https://creator.douyin.com/aweme/v1/creator/user/info/"
DOUYIN_MEDIA_USER_INFO_URL = "https://creator.douyin.com/web/api/media/user/info/"
DOUYIN_REFERER = "https://creator.douyin.com/"
XHS_PERSONAL_INFO_URL = "https://creator.xiaohongshu.com/api/galaxy/creator/home/personal_info"
XHS_REFERER = "https://creator.xiaohongshu.com/"
CHANNELS_FINDER_INFO_URL = "https://channels.weixin.qq.com/cgi-bin/mmfinderassistant-bin/shop/get_finder_ec_info_for_opening_page"
CHANNELS_REFERER = "https://channels.weixin.qq.com/platform"
KUAISHOU_USER_INFO_URL = "https://cp.kuaishou.com/rest/cp/creator/pc/home/userInfo?__NS_sig3=9989cefe68b8e4a0abc4c7c6c9df25ae1cf850bcd8d8dadad5d4d7cd"
KUAISHOU_REFERER = "https://cp.kuaishou.com/"
HTTP_PROFILE_HEADERS = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/137.0.0.0 Safari/537.36"
    ),
}

INVALID_AVATAR_KEYWORDS = ("qrcode", "二维码", "cover", "封面", "coin_rmb")
INVALID_PROFILE_NAME_KEYWORDS = (
    "创作者中心",
    "创作中心",
    "视频号助手",
    "发布",
    "上传",
    "首页",
    "数据中心",
    "内容管理",
    "作品管理",
    "消息",
    "通知",
    "评论",
    "私信",
    "帮助",
    "设置",
    "退出登录",
    "登录",
    "扫码",
    "二维码",
    "刷新",
    "草稿",
    "账号管理",
)


INVALID_PROFILE_NAME_KEYWORDS += (
    "创作者中心",
    "活动管理",
    "内容管理",
    "作品管理",
    "数据中心",
    "互动管理",
    "私信管理",
    "发布视频",
    "发布图文",
    "发布文章",
    "首页",
    "通知",
    "网址",
    "抖音",
    "登录",
    "扫码登录",
)
HANGUL_SYLLABLE_RE = re.compile(r"[\uac00-\ud7af]")
CHINESE_CHAR_RE = re.compile(r"[\u4e00-\u9fff]")


def _normalize_avatar_url(candidate: str | None) -> str | None:
    candidate = (candidate or "").strip()
    if not candidate:
        return None
    lowered = candidate.lower()
    if lowered.startswith("data:image/"):
        return None
    if any(keyword in lowered for keyword in INVALID_AVATAR_KEYWORDS):
        return None
    return candidate


def _normalize_profile_name(candidate: str | None) -> str | None:
    normalized = " ".join(str(candidate or "").split())
    if not normalized or len(normalized) < 2 or len(normalized) > 40:
        return None
    lowered = normalized.lower()
    if lowered.startswith("http://") or lowered.startswith("https://"):
        return None
    if any(keyword.lower() in lowered for keyword in INVALID_PROFILE_NAME_KEYWORDS):
        return None
    return normalized


def _normalize_douyin_profile_name(candidate: str | None) -> str | None:
    normalized = _normalize_profile_name(candidate)
    if not normalized:
        return None
    # Douyin can return font-mapped Hangul-looking nicknames from raw APIs.
    # Keep those out of the database and let the visible page / existing name win.
    if HANGUL_SYLLABLE_RE.search(normalized) and not CHINESE_CHAR_RE.search(normalized):
        return None
    return normalized


def _pick_avatar_from_url_list(value) -> str | None:
    if isinstance(value, dict):
        url_list = value.get("url_list")
        if isinstance(url_list, list):
            for url in url_list:
                normalized = _normalize_avatar_url(url)
                if normalized:
                    return normalized
        return _normalize_avatar_url(value.get("url") or value.get("uri"))
    return _normalize_avatar_url(value)


def _empty_profile() -> dict:
    return {
        "name": None,
        "avatarUrl": None,
        "uniqueId": None,
        "uid": None,
        "isValid": False,
    }


def _find_first_string_by_key(value, keys: tuple[str, ...]) -> str | None:
    key_set = set(keys)
    queue = [value]
    visited = 0
    while queue and visited < 5000:
        visited += 1
        current = queue.pop(0)
        if isinstance(current, dict):
            for key in keys:
                item = current.get(key)
                if isinstance(item, str) and item.strip():
                    return item.strip()
            for key, item in current.items():
                if key in key_set:
                    continue
                if isinstance(item, (dict, list)):
                    queue.append(item)
        elif isinstance(current, list):
            queue.extend(item for item in current if isinstance(item, (dict, list)))
    return None


def _extract_douyin_profile_from_payload(payload: dict | None) -> dict:
    payload = payload or {}
    profile = _empty_profile()
    profile["isValid"] = payload.get("status_code") == 0

    verify_info = payload.get("douyin_user_verify_info")
    if isinstance(verify_info, dict):
        profile["name"] = _normalize_douyin_profile_name(
            verify_info.get("nick_name")
            or verify_info.get("nickname")
            or verify_info.get("name")
        )
        profile["avatarUrl"] = _normalize_avatar_url(
            verify_info.get("avatar_url")
            or verify_info.get("avatar")
            or verify_info.get("avatar_uri")
        )
        profile["uniqueId"] = verify_info.get("douyin_unique_id") or verify_info.get("unique_id")

    user = payload.get("user")
    if isinstance(user, dict):
        if not profile.get("name"):
            profile["name"] = _normalize_douyin_profile_name(
                user.get("nickname")
                or user.get("nick_name")
                or user.get("name")
            )
        if not profile.get("avatarUrl"):
            for key in ("avatar_thumb", "avatar_medium", "avatar_larger", "avatar_url", "avatar"):
                avatar_url = _pick_avatar_from_url_list(user.get(key))
                if avatar_url:
                    profile["avatarUrl"] = avatar_url
                    break
        if not profile.get("uniqueId"):
            profile["uniqueId"] = user.get("unique_id") or user.get("short_id")

    if payload.get("uid"):
        profile["uid"] = str(payload.get("uid"))

    return profile


def _extract_xhs_profile_from_payload(payload: dict | None) -> dict:
    payload = payload or {}
    profile = _empty_profile()
    name = (
        payload.get("name")
        or payload.get("nickname")
        or _find_first_string_by_key(payload, ("name", "nickname", "userName"))
    )
    avatar_url = (
        payload.get("avatar")
        or payload.get("avatarUrl")
        or payload.get("avatar_url")
        or _find_first_string_by_key(payload, ("avatar", "avatarUrl", "avatar_url", "headUrl", "headImgUrl"))
    )
    profile["name"] = _normalize_profile_name(name)
    profile["avatarUrl"] = _normalize_avatar_url(avatar_url)
    profile["isValid"] = bool(profile.get("name") or profile.get("avatarUrl"))
    return profile


def _extract_channels_profile_from_payload(payload: dict | None) -> dict:
    payload = payload or {}
    profile = _empty_profile()
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    user_info = data.get("userInfo") if isinstance(data.get("userInfo"), dict) else {}
    profile["name"] = _normalize_profile_name(
        user_info.get("finderNickname")
        or payload.get("finderNickname")
        or _find_first_string_by_key(payload, ("finderNickname", "nickname", "name"))
    )
    profile["avatarUrl"] = _normalize_avatar_url(
        user_info.get("headImgUrl")
        or payload.get("headImgUrl")
        or _find_first_string_by_key(payload, ("headImgUrl", "avatar", "avatarUrl", "headUrl"))
    )
    profile["isValid"] = payload.get("errCode") == 0 and bool(profile.get("name") or profile.get("avatarUrl"))
    return profile


def _extract_kuaishou_profile_from_payload(payload: dict | None) -> dict:
    payload = payload or {}
    profile = _empty_profile()
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    user_info = data.get("coreUserInfo") if isinstance(data.get("coreUserInfo"), dict) else {}
    profile["name"] = _normalize_profile_name(
        user_info.get("userName")
        or payload.get("userName")
        or _find_first_string_by_key(payload, ("userName", "nickname", "name"))
    )
    profile["avatarUrl"] = _normalize_avatar_url(
        user_info.get("headUrl")
        or payload.get("headUrl")
        or _find_first_string_by_key(payload, ("headUrl", "avatar", "avatarUrl", "headImgUrl"))
    )
    profile["uid"] = str(user_info.get("userId") or "") or None
    profile["isValid"] = payload.get("result") == 1 and bool(profile.get("name") or profile.get("avatarUrl"))
    return profile


def _merge_profile(base: dict, incoming: dict) -> dict:
    if incoming.get("isValid"):
        base["isValid"] = True
    for key in ("name", "avatarUrl", "uniqueId", "uid"):
        if not base.get(key) and incoming.get(key):
            base[key] = incoming[key]
    return base


def _load_http_cookies(cookie_file: Path) -> httpx.Cookies:
    payload = json.loads(Path(cookie_file).read_text(encoding="utf-8"))
    cookies = payload.get("cookies", []) if isinstance(payload, dict) else []
    jar = httpx.Cookies()

    for item in cookies:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        value = str(item.get("value") or "")
        domain = str(item.get("domain") or "").strip()
        path = str(item.get("path") or "/")
        if name and domain:
            jar.set(name, value, domain=domain, path=path)

    return jar


async def _fetch_json_from_http(
    client: httpx.AsyncClient,
    url: str,
    *,
    method: str = "GET",
    headers: dict | None = None,
) -> dict | None:
    response = await client.request(method, url, headers=headers)
    if response.status_code >= 400:
        return None
    try:
        payload = response.json()
        return payload if isinstance(payload, dict) else None
    except (json.JSONDecodeError, ValueError):
        return None


async def fetch_douyin_account_profile_from_cookie(cookie_file: Path) -> dict:
    profile = _empty_profile()
    cookie_file = Path(cookie_file)
    if not cookie_file.exists():
        return profile

    try:
        cookies = _load_http_cookies(cookie_file)
    except (OSError, json.JSONDecodeError, ValueError):
        return profile

    async with httpx.AsyncClient(
        cookies=cookies,
        headers=HTTP_PROFILE_HEADERS,
        timeout=15.0,
        follow_redirects=True,
        trust_env=False,
    ) as client:
        for url in (DOUYIN_CREATOR_USER_INFO_URL, DOUYIN_MEDIA_USER_INFO_URL):
            payload = await _fetch_json_from_http(
                client,
                url,
                headers={"referer": DOUYIN_REFERER},
            )
            if not payload:
                continue
            profile = _merge_profile(profile, _extract_douyin_profile_from_payload(payload))
            if profile.get("name") and profile.get("avatarUrl"):
                return profile

        payload = await _fetch_json_from_http(
            client,
            DOUYIN_PC_USER_INFO_URL,
            headers={"referer": DOUYIN_REFERER},
        )
        if payload:
            profile = _merge_profile(profile, _extract_douyin_profile_from_payload(payload))
        return profile


async def fetch_api_account_profile_from_cookie(account_type: int, cookie_file: Path) -> dict:
    profile = _empty_profile()
    cookie_file = Path(cookie_file)
    if not cookie_file.exists():
        return profile

    platform_type = int(account_type)
    if platform_type == 1:
        url = XHS_PERSONAL_INFO_URL
        method = "GET"
        referer = XHS_REFERER
        extractor = _extract_xhs_profile_from_payload
    elif platform_type == 2:
        url = CHANNELS_FINDER_INFO_URL
        method = "POST"
        referer = CHANNELS_REFERER
        extractor = _extract_channels_profile_from_payload
    elif platform_type == 4:
        url = KUAISHOU_USER_INFO_URL
        method = "POST"
        referer = KUAISHOU_REFERER
        extractor = _extract_kuaishou_profile_from_payload
    else:
        return profile

    try:
        cookies = _load_http_cookies(cookie_file)
    except (OSError, json.JSONDecodeError, ValueError):
        return profile

    request_headers = {"referer": referer}
    if platform_type == 2:
        request_headers["origin"] = "https://channels.weixin.qq.com"
    elif platform_type == 4:
        request_headers["origin"] = "https://cp.kuaishou.com"

    async with httpx.AsyncClient(
        cookies=cookies,
        headers=HTTP_PROFILE_HEADERS,
        timeout=15.0,
        follow_redirects=True,
        trust_env=False,
    ) as client:
        payload = await _fetch_json_from_http(
            client,
            url,
            method=method,
            headers=request_headers,
        )
        if not payload:
            return profile
        return extractor(payload)


async def fetch_account_profile_from_cookie(account_type: int, cookie_file: Path, account_name: str = "") -> dict:
    platform_type = int(account_type)
    if not cookie_file.exists() or platform_type not in (1, 2, 3, 4):
        return _empty_profile()

    if platform_type == 3:
        return await fetch_douyin_account_profile_from_cookie(cookie_file)

    return await fetch_api_account_profile_from_cookie(platform_type, cookie_file)


async def fetch_avatar_url_from_cookie(account_type: int, cookie_file: Path, account_name: str = "") -> str | None:
    profile = await fetch_account_profile_from_cookie(account_type, cookie_file, account_name=account_name)
    return profile.get("avatarUrl")
