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
    if not raw:
        legacy = os.getenv("YOUTUBE_CHANNEL_ID", "").strip()
        if legacy:
            return [legacy]
        raise ValueError("YOUTUBE_CHANNEL_IDS is not set")
    return [x.strip() for x in raw.split(",") if x.strip()]


def get_feed(channel_id):
    url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    feed = feedparser.parse(url)
    if getattr(feed, "bozo", False) and not feed.entries:
        raise RuntimeError(f"Failed to parse feed for channel {channel_id}")
    return feed


def build_payload(entry, channel_title):
    webhook_role_id = os.getenv("DISCORD_ROLE_ID", "").strip()
    bot_name = os.getenv("BOT_NAME", "YouTube Notifier").strip() or "YouTube Notifier"
    bot_avatar_url = os.getenv("BOT_AVATAR_URL", "").strip()

    mention = f"<@&{webhook_role_id}> " if webhook_role_id else ""
    thumbnail = ""

    media_thumbnail = entry.get("media_thumbnail")
    if media_thumbnail and isinstance(media_thumbnail, list):
        thumbnail = media_thumbnail[0].get("url", "")

    embed = {
        "title": entry.get("title", "Новое видео"),
        "url": entry.get("link", ""),
        "description": f"Канал: {channel_title}",
        "color": 16711680,
        "footer": {
            "text": "YouTube RSS → Discord"
        }
    }

    if thumbnail:
        embed["image"] = {"url": thumbnail}

    payload = {
        "content": f"{mention}Новое видео на канале!",
        "username": bot_name,
        "embeds": [embed]
    }

    if bot_avatar_url:
        payload["avatar_url"] = bot_avatar_url

    return payload


def post_to_discord(payload):
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL", "").strip()
    if not webhook_url:
        raise ValueError("DISCORD_WEBHOOK_URL is not set")

    response = requests.post(webhook_url, json=payload, timeout=20)
    if response.status_code >= 400:
        raise RuntimeError(
            f"Discord webhook failed: {response.status_code} {response.text}"
        )


def process_channel(channel_id, state):
    feed = get_feed(channel_id)

    if not feed.entries:
        return False

    latest = feed.entries[0]
    latest_video_id = latest.get("yt_videoid") or latest.get("id") or latest.get("link")
    channel_title = latest.get("author") or feed.feed.get("title") or channel_id

    channel_state = state.get(channel_id, {})
    last_video_id = channel_state.get("last_video_id")

    if latest_video_id == last_video_id:
        return False

    if last_video_id is not None:
        payload = build_payload(latest, channel_title)
        post_to_discord(payload)

    state[channel_id] = {
        "last_video_id": latest_video_id,
        "channel_title": channel_title
    }
    return True


def main():
    state = load_state()
    changed = False
    errors = []

    for channel_id in get_channel_ids():
        try:
            updated = process_channel(channel_id, state)
            changed = changed or updated
        except Exception as e:
            errors.append(f"{channel_id}: {e}")

    if changed:
        save_state(state)

    if errors:
        for err in errors:
            print(err, file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
