import os
import json
import sys
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from pathlib import Path
import requests
import xml.etree.ElementTree as ET

STATE_FILE = Path("state.json")
WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "").strip()
YOUTUBE_CHANNEL_IDS = [
    ch.strip()
    for ch in os.getenv("YOUTUBE_CHANNEL_IDS", "").split(",")
    if ch.strip()
]
ROLE_ID = os.getenv("DISCORD_ROLE_ID", "").strip()
BOT_NAME = os.getenv("BOT_NAME", "YouTube Notifier").strip() or "YouTube Notifier"
BOT_AVATAR_URL = os.getenv("BOT_AVATAR_URL", "").strip()
FORCE_CHANNEL_ID = os.getenv("FORCE_CHANNEL_ID", "").strip()
RESET_STATE = os.getenv("RESET_STATE", "").strip().lower() in ("1", "true", "yes")
YT_COLOR = 0xFF0000
RETRY_COUNT = 3
RETRY_DELAY = 5
MAX_POSTED_IDS = 50
FEED_ENTRIES_LIMIT = 15


def now_iso() -> str:
    return datetime.now(ZoneInfo("Europe/Moscow")).strftime("%d.%m.%Y %H:%M:%S MSK")


def fail(msg: str):
    print(msg)
    sys.exit(1)


def get_feed_url(channel_id: str) -> str:
    return f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_state(data: dict):
    data["last_updated"] = now_iso()
    STATE_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def get_posted_ids(state: dict, channel_id: str) -> list:
    channel_data = state.get("channels", {}).get(channel_id, {})
    if "video_id" in channel_data and "posted_video_ids" not in channel_data:
        return [channel_data["video_id"]]
    return channel_data.get("posted_video_ids", [])


def add_posted_ids(state: dict, channel_id: str, new_ids: list):
    state.setdefault("channels", {})
    existing = get_posted_ids(state, channel_id)
    merged = existing + new_ids
    merged = merged[-MAX_POSTED_IDS:]
    state["channels"][channel_id] = {
        "posted_video_ids": merged,
        "updated_at": now_iso()
    }


def fetch_with_retry(url: str, timeout: int = 30):
    for attempt in range(1, RETRY_COUNT + 1):
        try:
            resp = requests.get(url, timeout=timeout)
            resp.raise_for_status()
            return resp
        except requests.RequestException as e:
            print(f"[Attempt {attempt}/{RETRY_COUNT}] Request failed: {e}")
            if attempt < RETRY_COUNT:
                time.sleep(RETRY_DELAY)
    fail(f"Failed to fetch {url} after {RETRY_COUNT} attempts")


def parse_feed_videos(feed_xml: str, limit: int = FEED_ENTRIES_LIMIT) -> list:
    ns = {
        "atom": "http://www.w3.org/2005/Atom",
        "yt": "http://www.youtube.com/xml/schemas/2015",
        "media": "http://search.yahoo.com/mrss/"
    }
    root = ET.fromstring(feed_xml)
    entries = root.findall("atom:entry", ns)[:limit]
    videos = []
    for entry in entries:
        video_id = entry.findtext("yt:videoId", default="", namespaces=ns)
        title = entry.findtext("atom:title", default="New video", namespaces=ns)
        published = entry.findtext("atom:published", default="", namespaces=ns)
        link = entry.find("atom:link", ns)
        url = link.attrib.get("href") if link is not None else f"https://youtu.be/{video_id}"
        author = entry.find("atom:author", ns)
        channel_name = (
            author.findtext("atom:name", default="YouTube", namespaces=ns)
            if author is not None else "YouTube"
        )
        thumbnail = None
        group = entry.find("media:group", ns)
        if group is not None:
            thumb = group.find("media:thumbnail", ns)
            if thumb is not None:
                thumbnail = thumb.attrib.get("url")
        videos.append({
            "video_id": video_id,
            "title": title,
            "url": url,
            "channel_name": channel_name,
            "thumbnail": thumbnail,
            "published": published,
        })
    return videos


