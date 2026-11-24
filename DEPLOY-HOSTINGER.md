# Deploying GetFireFech on Hostinger (with a domain)

GetFireFech is a Python (Flask) app that uses **yt-dlp** and **ffmpeg**. It needs root access, so it
**will not run on Hostinger shared/web/WordPress hosting**. Use a **Hostinger VPS** with the
**Ubuntu 24.04 + Docker** template. Docker and Docker Compose come pre-installed on that template.

Everything below takes about 15 minutes.

---

## 1. Point the domain at the VPS

In hPanel go to **Domains → DNS / Nameservers** for the domain and add:

| Type | Name | Points to | TTL |
|---|---|---|---|
| A | `@` | VPS IP address | 300 |
| A | `www` | VPS IP address | 300 |

To keep an existing website on the main domain, use a subdomain instead,
e.g. `A  download → VPS IP` for `download.yourdomain.com`.

Wait until `ping yourdomain.com` shows the VPS IP (usually a few minutes, max a few hours).

## 2. Get the code onto the VPS

SSH in (hPanel → VPS → **SSH access** shows the command and root password):

```bash
ssh root@VPS_IP
git clone https://github.com/kiranyasin/getfirefech.git
cd getfirefech
```

(Or upload the zip with `scp getfirefech.zip root@VPS_IP:` and run `unzip getfirefech.zip`.)

## 3. Start it with your domain

```bash
DOMAIN=yourdomain.com docker compose up -d --build
```

That's it. Caddy obtains a free SSL certificate automatically, so after 1–2 minutes
**https://yourdomain.com** shows the tool.

Check it:
```bash
docker compose ps
curl https://yourdomain.com/api/health     # → {"ffmpeg":true,"ok":true,"ytdlp":true}
docker compose logs -f                     # live logs
```

To serve both `yourdomain.com` and `www.yourdomain.com`, run with the main one and
redirect `www` in DNS/hPanel, or set `DOMAIN=yourdomain.com` and add a CNAME `www → yourdomain.com`.

> If ports 80/443 are taken (e.g. by the template's own web server/Traefik), stop that service
> first or change the `ports` in `docker-compose.yml`.

## 4. Firewall

hPanel → VPS → **Firewall**: allow TCP **80** and **443** (and 22 for SSH).

---

## Putting the tool inside an existing website

**Option A: link or menu item (simplest).** Host the tool on `download.yourdomain.com` and link to it.

**Option B: embed in a page (WordPress or any HTML page)** with a Custom HTML block:
```html
<iframe src="https://download.yourdomain.com" style="width:100%;height:1400px;border:0"
        allow="clipboard-read; clipboard-write"></iframe>
```

**Option C: use your own page design and call the API.** Copy the HTML/CSS/JS from `index.html`
into the site, set `const API = "https://download.yourdomain.com";` in the script, and start
the server with the site allowed:
```bash
DOMAIN=download.yourdomain.com ALLOWED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com \
  docker compose up -d --build
```

---

## Maintenance

Sites like YouTube/Instagram change often. When downloads start failing, update yt-dlp by rebuilding:

```bash
cd getfirefech
git pull                      # if using git
docker compose build --no-cache app && docker compose up -d
```

Doing this every couple of weeks (or via a cron job) keeps things working:
```bash
crontab -e
0 4 * * 1 cd /root/getfirefech && docker compose build --no-cache app && docker compose up -d
```

**YouTube "Sign in to confirm you're not a bot":** YouTube sometimes blocks data-center IPs.
Export `cookies.txt` from a logged-in browser (e.g. the "Get cookies.txt LOCALLY" extension),
put it in the project folder, and add to the `app` service in `docker-compose.yml`:
```yaml
    volumes:
      - ./cookies.txt:/app/cookies.txt:ro
    environment:
      - COOKIES_FILE=/app/cookies.txt
```
then `docker compose up -d`.

## Settings

| Variable | Default | Meaning |
|---|---|---|
| `DOMAIN` | (none → http on :80) | Domain to serve with automatic HTTPS |
| `ALLOWED_ORIGINS` | (none) | Other sites allowed to call the API (Option C) |
| `MAX_DURATION_SECONDS` | 10800 | Longest video allowed (3 h) |

## Recommended VPS size

KVM 1 (1 vCPU / 4 GB) is enough to start. Merging HD video with ffmpeg uses CPU, so move to KVM 2
if many people use it at once.
