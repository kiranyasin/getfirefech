"""GetFireFech — paste a link, download video, audio only, or video without sound.

Backend: Flask + yt-dlp + ffmpeg. Files are written to a temp folder, streamed
to the user, then deleted right away. Nothing is stored on the server.
"""
import os
import re
import shutil
import tempfile
import threading
import time

from flask import Flask, jsonify, request, send_file, send_from_directory, after_this_request

try:
    import yt_dlp
except ImportError:  # lets the UI load even before deps are installed
    yt_dlp = None

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, static_folder=None)

# Comma-separated list of other websites allowed to call this API
# (only needed if the page is hosted on a different domain than this server).
ALLOWED_ORIGINS = {o.strip().rstrip("/") for o in os.environ.get("ALLOWED_ORIGINS", "").split(",") if o.strip()}


@app.after_request
def _cors(resp):
    origin = request.headers.get("Origin", "").rstrip("/")
    if origin and ("*" in ALLOWED_ORIGINS or origin in ALLOWED_ORIGINS):
        resp.headers["Access-Control-Allow-Origin"] = origin
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
        resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        resp.headers["Access-Control-Expose-Headers"] = "Content-Disposition"
        resp.headers["Vary"] = "Origin"
    return resp


@app.route("/api/<path:_p>", methods=["OPTIONS"])
def _preflight(_p):
    return ("", 204)


MAX_DURATION = int(os.environ.get("MAX_DURATION_SECONDS", 60 * 60 * 3))  # 3 h
URL_RE = re.compile(r"^https?://", re.I)


def _base_opts():
    opts = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "restrictfilenames": False,
        "socket_timeout": 30,
    }
    cookies = os.environ.get("COOKIES_FILE")
    if cookies and os.path.exists(cookies):
        opts["cookiefile"] = cookies
    return opts


def _need_ytdlp():
    if yt_dlp is None:
        return jsonify(error="yt-dlp is not installed on the server. Run: pip install -r requirements.txt"), 500
    return None


def _safe_name(title: str) -> str:
    name = re.sub(r'[\\/:*?"<>|\n\r\t]+', " ", title or "video")
    name = re.sub(r"\s+", " ", name).strip()
    return (name[:150] or "video").rstrip(". ")


def _check_url(url):
    if not url or not URL_RE.match(url):
        return "Please paste a full link that starts with http:// or https://"
    return None


@app.get("/")
def index():
    return send_from_directory(BASE_DIR, "index.html")


@app.get("/api/health")
def health():
    return jsonify(ok=True, ytdlp=bool(yt_dlp), ffmpeg=bool(shutil.which("ffmpeg")))


@app.post("/api/info")
def info():
    err = _need_ytdlp()
    if err:
        return err
    url = (request.get_json(silent=True) or {}).get("url", "").strip()
    bad = _check_url(url)
    if bad:
        return jsonify(error=bad), 400
    try:
        with yt_dlp.YoutubeDL(_base_opts()) as ydl:
            data = ydl.extract_info(url, download=False)
    except Exception as e:  # yt-dlp raises many types
        msg = str(e).replace("ERROR: ", "")
        return jsonify(error=f"Couldn't read that link. {msg[:300]}"), 422

    if data.get("_type") == "playlist" and data.get("entries"):
        data = next((x for x in data["entries"] if x), data)

    formats = data.get("formats") or []
    heights = sorted(
        {f["height"] for f in formats if f.get("height") and f.get("vcodec") not in (None, "none")},
        reverse=True,
    )
    has_audio = any(f.get("acodec") not in (None, "none") for f in formats) or not formats
    has_video = bool(heights) or any(f.get("vcodec") not in (None, "none") for f in formats)

    return jsonify(
        title=data.get("title") or "Untitled",
        uploader=data.get("uploader") or data.get("channel") or "",
        thumbnail=data.get("thumbnail") or "",
        duration=data.get("duration") or 0,
        site=data.get("extractor_key") or data.get("extractor") or "",
        heights=heights,
        has_audio=has_audio,
        has_video=has_video,
        webpage_url=data.get("webpage_url") or url,
    )