def send_to_discord(video, force: bool = False):
    mention = f"<@&{ROLE_ID}> " if ROLE_ID else ""
    label = "[FORCE] " if force else ""
    embed = {
        "title": video["title"],
        "url": video["url"],
        "description": f"Channel: **{video['channel_name']}**",
        "color": YT_COLOR,
        "footer": {"text": "YouTube RSS -> Discord"},
    }
    if video.get("published"):
        try:
            dt = datetime.fromisoformat(video["published"].replace("Z", "+00:00"))
            embed["timestamp"] = dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        except Exception:
            pass
    if video.get("thumbnail"):
        embed["image"] = {"url": video["thumbnail"]}
    payload = {
        "username": BOT_NAME,
        "content": f"{mention}{label}Вышло новое видео!",
        "embeds": [embed],
    }
    if BOT_AVATAR_URL:
        payload["avatar_url"] = BOT_AVATAR_URL
    for attempt in range(1, RETRY_COUNT + 1):
        try:
            r = requests.post(WEBHOOK_URL, json=payload, timeout=30)
            if r.status_code == 429:
                retry_after = r.json().get("retry_after", RETRY_DELAY)
                print(f"Discord rate limit. Waiting {retry_after}s...")
                time.sleep(float(retry_after))
                continue
            r.raise_for_status()
            return
        except requests.RequestException as e:
            print(f"[Attempt {attempt}/{RETRY_COUNT}] Discord send failed: {e}")
            if attempt < RETRY_COUNT:
                time.sleep(RETRY_DELAY)
    fail(f"Failed to send to Discord after {RETRY_COUNT} attempts")


def run_force(channel_id: str):
    print(f"[FORCE] Sending latest video from channel: {channel_id}")
    feed_url = get_feed_url(channel_id)
    resp = fetch_with_retry(feed_url)
    videos = parse_feed_videos(resp.text, limit=1)
    if not videos:
        fail(f"[FORCE] No videos found for channel: {channel_id}")
    video = videos[0]
    print(f"[FORCE] Sending: {video['title']}")
    send_to_discord(video, force=True)
    state = load_state()
    add_posted_ids(state, channel_id, [video["video_id"]])
    save_state(state)
    print(f"[FORCE] Done. state.json updated at {state['last_updated']}")


def run_reset_state():
    """Fetch all channels and update state.json without posting to Discord."""
    if not YOUTUBE_CHANNEL_IDS:
        fail("Missing YOUTUBE_CHANNEL_IDS")
    print("[RESET] Updating state.json without posting to Discord...")
    state = load_state()
    for channel_id in YOUTUBE_CHANNEL_IDS:
        print(f"[RESET] Fetching channel: {channel_id}")
        feed_url = get_feed_url(channel_id)
        resp = fetch_with_retry(feed_url)
        videos = parse_feed_videos(resp.text)
        if not videos:
            print(f"[RESET] No videos found for channel: {channel_id}")
            continue
        all_ids = [v["video_id"] for v in videos]
        add_posted_ids(state, channel_id, all_ids)
        print(f"[RESET] Saved {len(all_ids)} video IDs for channel {channel_id} (no Discord post)")
    save_state(state)
    print(f"[RESET] Done. state.json updated at {state['last_updated']}")


def main():
    if not WEBHOOK_URL:
        fail("Missing DISCORD_WEBHOOK_URL")
    if RESET_STATE:
        run_reset_state()
        return
    if FORCE_CHANNEL_ID:
        run_force(FORCE_CHANNEL_ID)
        return
    if not YOUTUBE_CHANNEL_IDS:
        fail("Missing YOUTUBE_CHANNEL_IDS")
    state = load_state()
    state_changed = False
    for channel_id in YOUTUBE_CHANNEL_IDS:
        print(f"Checking channel: {channel_id}")
        feed_url = get_feed_url(channel_id)
        resp = fetch_with_retry(feed_url)
        videos = parse_feed_videos(resp.text)
        if not videos:
            print(f"No videos found for channel: {channel_id}")
            continue
        posted_ids = get_posted_ids(state, channel_id)
        if not posted_ids:
            all_ids = [v["video_id"] for v in videos]
            add_posted_ids(state, channel_id, all_ids)
            state_changed = True
            print(f"[{channel_id}] Initialized with {len(all_ids)} videos. No notifications sent.")
            continue
        new_videos = [v for v in reversed(videos) if v["video_id"] not in posted_ids]
        if not new_videos:
            print(f"[{channel_id}] No new videos.")
            continue
        for video in new_videos:
            send_to_discord(video)
            print(f"[{channel_id}] Sent new video: {video['title']}")
            if len(new_videos) > 1:
                time.sleep(2)
        new_ids = [v["video_id"] for v in new_videos]
        add_posted_ids(state, channel_id, new_ids)
        state_changed = True
    if state_changed:
        save_state(state)
        print(f"state.json updated at {state['last_updated']}")
    else:
        state["last_checked"] = now_iso()
        save_state(state)
        print(f"No changes. state.json last_checked updated at {state['last_updated']}")


if __name__ == "__main__":
    main()
