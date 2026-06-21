# ⚡ SPEED X FIFA World Cup Live 2026
**Developer: NIROB BBZ / SPEED_X** — All Rights Reserved © 2026

## 🚀 Setup

```bash
pip install -r requirements.txt
python app.py
```

Server runs on: `http://0.0.0.0:5000`

---

## ✅ What's Fixed & New

### 🔧 HLS CORS Proxy (Main Fix)
Links like `http://198.195.239.50:8095/btv/video.m3u8` no longer spin — the server
fetches the playlist and rewrites all `.ts` segment URLs through `/hls-proxy/segment`,
bypassing browser CORS restrictions completely.

### 🎨 New VIP Design
- Orbitron + Inter fonts — dark premium look
- Animated ticker, gradient logo, clean card layout

### 🛡️ Admin Panel Upgrades
- Sidebar navigation
- Real-time stat cards (viewers, channels, bans, uptime)
- Live user table auto-refreshes every 3 seconds
- System uptime counter

### 🤖 Telegram Bot Commands
| Command | Action |
|---|---|
| `/start` | Welcome + stats |
| `/ip <address>` | Full IP lookup with location, ISP, VPN check |
| `/ban <ip> [secs]` | Ban an IP (default 1 hour) |
| `/unban <ip>` | Release an IP |
| `/users` | List all live viewers |
| `/status` | Platform status |
| `/uptime` | Bot uptime |

---

## 📡 Adding Streams
In Admin Panel → "Add Stream Channel":
- Name: `BTV Live`
- URL: `http://198.195.239.50:8095/btv/video.m3u8`

The proxy handles everything automatically.