def _build_opts(mode: str, height: int | None, audio_fmt: str, outdir: str):
    opts = _base_opts()
    opts["outtmpl"] = os.path.join(outdir, "%(title).150B.%(ext)s")
    h = f"[height<={height}]" if height else ""

    if mode == "audio":
        opts["format"] = "bestaudio/best"
        if audio_fmt == "mp3":
            opts["postprocessors"] = [
                {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "320"}
            ]
        else:  # m4a
            opts["format"] = "bestaudio[ext=m4a]/bestaudio/best"
            opts["postprocessors"] = [{"key": "FFmpegExtractAudio", "preferredcodec": "m4a"}]
    elif mode == "mute":
        opts["format"] = f"bestvideo{h}[ext=mp4]/bestvideo{h}/best{h}/best"
        opts["merge_output_format"] = "mp4"
        # strip any audio track that came along (e.g. single-file formats)
        opts["postprocessor_args"] = {"ffmpeg": ["-an"]}
        opts["postprocessors"] = [{"key": "FFmpegVideoRemuxer", "preferedformat": "mp4"}]
    else:  # video with sound
        opts["format"] = (
            f"bestvideo{h}[ext=mp4]+bestaudio[ext=m4a]/"
            f"bestvideo{h}+bestaudio/best{h}/best"
        )
        opts["merge_output_format"] = "mp4"
    return opts


@app.get("/api/download")
def download():
    err = _need_ytdlp()
    if err:
        return err
    url = request.args.get("url", "").strip()
    mode = request.args.get("mode", "video")
    audio_fmt = request.args.get("afmt", "mp3")
    try:
        height = int(request.args.get("h") or 0) or None
    except ValueError:
        height = None

    bad = _check_url(url)
    if bad:
        return jsonify(error=bad), 400
    if mode not in ("video", "audio", "mute"):
        return jsonify(error="Unknown format."), 400

    outdir = tempfile.mkdtemp(prefix="gff_")
    try:
        with yt_dlp.YoutubeDL(_base_opts()) as ydl:
            meta = ydl.extract_info(url, download=False)
        if (meta.get("duration") or 0) > MAX_DURATION:
            shutil.rmtree(outdir, ignore_errors=True)
            return jsonify(error="That video is too long for this server."), 413

        with yt_dlp.YoutubeDL(_build_opts(mode, height, audio_fmt, outdir)) as ydl:
            ydl.download([url])
    except Exception as e:
        shutil.rmtree(outdir, ignore_errors=True)
        return jsonify(error=f"Download failed. {str(e).replace('ERROR: ', '')[:300]}"), 422

    files = [f for f in os.listdir(outdir) if not f.endswith((".part", ".ytdl"))]
    if not files:
        shutil.rmtree(outdir, ignore_errors=True)
        return jsonify(error="Download produced no file."), 500
    path = os.path.join(outdir, max(files, key=lambda f: os.path.getsize(os.path.join(outdir, f))))

    ext = os.path.splitext(path)[1]
    suffix = " (no sound)" if mode == "mute" else ""
    filename = _safe_name(meta.get("title")) + suffix + ext

    @after_this_request
    def _cleanup(resp):
        # delete shortly after the response finishes streaming
        threading.Timer(120, shutil.rmtree, args=(outdir,), kwargs={"ignore_errors": True}).start()
        return resp

    return send_file(path, as_attachment=True, download_name=filename)


def _sweep_old_temp():
    """Safety net: remove any temp folders older than 30 minutes."""
    while True:
        root = tempfile.gettempdir()
        for d in os.listdir(root):
            p = os.path.join(root, d)
            if d.startswith("gff_") and os.path.isdir(p) and time.time() - os.path.getmtime(p) > 1800:
                shutil.rmtree(p, ignore_errors=True)
        time.sleep(600)


threading.Thread(target=_sweep_old_temp, daemon=True).start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)), debug=False)
