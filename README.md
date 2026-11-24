# GetFireFech 🔥

Paste a link from YouTube, TikTok, Instagram, X, Facebook, and 1,000+ other sites. Download:

- **Video**: with sound, any quality the site offers (MP4)
- **Audio**: sound only (MP3 320k or M4A)
- **No sound**: video only, audio removed (MP4)

Built with Python (Flask), [yt-dlp](https://github.com/yt-dlp/yt-dlp) and ffmpeg. Files go to a temp folder, get sent to the user, then get deleted.

## Run on your computer

You need Python 3.10+ and ffmpeg (`brew install ffmpeg`, `sudo apt install ffmpeg`, or `winget install ffmpeg`).

```bash
cd getfirefech
pip install -r requirements.txt
python app.py
```

Open http://localhost:8000

## Put it online

Vercel **can't** run this backend, because its serverless functions don't have ffmpeg and time out too soon. Use a host that runs Docker:

**Render** (free tier available)
1. Push this folder to a GitHub repo.
2. On render.com, choose New → Web Service, pick the repo, and set Runtime to **Docker**.
3. Deploy. Your site will be at `https://getfirefech.onrender.com` (or similar).

**Railway / Fly.io / any VPS**: they all use the included `Dockerfile`.
```bash
docker build -t getfirefech .
docker run -p 8000:8000 getfirefech
```

## Settings (environment variables)

| Name | What it does |
|---|---|
| `PORT` | Port to listen on (default 8000) |
| `MAX_DURATION_SECONDS` | Longest video allowed (default 10800 = 3 h) |
| `COOKIES_FILE` | Path to a cookies.txt. This helps with Instagram/YouTube when they block server IPs |

## Keep it working

Sites change often. If downloads start failing, update yt-dlp:
```bash
pip install -U yt-dlp
```
(On Render, just redeploy, which installs the latest yt-dlp.)

YouTube sometimes blocks data-center IPs ("Sign in to confirm you're not a bot"). The fix is passing a `COOKIES_FILE` exported from a logged-in browser.

## API

- `POST /api/info` with `{"url": "..."}` returns the title, thumbnail, duration and available qualities
- `GET /api/download?url=...&mode=video|audio|mute&h=1080&afmt=mp3|m4a` returns the file
- `GET /api/health` returns status

## Note

Only download videos you own or have permission to save. Respect each platform's terms.
