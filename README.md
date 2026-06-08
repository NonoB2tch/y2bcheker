# YouTube -> Discord via GitHub Actions

Automatically checks YouTube RSS and posts new videos to a Discord channel via webhook.

## How it works

- Runs every 5 minutes via GitHub Actions `schedule`
- Fetches the latest video from a YouTube channel RSS feed
- Sends a Discord embed notification when a new video is detected
- Saves the last seen video ID in `state.json` to avoid duplicate posts
- Supports **force-posting** any video on demand

## Files

| File | Description |
|------|-------------|
| `youtube_to_discord.py` | Main script |
| `.github/workflows/youtube-discord.yml` | GitHub Actions workflow |
| `requirements.txt` | Python dependencies |
| `state.json` | Auto-created after first run |

## Setup

### 1. GitHub Secrets

Go to `Settings` -> `Secrets and variables` -> `Actions` -> `New repository secret`

| Secret | Required | Description |
|--------|----------|-------------|
| `DISCORD_WEBHOOK_URL` | Yes | Discord webhook URL |
| `YOUTUBE_CHANNEL_ID` | Yes | YouTube channel ID (e.g. `UCxxxxx`) |
| `DISCORD_ROLE_ID` | No | Role ID to ping on new video |
| `BOT_NAME` | No | Webhook bot display name |
| `BOT_AVATAR_URL` | No | Webhook bot avatar URL |

### 2. First run

Run the workflow manually via `Actions` -> `YouTube to Discord` -> `Run workflow` (leave field empty).

The first run **does not send** a Discord message - it only saves the current latest video to `state.json` as a baseline. All subsequent new videos will trigger notifications.

### 3. Automatic runs

After the first run, the workflow triggers automatically every 5 minutes via cron schedule.

## Force-post

You can force-post the latest video from any channel on demand:

1. Go to `Actions` -> `YouTube to Discord` -> `Run workflow`
2. Enter a YouTube Channel ID in the `Channel ID to force-post` field
3. Click `Run workflow`

The bot will immediately post the latest video from that channel to Discord with a `[FORCE]` label. It also updates `state.json` so the next automatic run won't re-post it.

## How to get a YouTube Channel ID

1. Open the channel page on YouTube
2. Open the page source (`Ctrl+U`) and search for `"externalId"` — the value next to it is the Channel ID

Or check the RSS feed directly:
```
https://www.youtube.com/feeds/videos.xml?channel_id=YOUR_CHANNEL_ID
```

## Discord message format

Each notification includes:
- Role mention (if `DISCORD_ROLE_ID` is set)
- Embed with video title (clickable link), channel name, thumbnail, and publish timestamp
- Red color bar (#FF0000)
- Footer: `YouTube RSS -> Discord`

## Notes

- GitHub Actions `schedule` may have delays of a few minutes under high load
- Keep `DISCORD_WEBHOOK_URL` private - anyone with it can post to your channel
- The role must have `Allow anyone to mention this role` enabled for pings to work
