from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


@dataclass
class PublishResult:
    provider: str
    request_id: str | None = None
    published_url: str | None = None


class PublishError(RuntimeError):
    pass


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _post_json(url: str, payload: dict[str, Any], headers: dict[str, str] | None = None, method: str = "POST") -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    req = Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    for key, value in (headers or {}).items():
        if value:
            req.add_header(key, value)
    try:
        with urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace") if hasattr(exc, "read") else ""
        raise PublishError(f"HTTP {exc.code} calling {url}: {body or exc.reason}") from exc
    except URLError as exc:
        raise PublishError(f"Unable to reach {url}: {exc.reason}") from exc
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"raw": raw}


def _post_form(url: str, payload: dict[str, str], headers: dict[str, str] | None = None) -> dict[str, Any]:
    from urllib.parse import urlencode

    data = urlencode(payload).encode("utf-8")
    req = Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    for key, value in (headers or {}).items():
        if value:
            req.add_header(key, value)
    try:
        with urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace") if hasattr(exc, "read") else ""
        raise PublishError(f"HTTP {exc.code} calling {url}: {body or exc.reason}") from exc
    except URLError as exc:
        raise PublishError(f"Unable to reach {url}: {exc.reason}") from exc
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"raw": raw}


def build_message(title: str, draft: str | None) -> str:
    body = (draft or "").strip()
    return body if body else title.strip()


def provider_status() -> dict[str, dict[str, Any]]:
    return {
        "telegram": {
            "configured": bool(_env("TELEGRAM_PUBLISH_BOT_TOKEN") and _env("TELEGRAM_PUBLISH_CHAT_ID")),
            "chat_id": bool(_env("TELEGRAM_PUBLISH_CHAT_ID")),
        },
        "twitter": {
            "configured": bool(_env("TWITTER_API_BEARER_TOKEN")),
            "api_base": _env("TWITTER_API_BASE_URL", "https://api.x.com"),
        },
        "linkedin": {
            "configured": bool(_env("LINKEDIN_ACCESS_TOKEN") and _env("LINKEDIN_AUTHOR_URN")),
            "author_urn": bool(_env("LINKEDIN_AUTHOR_URN")),
        },
        "facebook": {
            "configured": bool(_env("META_PAGE_ACCESS_TOKEN") and _env("META_PAGE_ID")),
            "page_id": bool(_env("META_PAGE_ID")),
        },
        "instagram": {
            "configured": bool(_env("META_IG_USER_ID") and _env("META_PAGE_ACCESS_TOKEN")),
            "ig_user_id": bool(_env("META_IG_USER_ID")),
            "default_media_url": bool(_env("META_DEFAULT_IMAGE_URL")),
        },
        "tiktok": {
            "configured": bool(_env("TIKTOK_PUBLISH_URL") or _env("CUSTOM_PUBLISH_URL")),
            "custom_gateway": bool(_env("TIKTOK_PUBLISH_URL") or _env("CUSTOM_PUBLISH_URL")),
        },
        "custom": {
            "configured": bool(_env("CUSTOM_PUBLISH_URL") and _env("CUSTOM_PUBLISH_TOKEN")),
            "url": bool(_env("CUSTOM_PUBLISH_URL")),
        },
    }


def publish_content(channel: str, title: str, draft: str | None) -> PublishResult:
    channel_key = channel.strip().lower()
    message = build_message(title, draft)
    if channel_key in {"telegram", "tg"}:
        return PublishResult(provider="telegram", request_id=publish_telegram(message))
    if channel_key in {"x", "twitter", "x/twitter"}:
        return PublishResult(provider="twitter", request_id=publish_twitter(message))
    if channel_key == "linkedin":
        return PublishResult(provider="linkedin", request_id=publish_linkedin(message))
    if channel_key in {"facebook", "meta", "instagram", "instagram/facebook"}:
        return publish_meta(channel_key, message)
    if channel_key == "tiktok":
        return PublishResult(provider="tiktok", request_id=publish_tiktok(message))
    if channel_key == "custom gateway":
        return PublishResult(provider="custom", request_id=publish_custom(channel_key, message))
    raise PublishError(f"Unsupported channel: {channel}")


