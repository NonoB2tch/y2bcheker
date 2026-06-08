import json
import os
import sys
from pathlib import Path

import feedparser
import requests

STATE_FILE = Path("state.json")


def load_state():
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_state(state):
    STATE_FILE.write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def get_channel_ids():
    raw = os.getenv("YOUTUBE_CHANNEL_IDS", "").strip()
    if raw:
        return [x.strip() for x in raw.split(",") if x.strip()]

    legacy = os.getenv("YOUTUBE_CHANNEL_ID", "").strip()
    if legacy:
        return [legacy]

    raise ValueError("YOUTUBE_CHANNEL_IDS or YOUTUBE_CHANNEL_ID is not set")


def get_feed(channel_id):
    url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    feed = feedparser.parse(url)
    if getattr(feed, "bozo", False) and not feed.entries:
        raise RuntimeError(f"Failed to parse feed for channel {channel_id}")
    return feed


def build_payload(entry, channel_title):
    role_id = os.getenv("DISCORD_ROLE_ID", "").strip()
    bot_name = os.getenv("BOT_NAME", "YouTube Notifier").strip() or "YouTube Notifier"
    bot_avatar_url = os.getenv("BOT_AVATAR_URL", "").strip()

    mention = f"<@&{role_id}> " if role_id else ""
    thumbnail = ""

    media_thumbnail = entry.get("media_thumbnail")
    if media_thumbnail and isinstance(media_thumbnail, list):
        thumbnail = media_thumbnail[0].get("url", "")

    embed = {
        "title": entry.get("title", "Новое видео"),
        "url": entry.get("link", ""),
        "description": f"Канал: {channel_title}",
        "color": 16711680,
        "footer": {"text": "YouTube 
