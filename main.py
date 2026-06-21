
# ==============================================================================
#  PROJECT: SPEED X FIFA World Cup Live 2026
#  DEVELOPER: SPEED_X / NIROB BBZ — All Rights Reserved © 2026
#  ARCHITECTURE: HLS REVERSE PROXY + VIP SECURE PLATFORM
# ==============================================================================

import sqlite3
import time
import requests
import re
import threading
from flask import Flask, render_template_string, request, redirect, url_for, session, jsonify, Response, stream_with_context

app = Flask(__name__)
app.secret_key = "SPEED_X_ULTRA_SECRET_2026_FIFA"

BOT_TOKEN = "7728749662:AAHoOX61nxVXob7IxeAYV4KhgkrxyP9RimM"
ADMIN_ID  = "7224513731"

active_users = {}
bot_start_time = time.time()

# ─────────────────────────────────────────────
#  DATABASE
# ─────────────────────────────────────────────
def init_db():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS channels (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL, link TEXT NOT NULL, logo TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS banned_ips (
        ip TEXT PRIMARY KEY, ban_until REAL, reason TEXT)''')
    defaults = [
        ('site_name',      'SPEED X · FIFA World Cup 2026'),
        ('tg_channel',     'SPEED_X_CHANNELS'),
        ('admin_password', 'admin123'),
        ('site_status',    'ON'),
        ('bg_color',       '#04040e'),
    ]
    for k, v in defaults:
        c.execute("INSERT OR IGNORE INTO settings (key,value) VALUES (?,?)", (k, v))
    conn.commit(); conn.close()

init_db()

def get_setting(key):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key=?", (key,))
    row = c.fetchone(); conn.close()
    return row[0] if row else ""

def send_tg(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": ADMIN_ID, "text": text,
                                 "parse_mode": "Markdown"}, timeout=5)
    except: pass

def is_ip_banned(ip):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT ban_until FROM banned_ips WHERE ip=?", (ip,))
    row = c.fetchone(); conn.close()
    if row and time.time() < row[0]:
        return True, row[0]
    return False, 0

def ban_ip(ip, secs=300, reason="Policy Violation"):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO banned_ips VALUES (?,?,?)",
              (ip, time.time() + secs, reason))
    conn.commit(); conn.close()

def unban_ip(ip):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("DELETE FROM banned_ips WHERE ip=?", (ip,))
    conn.commit(); conn.close()

def track(action="Home"):
    ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    active_users[ip] = {'last_seen': time.time(), 'page': action}

def clean_users():
    t = time.time()
    for ip in [k for k,v in active_users.items() if t - v['last_seen'] > 15]:
        del active_users[ip]

def uptime_str():
    secs = int(time.time() - bot_start_time)
    h, r = divmod(secs, 3600); m, s = divmod(r, 60)
    return f"{h}h {m}m {s}s"

# ─────────────────────────────────────────────
#  HLS REVERSE PROXY  ← fixes the CORS problem
# ─────────────────────────────────────────────
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Linux; Android 11) AppleWebKit/537.36',
    'Accept': '*/*',
    'Connection': 'keep-alive',
}

@app.route('/hls-proxy/playlist')
def hls_proxy_playlist():
    """Fetch remote .m3u8, rewrite .ts segment URLs through our proxy."""
    if not session.get('tg_joined'):
        return "Forbidden", 403
    origin_url = request.args.get('url', '')
    if not origin_url:
        return "Missing url", 400
    try:
        r = requests.get(origin_url, headers=HEADERS, timeout=10)
        content = r.text
        base_url = origin_url.rsplit('/', 1)[0]

        def rewrite_line(line):
            line = line.strip()
            if not line or line.startswith('#'):
                return line
            # absolute URL
            if line.startswith('http://') or line.startswith('https://'):
                seg = line
            else:
                seg = base_url + '/' + line
            return url_for('hls_proxy_segment', url=seg, _external=False)

        rewritten = '\n'.join(rewrite_line(l) for l in content.splitlines())
        return Response(rewritten, content_type='application/vnd.apple.mpegurl',
                        headers={'Access-Control-Allow-Origin': '*',
                                 'Cache-Control': 'no-cache'})
    except Exception as e:
        return f"Proxy error: {e}", 502

@app.route('/hls-proxy/segment')
def hls_proxy_segment():
    """Stream a .ts segment to the browser."""
    if not session.get('tg_joined'):
        return "Forbidden", 403
    seg_url = request.args.get('url', '')
    if not seg_url:
        return "Missing url", 400
    try:
        r = requests.get(seg_url, headers=HEADERS, stream=True, timeout=15)
        def generate():
            for chunk in r.iter_content(1024 * 64):
                yield chunk
        return Response(stream_with_context(generate()),
                        content_type='video/mp2t',
                        headers={'Access-Control-Allow-Origin': '*',
                                 'Cache-Control': 'no-cache'})
    except Exception as e:
        return f"Segment error: {e}", 502

# ─────────────────────────────────────────────
#  STREAM ENDPOINT
# ─────────────────────────────────────────────
@app.route('/stream/<int:cid>')
def stream_info(cid):
    if not session.get('tg_joined'):
        return jsonify({"error": "Access Denied"}), 403
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT link FROM channels WHERE id=?", (cid,))
    row = c.fetchone(); conn.close()
    if not row:
        return jsonify({"error": "Not Found"}), 404
    original = row[0]
    proxy_url = url_for('hls_proxy_playlist', url=original, _external=False)
    return jsonify({"stream_url": proxy_url, "original": original})

# ─────────────────────────────────────────────
#  HTML TEMPLATES
# ─────────────────────────────────────────────
MAIN_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{{ site_name }}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&family=Inter:wght@300;400;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
<script src="https://cdn.jsdelivr.net/npm/hls.js@latest"></script>
<style>
:root{
  --r:#ff0044;--g:#00ffa3;--b:#0099ff;
  --bg:#04040e;--card:#090918;--border:rgba(0,255,163,.13);
}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:#e8e8f0;font-family:'Inter',sans-serif;min-height:100vh;overflow-x:hidden}
body::before{
  content:'';position:fixed;inset:0;
  background:radial-gradient(ellipse 80% 50% at 50% -10%,rgba(0,255,163,.07),transparent),
             radial-gradient(ellipse 60% 40% at 80% 110%,rgba(0,153,255,.05),transparent);
  pointer-events:none;z-index:0
}

/* ── TOP BAR ── */
.topbar{position:relative;z-index:10;display:flex;align-items:center;justify-content:space-between;
  padding:12px 20px;border-bottom:1px solid var(--border);
  background:rgba(4,4,14,.85);backdrop-filter:blur(12px)}
.logo{font-family:'Orbitron',monospace;font-weight:900;font-size:1.05rem;
  background:linear-gradient(90deg,var(--g),var(--b));-webkit-background-clip:text;
  -webkit-text-fill-color:transparent;letter-spacing:2px}
.live-pill{display:flex;align-items:center;gap:6px;background:rgba(255,0,68,.12);
  border:1px solid rgba(255,0,68,.4);padding:4px 12px;border-radius:50px;
  font-size:.75rem;font-weight:600;color:var(--r);animation:pulse 2s infinite}
.live-dot{width:7px;height:7px;background:var(--r);border-radius:50%;animation:blink 1s infinite}
@keyframes blink{0%,100%{opacity:1}50%{opacity:.2}}
@keyframes pulse{0%,100%{box-shadow:0 0 0 0 rgba(255,0,68,.3)}50%{box-shadow:0 0 0 6px rgba(255,0,68,0)}}

/* ── VPN BLOCK ── */
#vpn-screen{display:none;position:fixed;inset:0;background:#04040e;z-index:99999;
  align-items:center;justify-content:center;flex-direction:column;text-align:center;padding:20px}
.vpn-card{border:2px solid var(--r);border-radius:16px;padding:40px 28px;max-width:420px;
  background:rgba(255,0,68,.04);box-shadow:0 0 60px rgba(255,0,68,.2)}

/* ── LAYOUT ── */
.wrap{max-width:860px;margin:0 auto;padding:20px 14px;position:relative;z-index:1}

/* ── TELEGRAM GATE ── */
.tg-gate{background:var(--card);border:1px solid rgba(0,153,255,.25);border-radius:16px;
  padding:36px 20px;text-align:center;max-width:420px;margin:40px auto;
  box-shadow:0 0 40px rgba(0,153,255,.08)}
.tg-gate h2{font-family:'Orbitron';font-size:1.1rem;margin:14px 0 8px;color:var(--g)}
.tg-gate p{color:#888;font-size:.88rem;margin-bottom:20px;line-height:1.6}
.btn-tg{display:inline-flex;align-items:center;gap:8px;background:#0088cc;
  color:#fff;padding:11px 24px;border-radius:10px;text-decoration:none;
  font-weight:600;font-size:.9rem;transition:.2s;box-shadow:0 4px 20px rgba(0,136,204,.3)}
.btn-tg:hover{background:#006fa6;transform:translateY(-1px)}

/* ── PLAYER ── */
.player-wrap{max-width:640px;margin:0 auto 20px;border-radius:14px;overflow:hidden;
  border:1px solid rgba(0,255,163,.2);box-shadow:0 0 40px rgba(0,255,163,.06)}
.player-head{display:flex;justify-content:space-between;align-items:center;
  background:#070714;padding:8px 14px;font-size:.82rem}
.ch-label{color:var(--g);font-weight:600;display:flex;align-items:center;gap:6px}
.close-btn{background:rgba(255,0,68,.15);border:1px solid rgba(255,0,68,.4);
  color:var(--r);padding:4px 12px;border-radius:6px;cursor:pointer;
  text-decoration:none;font-size:.8rem;transition:.2s}
.close-btn:hover{background:var(--r);color:#fff}
.video-box{position:relative;background:#000}
video{width:100%;display:block;max-height:370px}
.wm{position:absolute;top:10px;right:10px;font-family:'Orbitron';font-size:.65rem;
  background:rgba(0,0,0,.65);padding:3px 8px;border-radius:4px;color:var(--g);
  border:1px solid rgba(0,255,163,.2);pointer-events:none}

/* ── FEEDBACK ── */
.fb-box{max-width:640px;margin:0 auto 28px;background:var(--card);
  border:1px solid var(--border);border-radius:12px;padding:14px 16px}
.fb-box h3{font-size:.88rem;color:var(--g);margin-bottom:10px}
.stars i{font-size:1.2rem;color:#333;cursor:pointer;margin-right:4px;transition:.2s}
.stars i.on,.stars i:hover{color:#ffc107;text-shadow:0 0 8px #ffc10755}
textarea.fb-input{width:100%;background:#0c0c20;border:1px solid rgba(255,255,255,.08);
  border-radius:8px;padding:9px;color:#ddd;font-family:'Inter';font-size:.88rem;
  resize:none;height:52px;margin:8px 0}
.fb-btn{width:100%;background:linear-gradient(90deg,var(--g),var(--b));
  color:#000;font-weight:700;border:none;border-radius:8px;padding:8px;
  cursor:pointer;font-size:.9rem;transition:.2s}
.fb-btn:hover{opacity:.9;box-shadow:0 0 14px rgba(0,255,163,.4)}

/* ── SECTION TITLE ── */
.sec-title{font-family:'Orbitron';font-size:.85rem;color:#fff;letter-spacing:2px;
  margin:10px 0 14px;padding-left:10px;border-left:3px solid var(--r)}

/* ── CHANNEL GRID ── */
.ch-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(110px,1fr));gap:10px}
.ch-card{background:var(--card);border:1px solid var(--border);border-radius:12px;
  padding:14px 10px;cursor:pointer;transition:.25s;text-decoration:none;color:#fff;
  display:flex;flex-direction:column;align-items:center;gap:8px}
.ch-card:hover{border-color:var(--r);transform:translateY(-3px);
  box-shadow:0 6px 20px rgba(255,0,68,.15)}
.ch-icon{width:48px;height:48px;border-radius:50%;background:#0d0d24;
  display:flex;align-items:center;justify-content:center;overflow:hidden;
  border:1px solid rgba(255,255,255,.06)}
.ch-icon img{width:100%;height:100%;object-fit:cover}
.ch-icon i{font-size:20px;color:var(--g)}
.ch-name{font-size:.82rem;font-weight:600;text-align:center;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;width:100%}

/* ── INFO TICKER ── */
.ticker{background:rgba(0,0,0,.4);border-top:1px solid var(--border);
  border-bottom:1px solid var(--border);padding:6px 0;overflow:hidden;margin-bottom:18px}
.ticker-inner{display:flex;gap:48px;white-space:nowrap;animation:ticker 25s linear infinite}
@keyframes ticker{from{transform:translateX(100vw)}to{transform:translateX(-100%)}}
.ticker-inner span{font-size:.78rem;color:var(--g);opacity:.7}

/* ── DEV TAG ── */
.dev-tag{position:fixed;bottom:14px;left:14px;background:rgba(4,4,14,.9);
  border:1px solid var(--border);padding:5px 10px;border-radius:6px;
  font-size:.72rem;color:#888;z-index:9999;display:flex;align-items:center;gap:6px}
.dev-tag b{color:var(--r)}

/* ── FOOTER ── */
footer{text-align:center;padding:20px;border-top:1px solid var(--border);
  font-family:'Orbitron';font-size:.7rem;color:#333;margin-top:30px}
footer span{color:var(--g)}
</style>
</head>
<body>

<div id="vpn-screen">
  <div class="vpn-card">
    <i class="fas fa-shield-virus" style="font-size:52px;color:var(--r);margin-bottom:14px"></i>
    <h2 style="color:var(--r);font-family:Orbitron;font-size:1.1rem;margin-bottom:10px">VPN DETECTED</h2>
    <p style="line-height:1.7;font-size:.95rem">Proxy/VPN connection identified.<br>
    <span style="color:var(--g);font-weight:600">IP banned for 5 minutes.</span><br>
    Disconnect VPN and try again.</p>
  </div>
</div>

<div class="topbar">
  <div class="logo">⚡ SPEED_X</div>
  <div class="live-pill"><span class="live-dot"></span> LIVE FIFA 2026</div>
</div>

<div class="ticker">
  <div class="ticker-inner">
    <span>🏆 FIFA WORLD CUP 2026</span>
    <span>⚡ SPEED_X SECURE PLATFORM</span>
    <span>📡 VIP LIVE STREAMING ACTIVE</span>
    <span>🔒 ANTI-VPN PROTECTION ENABLED</span>
    <span>🌐 GLOBAL VIEWERS CONNECTED</span>
    <span>🏆 FIFA WORLD CUP 2026</span>
    <span>⚡ SPEED_X SECURE PLATFORM</span>
  </div>
</div>

<div class="wrap">

  {% if not session.get('tg_joined') %}
  <div class="tg-gate">
    <i class="fab fa-telegram" style="font-size:52px;color:#0088cc"></i>
    <h2>Verification Required</h2>
    <p>Join our official Telegram channel to unlock<br>VIP live streaming access.</p>
    <a href="https://t.me/{{ tg_channel }}" target="_blank" class="btn-tg" onclick="doVerify()">
      <i class="fab fa-telegram"></i> JOIN CHANNEL TO UNLOCK
    </a>
  </div>

  {% else %}

  {% if ch_id %}
  <div class="player-wrap">
    <div class="player-head">
      <span class="ch-label"><i class="fa-solid fa-satellite-dish"></i> {{ ch_name }}</span>
      <a href="{{ url_for('home') }}" class="close-btn"><i class="fa-solid fa-xmark"></i> Close</a>
    </div>
    <div class="video-box">
      <video id="player" controls autoplay muted playsinline></video>
      <div class="wm">SPEED_X · SECURE</div>
    </div>
  </div>

  <div class="fb-box">
    <h3><i class="fa-solid fa-signal"></i> Stream Feedback</h3>
    <div class="stars" id="stars">
      {% for i in range(1,6) %}
      <i class="fa-solid fa-star" data-v="{{ i }}"></i>
      {% endfor %}
    </div>
    <textarea class="fb-input" id="fb-msg" placeholder="Comment on stream quality…"></textarea>
    <button class="fb-btn" onclick="sendFB('{{ ch_id }}')">SUBMIT FEEDBACK</button>
  </div>
  {% endif %}

  <div class="sec-title">VIP LIVE CHANNELS</div>
  <div class="ch-grid">
    {% for ch in channels %}
    <a href="?ch_id={{ ch[0] }}" class="ch-card">
      <div class="ch-icon">
        {% if ch[3] %}<img src="{{ ch[3] }}" alt="">{% else %}<i class="fa-solid fa-tv"></i>{% endif %}
      </div>
      <div class="ch-name">{{ ch[1] }}</div>
    </a>
    {% endfor %}
  </div>
  {% endif %}

  <footer>POWERED BY <span>{{ site_name }}</span> · NIROB BBZ © 2026</footer>
</div>

<div class="dev-tag"><i class="fa-solid fa-code"></i> Dev: <b>SPEED_X</b></div>

<script>
// ── Anti-VPN ──
function vpnCheck(){
  fetch('https://ipapi.co/json/').then(r=>r.json()).then(d=>{
    if(d.vpn||d.proxy||/Hosting|VPN|Proxy/.test(d.org||'')){
      autoBan(d.ip,d.org||'Unknown');
    }
  }).catch(()=>{
    fetch('https://ipinfo.io/json').then(r=>r.json()).then(d=>{
      if(/Hosting|VPN|Proxy/.test(d.org||'')) autoBan(d.ip||'?',d.org);
    });
  });
}
function autoBan(ip,org){
  fetch('/api/auto-ban',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({ip,detail:org})}).then(()=>{
    document.getElementById('vpn-screen').style.display='flex';
    document.querySelector('.wrap').style.display='none';
  });
}
vpnCheck();
setInterval(vpnCheck,3000);
document.addEventListener('visibilitychange',()=>{if(document.visibilityState==='visible')vpnCheck();});

// ── Telegram verify ──
function doVerify(){
  fetch('/api/verify',{method:'POST'});
  setTimeout(()=>location.href='{{ url_for("bypass_tg") }}',1600);
}

// ── Stars ──
let rating=5;
document.querySelectorAll('#stars i').forEach(s=>{
  s.addEventListener('click',function(){
    rating=+this.dataset.v;
    document.querySelectorAll('#stars i').forEach(x=>x.classList.toggle('on',+x.dataset.v<=rating));
  });
});
document.querySelectorAll('#stars i')[4]?.classList.add('on');

function sendFB(cid){
  let msg=document.getElementById('fb-msg').value.trim();
  if(!msg){alert('Please write a comment.');return;}
  fetch('/api/feedback',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({channel_id:cid,rating,msg})})
  .then(()=>{alert('Feedback sent!');document.getElementById('fb-msg').value='';});
}

// ── HLS Player ──
{% if ch_id %}
document.addEventListener('DOMContentLoaded',()=>{
  const video=document.getElementById('player');
  fetch('/stream/{{ ch_id }}').then(r=>r.json()).then(d=>{
    if(!d.stream_url){alert('Stream not found.');return;}
    const src=d.stream_url;
    if(Hls.isSupported()){
      const hls=new Hls({maxBufferLength:20,debug:false});
      hls.loadSource(src);
      hls.attachMedia(video);
      hls.on(Hls.Events.MANIFEST_PARSED,()=>video.play().catch(()=>{}));
      hls.on(Hls.Events.ERROR,(e,d)=>{if(d.fatal)hls.startLoad();});
    } else if(video.canPlayType('application/vnd.apple.mpegurl')){
      video.src=src;
      video.play().catch(()=>{});
    }
  });
});
{% endif %}

// ── Heartbeat ──
setInterval(()=>fetch('/api/hb?p={% if ch_id %}ch:{{ ch_id }}{% else %}home{% endif %}'),5000);
</script>
</body>
</html>
"""

ADMIN_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>SPEED_X Admin Panel</title>
<link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&family=JetBrains+Mono:wght@400;600&family=Inter:wght@300;400;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
<style>
:root{--r:#ff0044;--g:#00ffa3;--b:#0099ff;--y:#ffc107;--bg:#04040e;--card:#080817;--border:rgba(0,255,163,.12)}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:#dde;font-family:'Inter',sans-serif;min-height:100vh}

/* ── SIDEBAR ── */
.sidebar{position:fixed;top:0;left:0;width:220px;height:100vh;background:#060613;
  border-right:1px solid var(--border);padding:0;overflow-y:auto;z-index:100}
.sb-logo{padding:20px 16px;border-bottom:1px solid var(--border)}
.sb-logo h1{font-family:'Orbitron';font-size:.95rem;color:var(--g);letter-spacing:1px}
.sb-logo small{color:#555;font-size:.7rem}
.sb-nav a{display:flex;align-items:center;gap:10px;padding:11px 16px;color:#888;
  text-decoration:none;font-size:.83rem;font-weight:500;transition:.2s;border-left:3px solid transparent}
.sb-nav a:hover,.sb-nav a.active{color:var(--g);border-left-color:var(--g);background:rgba(0,255,163,.04)}
.sb-nav .sec{padding:12px 16px 6px;font-size:.68rem;color:#444;letter-spacing:2px;text-transform:uppercase}

/* ── MAIN ── */
.main{margin-left:220px;padding:24px;min-height:100vh}
.page-title{font-family:'Orbitron';font-size:1rem;color:#fff;margin-bottom:20px;
  padding-bottom:12px;border-bottom:1px solid var(--border);display:flex;align-items:center;gap:10px}
.page-title i{color:var(--g)}

/* ── STAT CARDS ── */
.stats{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:14px;margin-bottom:24px}
.stat{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:16px;
  display:flex;flex-direction:column;gap:6px}
.stat-label{font-size:.72rem;color:#555;text-transform:uppercase;letter-spacing:1.5px}
.stat-val{font-family:'Orbitron';font-size:1.5rem;font-weight:700}
.stat-sub{font-size:.72rem;color:#555}
.stat.green .stat-val{color:var(--g)}
.stat.red   .stat-val{color:var(--r)}
.stat.blue  .stat-val{color:var(--b)}
.stat.yel   .stat-val{color:var(--y)}

/* ── BOXES ── */
.box{background:var(--card);border:1px solid var(--border);border-radius:12px;
  padding:18px;margin-bottom:18px}
.box-title{font-family:'Orbitron';font-size:.8rem;color:var(--g);margin-bottom:14px;
  display:flex;align-items:center;gap:8px}
.box-title i{color:var(--r)}

/* ── FORM ── */
input,select,textarea{width:100%;background:#0c0c20;border:1px solid rgba(255,255,255,.07);
  border-radius:8px;padding:9px 12px;color:#ddd;font-family:'Inter';font-size:.86rem;
  margin-bottom:10px;transition:.2s}
input:focus,select:focus{outline:none;border-color:rgba(0,255,163,.4)}
.btn{width:100%;padding:9px;border:none;border-radius:8px;font-weight:700;
  cursor:pointer;font-family:'Inter';font-size:.88rem;transition:.2s;letter-spacing:.5px}
.btn-g{background:linear-gradient(90deg,var(--g),#00ccff);color:#000}
.btn-r{background:var(--r);color:#fff}
.btn-y{background:var(--y);color:#000}
.btn-g:hover{box-shadow:0 0 14px rgba(0,255,163,.4)}
.btn-r:hover{box-shadow:0 0 14px rgba(255,0,68,.4)}

/* ── TABLE ── */
.tbl{width:100%;border-collapse:collapse;font-size:.82rem}
.tbl th{background:#0a0a1e;color:var(--g);padding:9px 10px;text-align:left;
  font-size:.72rem;text-transform:uppercase;letter-spacing:1px;border-bottom:1px solid var(--border)}
.tbl td{padding:9px 10px;border-bottom:1px solid rgba(255,255,255,.03);color:#bbb}
.tbl tr:hover td{background:rgba(255,255,255,.02)}
.badge{display:inline-block;padding:2px 8px;border-radius:4px;font-size:.7rem;font-weight:600}
.badge-g{background:rgba(0,255,163,.12);color:var(--g);border:1px solid rgba(0,255,163,.2)}
.badge-r{background:rgba(255,0,68,.12);color:var(--r);border:1px solid rgba(255,0,68,.2)}
.badge-b{background:rgba(0,153,255,.12);color:var(--b);border:1px solid rgba(0,153,255,.2)}
.badge-y{background:rgba(255,193,7,.12);color:var(--y);border:1px solid rgba(255,193,7,.2)}
.del-btn{color:var(--r);text-decoration:none;font-size:.78rem;padding:3px 8px;
  border:1px solid rgba(255,0,68,.3);border-radius:4px;transition:.2s}
.del-btn:hover{background:var(--r);color:#fff}

/* ── GRID ── */
.grid2{display:grid;grid-template-columns:1fr 1.6fr;gap:20px}
@media(max-width:900px){.grid2{grid-template-columns:1fr}.sidebar{width:180px}.main{margin-left:180px}}
@media(max-width:650px){.sidebar{position:static;width:100%;height:auto}.main{margin-left:0}}

/* ── UPTIME ── */
.uptime-bar{background:#0a0a1e;border:1px solid var(--border);border-radius:8px;
  padding:10px 14px;font-family:'JetBrains Mono';font-size:.8rem;color:var(--g);margin-bottom:12px}
</style>
</head>
<body>

<aside class="sidebar">
  <div class="sb-logo">
    <h1>⚡ SPEED_X</h1>
    <small>Admin Control Panel</small>
  </div>
  <nav class="sb-nav">
    <div class="sec">Monitor</div>
    <a href="#stats" class="active"><i class="fa-solid fa-chart-line fa-fw"></i> Dashboard</a>
    <a href="#users"><i class="fa-solid fa-users fa-fw"></i> Live Users</a>
    <a href="#bans"><i class="fa-solid fa-shield-halved fa-fw"></i> IP Firewall</a>
    <div class="sec">Management</div>
    <a href="#channels"><i class="fa-solid fa-tv fa-fw"></i> Channels</a>
    <a href="#settings"><i class="fa-solid fa-gear fa-fw"></i> Settings</a>
    <div class="sec">Account</div>
    <a href="{{ url_for('logout') }}" style="color:var(--r)"><i class="fa-solid fa-right-from-bracket fa-fw"></i> Logout</a>
  </nav>
</aside>

<main class="main">
  <div class="page-title" id="stats">
    <i class="fa-solid fa-terminal"></i> NIROB BBZ CONTROL INFRASTRUCTURE
  </div>

  <!-- STATS -->
  <div class="stats">
    <div class="stat green">
      <div class="stat-label">Live Viewers</div>
      <div class="stat-val" id="sc-users">{{ active_count }}</div>
      <div class="stat-sub">Active right now</div>
    </div>
    <div class="stat blue">
      <div class="stat-label">Channels</div>
      <div class="stat-val">{{ channels|length }}</div>
      <div class="stat-sub">Live streams loaded</div>
    </div>
    <div class="stat red">
      <div class="stat-label">Banned IPs</div>
      <div class="stat-val">{{ banned_list|length }}</div>
      <div class="stat-sub">Active firewall blocks</div>
    </div>
    <div class="stat yel">
      <div class="stat-label">System Uptime</div>
      <div class="stat-val" id="sc-uptime" style="font-size:1rem;padding-top:4px">{{ uptime }}</div>
      <div class="stat-sub">Since last restart</div>
    </div>
    <div class="stat" style="border-color:{{ 'rgba(0,255,163,.3)' if site_status == 'ON' else 'rgba(255,0,68,.3)' }}">
      <div class="stat-label">Platform Status</div>
      <div class="stat-val" style="color:{{ '#00ffa3' if site_status == 'ON' else '#ff0044' }};font-size:1rem">
        {{ '🟢 ONLINE' if site_status == 'ON' else '🔴 OFFLINE' }}
      </div>
      <div class="stat-sub">{{ site_name }}</div>
    </div>
  </div>

  <div class="grid2">
    <!-- LEFT COL -->
    <div>
      <!-- ADD CHANNEL -->
      <div class="box">
        <div class="box-title"><i class="fa-solid fa-plus-circle"></i> Add Stream Channel</div>
        <form action="{{ url_for('admin_add') }}" method="POST">
          <input name="name" placeholder="Channel Name" required>
          <input name="link" placeholder="M3U8 Stream URL (http://…/video.m3u8)" required>
          <input name="logo" placeholder="Logo Image URL (optional)">
          <button class="btn btn-g" type="submit"><i class="fa-solid fa-satellite-dish"></i> INJECT CHANNEL</button>
        </form>
      </div>

      <!-- IP BAN -->
      <div class="box" id="bans">
        <div class="box-title"><i class="fa-solid fa-ban"></i> IP Firewall Controls</div>
        <form action="{{ url_for('admin_manual_ban') }}" method="POST" style="margin-bottom:14px">
          <input name="ip" placeholder="Target IP Address" required>
          <input name="duration" type="number" placeholder="Duration in seconds (e.g. 300)" required>
          <button class="btn btn-r" type="submit"><i class="fa-solid fa-lock"></i> BAN IP</button>
        </form>
        <form action="{{ url_for('admin_manual_unban') }}" method="POST">
          <input name="ip" placeholder="IP to Release from Ban" required>
          <button class="btn btn-y" type="submit"><i class="fa-solid fa-key"></i> UNBAN IP</button>
        </form>
      </div>

      <!-- SETTINGS -->
      <div class="box" id="settings">
        <div class="box-title"><i class="fa-solid fa-gear"></i> Platform Settings</div>
        <form action="{{ url_for('admin_settings') }}" method="POST">
          <label style="font-size:.72rem;color:#555;text-transform:uppercase;letter-spacing:1px">Site Name</label>
          <input name="site_name" value="{{ site_name }}">
          <label style="font-size:.72rem;color:#555;text-transform:uppercase;letter-spacing:1px">Telegram Channel</label>
          <input name="tg_channel" value="{{ tg_channel }}">
          <label style="font-size:.72rem;color:#555;text-transform:uppercase;letter-spacing:1px">Admin Password</label>
          <input name="admin_password" type="password" value="{{ admin_password }}">
          <label style="font-size:.72rem;color:#555;text-transform:uppercase;letter-spacing:1px">Site Status</label>
          <select name="site_status">
            <option value="ON" {{ 'selected' if site_status=='ON' }}>🟢 ONLINE</option>
            <option value="OFF" {{ 'selected' if site_status=='OFF' }}>🔴 MAINTENANCE</option>
          </select>
          <button class="btn btn-g" type="submit"><i class="fa-solid fa-floppy-disk"></i> SAVE SETTINGS</button>
        </form>
      </div>
    </div>

    <!-- RIGHT COL -->
    <div>
      <!-- LIVE USERS -->
      <div class="box" id="users">
        <div class="box-title"><i class="fa-solid fa-users"></i> Live Viewers — <span id="lv-count">{{ active_count }}</span> online</div>
        <div class="uptime-bar">⏱ System Uptime: <span id="lv-uptime">{{ uptime }}</span></div>
        <div style="max-height:200px;overflow-y:auto">
          <table class="tbl">
            <thead><tr><th>IP Address</th><th>Current Page</th><th>Status</th></tr></thead>
            <tbody id="user-tbody">
              {% for ip,d in active_users.items() %}
              <tr>
                <td><code style="font-size:.78rem;color:var(--b)">{{ ip }}</code></td>
                <td>{{ d.page }}</td>
                <td><span class="badge badge-g">ONLINE</span></td>
              </tr>
              {% endfor %}
            </tbody>
          </table>
        </div>
      </div>

      <!-- BANNED IPs -->
      <div class="box">
        <div class="box-title"><i class="fa-solid fa-shield-halved"></i> Active Firewall Restrictions</div>
        <div style="max-height:180px;overflow-y:auto">
          <table class="tbl">
            <thead><tr><th>Banned IP</th><th>Time Left</th><th>Reason</th></tr></thead>
            <tbody>
              {% for rec in banned_list %}
              <tr>
                <td><code style="font-size:.78rem;color:var(--r)">{{ rec[0] }}</code></td>
                <td><span class="badge badge-r">{{ rec[1] }}s</span></td>
                <td><span style="font-size:.75rem;color:#888">{{ rec[2] }}</span></td>
              </tr>
              {% endfor %}
            </tbody>
          </table>
        </div>
      </div>

      <!-- CHANNELS TABLE -->
      <div class="box" id="channels">
        <div class="box-title"><i class="fa-solid fa-list"></i> Stream Channel Database</div>
        <div style="max-height:280px;overflow-y:auto">
          <table class="tbl">
            <thead><tr><th>Icon</th><th>Channel Name</th><th>Stream URL</th><th>Action</th></tr></thead>
            <tbody>
              {% for ch in channels %}
              <tr>
                <td>{% if ch[3] %}<img src="{{ ch[3] }}" width="26" height="26" style="border-radius:50%;vertical-align:middle">
                    {% else %}<i class="fa-solid fa-tv" style="color:var(--g)"></i>{% endif %}</td>
                <td><b style="color:#ddd">{{ ch[1] }}</b></td>
                <td><code style="font-size:.7rem;color:#555;word-break:break-all">{{ ch[2][:45] }}…</code></td>
                <td><a href="{{ url_for('admin_delete', id=ch[0]) }}" class="del-btn"><i class="fa-solid fa-trash"></i></a></td>
              </tr>
              {% endfor %}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</main>

<script>
function refreshUsers(){
  fetch('/admin/api/users').then(r=>r.json()).then(d=>{
    document.getElementById('lv-count').textContent=d.count;
    document.getElementById('sc-users').textContent=d.count;
    document.getElementById('lv-uptime').textContent=d.uptime;
    document.getElementById('sc-uptime').textContent=d.uptime;
    let rows='';
    for(let ip in d.users){
      rows+=`<tr><td><code style="font-size:.78rem;color:var(--b)">${ip}</code></td>
             <td>${d.users[ip].page}</td>
             <td><span class="badge badge-g">ONLINE</span></td></tr>`;
    }
    document.getElementById('user-tbody').innerHTML=rows||'<tr><td colspan="3" style="color:#444;text-align:center">No active users</td></tr>';
  });
}
setInterval(refreshUsers,3000);
</script>
</body>
</html>
"""

LOGIN_HTML = """<!DOCTYPE html>
<html><head>
<meta charset="UTF-8">
<title>Admin Login · SPEED_X</title>
<link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@700;900&family=Inter:wght@400;600&display=swap" rel="stylesheet">
<style>
body{background:#04040e;display:flex;align-items:center;justify-content:center;
  height:100vh;margin:0;font-family:'Inter',sans-serif}
.card{background:#080817;border:1px solid rgba(0,255,163,.2);border-radius:16px;
  padding:36px 28px;width:320px;text-align:center;box-shadow:0 0 60px rgba(0,255,163,.05)}
h2{font-family:'Orbitron';color:#00ffa3;font-size:1rem;letter-spacing:1px;margin-bottom:6px}
p{color:#555;font-size:.8rem;margin-bottom:24px}
input{width:100%;background:#0c0c20;border:1px solid rgba(255,255,255,.07);
  border-radius:8px;padding:11px 14px;color:#ddd;font-size:.9rem;
  margin-bottom:14px;text-align:center;letter-spacing:2px}
input:focus{outline:none;border-color:rgba(0,255,163,.4)}
button{width:100%;background:linear-gradient(90deg,#00ffa3,#0099ff);
  color:#000;font-weight:700;border:none;border-radius:8px;padding:11px;
  cursor:pointer;font-size:.9rem;letter-spacing:.5px}
button:hover{opacity:.9}
</style>
</head><body>
<div class="card">
  <h2>⚡ SPEED_X ADMIN</h2>
  <p>NIROB BBZ Control Infrastructure</p>
  <form action="/admin/login" method="POST">
    <input type="password" name="password" placeholder="Enter Passphrase" required>
    <button type="submit">AUTHENTICATE</button>
  </form>
</div>
</body></html>
"""

MAINTENANCE_HTML = """<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>Maintenance</title>
<style>body{background:#04040e;color:#ddd;font-family:sans-serif;display:flex;
align-items:center;justify-content:center;height:100vh;margin:0;text-align:center}
.card{border:1px dashed rgba(255,0,68,.3);padding:40px;border-radius:16px;max-width:420px}
h2{color:#ff0044;font-size:1.3rem;margin-bottom:12px}p{color:#666;line-height:1.7}</style>
</head><body><div class="card">
<h2>⚙️ System Maintenance</h2>
<p>Platform is currently offline for upgrades.<br>We'll be back shortly.</p>
</div></body></html>
"""

BANNED_HTML = """<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>Banned</title>
<style>body{background:#04040e;color:#ddd;font-family:sans-serif;display:flex;
align-items:center;justify-content:center;height:100vh;margin:0;text-align:center}
.card{border:2px solid #ff0044;padding:40px;border-radius:16px;max-width:440px;
box-shadow:0 0 50px rgba(255,0,68,.2)}
h2{color:#ff0044;margin-bottom:14px}
code{background:#0a0a1e;padding:2px 8px;border-radius:4px;color:#0099ff}
.timer{color:#00ffa3;font-size:1.3rem;font-weight:700;margin-top:10px}</style>
</head><body><div class="card">
<h2>🛡️ ACCESS DENIED</h2>
<p>IP <code>{ip}</code> is currently banned.<br>
<span class="timer">{remaining}s remaining</span><br><br>
Disconnect VPN/Proxy and try again.</p>
</div></body></html>
"""

# ─────────────────────────────────────────────
#  ROUTES
# ─────────────────────────────────────────────
@app.before_request
def firewall():
    ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    if not request.path.startswith('/admin') and request.path != '/api/auto-ban':
        banned, bu = is_ip_banned(ip)
        if banned:
            return BANNED_HTML.format(ip=ip, remaining=int(bu - time.time())), 403

@app.route('/')
def home():
    if get_setting('site_status') == 'OFF':
        return MAINTENANCE_HTML
    ip  = request.headers.get('X-Forwarded-For', request.remote_addr)
    cid = request.args.get('ch_id')
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT id,name,link,logo FROM channels")
    channels = c.fetchall()
    ch_name = ""
    if cid:
        track(f"Streaming ch:{cid}")
        c.execute("SELECT name FROM channels WHERE id=?", (cid,))
        row = c.fetchone()
        ch_name = row[0] if row else "Unknown"
        send_tg(f"📺 *Stream Started*\nIP: `{ip}`\nChannel: *{ch_name}* (ID:{cid})")
    elif session.get('tg_joined'):
        track("Dashboard")
    conn.close()
    return render_template_string(MAIN_HTML, channels=channels,
        ch_id=cid, ch_name=ch_name,
        site_name=get_setting('site_name'),
        tg_channel=get_setting('tg_channel'))

@app.route('/bypass-verification')
def bypass_tg():
    ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    session['tg_joined'] = True
    send_tg(f"🔓 *Verified*\nIP: `{ip}` unlocked the platform.")
    return redirect(url_for('home'))

# ── APIs ──
@app.route('/api/auto-ban', methods=['POST'])
def api_auto_ban():
    d = request.get_json() or {}
    ip = d.get('ip', request.headers.get('X-Forwarded-For', request.remote_addr))
    detail = d.get('detail', 'Unknown')
    ban_ip(ip, 300, f"Auto: VPN/Proxy ({detail})")
    send_tg(f"🚨 *Auto-Ban Triggered*\nIP: `{ip}`\nReason: `{detail}`")
    return jsonify({"banned": True})

@app.route('/api/verify', methods=['POST'])
def api_verify():
    ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    send_tg(f"🔗 *Telegram Click*\nIP: `{ip}` clicked the join button.")
    return jsonify({"ok": True})

@app.route('/api/hb')
def api_hb():
    p = request.args.get('p', 'active')
    ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    active_users[ip] = {'last_seen': time.time(), 'page': p}
    clean_users()
    return jsonify({"ok": True})

@app.route('/api/feedback', methods=['POST'])
def api_feedback():
    d = request.get_json()
    ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    stars = "⭐" * int(d.get('rating', 5))
    send_tg(f"📝 *Feedback*\nChannel: {d.get('channel_id')}\n{stars}\n_{d.get('msg')}_\nIP: `{ip}`")
    return jsonify({"ok": True})

# ── Admin ──
@app.route('/admin')
def admin():
    ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    if not session.get('admin_logged'):
        send_tg(f"👁️ *Admin Page Visited*\nIP: `{ip}` accessed `/admin`.")
        return LOGIN_HTML
    clean_users()
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT id,name,link,logo FROM channels")
    channels = c.fetchall()
    c.execute("SELECT ip,ban_until,reason FROM banned_ips")
    raw_bans = c.fetchall(); conn.close()
    now = time.time()
    banned_list = [(b[0], int(b[1]-now), b[2]) for b in raw_bans if b[1] > now]
    return render_template_string(ADMIN_HTML,
        channels=channels, banned_list=banned_list,
        active_users=active_users, active_count=len(active_users),
        site_name=get_setting('site_name'), tg_channel=get_setting('tg_channel'),
        admin_password=get_setting('admin_password'),
        site_status=get_setting('site_status'), uptime=uptime_str())

@app.route('/admin/login', methods=['POST'])
def admin_login():
    ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    pw = request.form.get('password')
    if pw == get_setting('admin_password'):
        session['admin_logged'] = True
        send_tg(f"✅ *Admin Login*\nIP: `{ip}` authenticated successfully.")
        return redirect(url_for('admin'))
    send_tg(f"❌ *Wrong Password*\nIP: `{ip}` tried: `{pw}`")
    return '<script>alert("Wrong password!");history.back();</script>'

@app.route('/admin/add', methods=['POST'])
def admin_add():
    if not session.get('admin_logged'): return redirect(url_for('admin'))
    name = request.form['name']; link = request.form['link']; logo = request.form.get('logo','')
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("INSERT INTO channels (name,link,logo) VALUES (?,?,?)", (name,link,logo))
    conn.commit(); conn.close()
    send_tg(f"➕ *Channel Added*\n`{name}`\n`{link}`")
    return redirect(url_for('admin'))

@app.route('/admin/delete/<int:id>')
def admin_delete(id):
    if not session.get('admin_logged'): return redirect(url_for('admin'))
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT name FROM channels WHERE id=?", (id,))
    row = c.fetchone()
    c.execute("DELETE FROM channels WHERE id=?", (id,))
    conn.commit(); conn.close()
    send_tg(f"🗑️ *Channel Deleted*\n`{row[0] if row else id}`")
    return redirect(url_for('admin'))

@app.route('/admin/manual-ban', methods=['POST'])
def admin_manual_ban():
    if not session.get('admin_logged'): return redirect(url_for('admin'))
    ip = request.form['ip']; dur = int(request.form.get('duration', 300))
    ban_ip(ip, dur, "Manual ban by admin")
    send_tg(f"🚫 *Manual Ban*\nIP: `{ip}` for `{dur}s`")
    return redirect(url_for('admin'))

@app.route('/admin/manual-unban', methods=['POST'])
def admin_manual_unban():
    if not session.get('admin_logged'): return redirect(url_for('admin'))
    ip = request.form['ip']; unban_ip(ip)
    send_tg(f"🔓 *Manual Unban*\nIP: `{ip}` released.")
    return redirect(url_for('admin'))

@app.route('/admin/settings', methods=['POST'])
def admin_settings():
    if not session.get('admin_logged'): return redirect(url_for('admin'))
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    for k in ('site_name','tg_channel','admin_password','site_status'):
        c.execute("UPDATE settings SET value=? WHERE key=?", (request.form.get(k), k))
    conn.commit(); conn.close()
    send_tg("⚙️ *Settings Updated* via Admin Panel.")
    return redirect(url_for('admin'))

@app.route('/admin/api/users')
def admin_api_users():
    clean_users()
    return jsonify({"count": len(active_users), "users": active_users, "uptime": uptime_str()})

@app.route('/admin/logout')
def logout():
    session.pop('admin_logged', None)
    return redirect(url_for('admin'))

# ─────────────────────────────────────────────
#  TELEGRAM BOT (background polling)
# ─────────────────────────────────────────────
def get_ip_info(ip):
    try:
        d = requests.get(f"https://ipapi.co/{ip}/json/", timeout=6).json()
        flag = d.get('country_code', '??')
        return (
            f"╔══════ SPEED_X · IP INTEL ══════╗\n"
            f"🌐  IP      : {d.get('ip','?')}\n"
            f"🏳️  Country : {d.get('country_name','?')} [{flag}]\n"
            f"🏙️  City    : {d.get('city','?')}\n"
            f"📍  Region  : {d.get('region','?')}\n"
            f"🏢  ISP/Org : {d.get('org','?')}\n"
            f"⏱️  Timezone: {d.get('timezone','?')}\n"
            f"🛡️  VPN/Prx : {d.get('proxy', False)}\n"
            f"📶  ASN     : {d.get('asn','?')}\n"
            f"╚═══════════════════════════════╝"
        )
    except:
        return "❌ Failed to fetch IP info."

def bot_reply(chat_id, text):
    try:
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                      json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}, timeout=5)
    except: pass

def bot_loop():
    offset = 0
    while True:
        try:
            r = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates",
                             params={"offset": offset, "timeout": 20}, timeout=25).json()
            for upd in r.get("result", []):
                offset = upd["id"] + 1
                msg = upd.get("message", {})
                cid = msg.get("chat", {}).get("id")
                txt = msg.get("text", "").strip()
                if not cid or not txt: continue

                if txt == "/start":
                    bot_reply(cid,
                        f"⚡ *SPEED_X FIFA 2026 BOT*\n"
                        f"━━━━━━━━━━━━━━━━━━━━━\n"
                        f"🔧 Dev: *NIROB BBZ*\n"
                        f"⏱ Uptime: `{uptime_str()}`\n"
                        f"👥 Viewers: `{len(active_users)}`\n"
                        f"━━━━━━━━━━━━━━━━━━━━━\n"
                        f"*Commands:*\n"
                        f"`/ip <address>` — IP lookup\n"
                        f"`/ban <ip> <secs>` — Ban IP\n"
                        f"`/unban <ip>` — Unban IP\n"
                        f"`/users` — Live viewer list\n"
                        f"`/status` — Platform status\n"
                        f"`/uptime` — Bot uptime")

                elif txt.startswith("/ip "):
                    bot_reply(cid, get_ip_info(txt[4:].strip()))

                elif txt.startswith("/ban "):
                    parts = txt.split()
                    if len(parts) >= 2:
                        target = parts[1]
                        dur = int(parts[2]) if len(parts) >= 3 else 3600
                        ban_ip(target, dur, "Banned via Telegram Bot")
                        bot_reply(cid, f"🚫 IP `{target}` banned for `{dur}s`.")

                elif txt.startswith("/unban "):
                    target = txt[7:].strip()
                    unban_ip(target)
                    bot_reply(cid, f"🔓 IP `{target}` unbanned.")

                elif txt == "/users":
                    clean_users()
                    if not active_users:
                        bot_reply(cid, "👥 No active viewers right now.")
                    else:
                        lines = [f"👥 *Live Viewers ({len(active_users)}):*"]
                        for ip, d in active_users.items():
                            lines.append(f"• `{ip}` — {d['page']}")
                        bot_reply(cid, "\n".join(lines))

                elif txt == "/status":
                    bot_reply(cid,
                        f"📊 *Platform Status*\n"
                        f"Site: `{get_setting('site_status')}`\n"
                        f"Viewers: `{len(active_users)}`\n"
                        f"Uptime: `{uptime_str()}`\n"
                        f"Name: `{get_setting('site_name')}`")

                elif txt == "/uptime":
                    bot_reply(cid, f"⏱ Bot uptime: `{uptime_str()}`")

        except Exception as e:
            time.sleep(3)

threading.Thread(target=bot_loop, daemon=True).start()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