def publish_telegram(message: str) -> str:
    token = _env("TELEGRAM_PUBLISH_BOT_TOKEN")
    chat_id = _env("TELEGRAM_PUBLISH_CHAT_ID")
    if not token or not chat_id:
        raise PublishError("Telegram publishing is not configured")
    data = _post_form(
        f"https://api.telegram.org/bot{token}/sendMessage",
        {"chat_id": chat_id, "text": message},
    )
    if not data.get("ok"):
        raise PublishError(f"Telegram API error: {data}")
    result = data.get("result") or {}
    return str(result.get("message_id") or result.get("id") or "telegram-message")


def publish_twitter(message: str) -> str:
    token = _env("TWITTER_API_BEARER_TOKEN")
    api_base = _env("TWITTER_API_BASE_URL", "https://api.x.com")
    if not token:
        raise PublishError("Twitter/X publishing is not configured")
    data = _post_json(
        f"{api_base.rstrip('/')}/2/tweets",
        {"text": message},
        headers={"Authorization": f"Bearer {token}"},
    )
    tweet = data.get("data") or {}
    return str(tweet.get("id") or data.get("id") or "twitter-post")


def publish_linkedin(message: str) -> str:
    token = _env("LINKEDIN_ACCESS_TOKEN")
    author_urn = _env("LINKEDIN_AUTHOR_URN")
    if not token or not author_urn:
        raise PublishError("LinkedIn publishing is not configured")
    data = _post_json(
        "https://api.linkedin.com/v2/ugcPosts",
        {
            "author": author_urn,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": message},
                    "shareMediaCategory": "NONE",
                }
            },
            "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
        },
        headers={
            "Authorization": f"Bearer {token}",
            "X-Restli-Protocol-Version": "2.0.0",
        },
    )
    return str(data.get("id") or data.get("value") or "linkedin-post")


def publish_meta(channel_key: str, message: str) -> PublishResult:
    page_token = _env("META_PAGE_ACCESS_TOKEN")
    page_id = _env("META_PAGE_ID")
    ig_user_id = _env("META_IG_USER_ID")
    default_media_url = _env("META_DEFAULT_IMAGE_URL")
    if channel_key in {"facebook", "meta"}:
        if not page_token or not page_id:
            raise PublishError("Facebook publishing is not configured")
        data = _post_json(
            f"https://graph.facebook.com/v20.0/{page_id}/feed",
            {"message": message, "access_token": page_token},
        )
        return PublishResult(provider="facebook", request_id=str(data.get("id") or data.get("post_id") or "facebook-post"))

    if channel_key in {"instagram", "instagram/facebook"}:
        if not page_token or not ig_user_id:
            raise PublishError("Instagram publishing is not configured")
        if not default_media_url:
            raise PublishError("Instagram publishing requires META_DEFAULT_IMAGE_URL until media upload is implemented")
        creation = _post_json(
            f"https://graph.facebook.com/v20.0/{ig_user_id}/media",
            {"caption": message, "image_url": default_media_url, "access_token": page_token},
        )
        container_id = creation.get("id")
        if not container_id:
            raise PublishError(f"Instagram media container creation failed: {creation}")
        published = _post_json(
            f"https://graph.facebook.com/v20.0/{ig_user_id}/media_publish",
            {"creation_id": str(container_id), "access_token": page_token},
        )
        return PublishResult(provider="instagram", request_id=str(published.get("id") or container_id))

    raise PublishError(f"Unsupported Meta channel: {channel_key}")


def publish_tiktok(message: str) -> str:
    url = _env("TIKTOK_PUBLISH_URL") or _env("CUSTOM_PUBLISH_URL")
    token = _env("TIKTOK_PUBLISH_TOKEN") or _env("CUSTOM_PUBLISH_TOKEN")
    if not url or not token:
        raise PublishError("TikTok publishing is not configured")
    data = _post_json(
        url,
        {"channel": "tiktok", "message": message, "published_at": datetime.utcnow().isoformat()},
        headers={"Authorization": f"Bearer {token}"},
    )
    return str(data.get("id") or data.get("request_id") or "tiktok-post")


def publish_custom(channel: str, message: str) -> str:
    url = _env("CUSTOM_PUBLISH_URL")
    token = _env("CUSTOM_PUBLISH_TOKEN")
    if not url or not token:
        raise PublishError("Custom gateway is not configured")
    data = _post_json(
        url,
        {"channel": channel, "message": message, "published_at": datetime.utcnow().isoformat()},
        headers={"Authorization": f"Bearer {token}"},
    )
    return str(data.get("id") or data.get("request_id") or "custom-post")
