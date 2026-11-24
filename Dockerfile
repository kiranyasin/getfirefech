FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Deno: the JavaScript runtime yt-dlp needs to solve YouTube's challenges
COPY --from=denoland/deno:bin /deno /usr/local/bin/deno

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -U -r requirements.txt
COPY . .

ENV PORT=8000
EXPOSE 8000
# long timeout: big videos take time to download + merge
CMD gunicorn -w 2 --threads 4 -t 900 -b 0.0.0.0:$PORT app:app
