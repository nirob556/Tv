# ==============================================================================
#  PROJECT: SPEED X FIFA World Cup live match 2026
#  DEVELOPER & PROGRAMMER: SPEED_X / NIROB BBZ (All Rights Reserved © 2026)
#  SECURITY: ANTI-CRACK API MASKING & REVERSE PROXY INFRASTRUCTURE
# ==============================================================================

import sqlite3
import time
import requests
from flask import Flask, render_template_string, request, redirect, url_for, session, jsonify, Response

app = Flask(__name__)
app.secret_key = "SPEED_X_SECRET_KEY_FIFA_2026"

# Telegram Bot Token
BOT_TOKEN = "7728749662:AAHoOX61nxVXob7IxeAYV4KhgkrxyP9RimM"
ADMIN_ID = "7224513731"  

active_users = {}

# --- Database Initialize & Setup ---
def init_db():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            link TEXT NOT NULL,
            logo TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('site_name', 'SPEED X FIFA World Cup live match 2026')")
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('tg_channel', 'SPEED_X_CHANNELS')")
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('admin_password', 'admin123')") # অ্যাডমিন পাসওয়ার্ড ব্যাকএন্ডে থাকবে
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('site_status', 'ON')") 
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('bg_url', '#03030a')") 
    conn.commit()
    conn.close()

init_db()

# --- Core Helper Functions ---
def get_setting(key):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key=?", (key,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else ""

def send_telegram_alert(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        if ADMIN_ID:
            requests.post(url, json={"chat_id": ADMIN_ID, "text": text, "parse_mode": "Markdown"})
        else:
            updates = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates").json()
            if updates.get("result"):
                chat_id = updates["result"][-1]["message"]["chat"]["id"]
                requests.post(url, json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"})
    except Exception as e:
        print(f"Telegram Error: {e}")

def track_user(action="Home"):
    ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    active_users[ip] = {'last_seen': time.time(), 'channel': action}

def clean_inactive_users():
    current_time = time.time()
    to_delete = [ip for ip, data in active_users.items() if current_time - data['last_seen'] > 15]
    for ip in to_delete:
        del active_users[ip]

# --- UI TEMPLATES ---

BASE_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Live Streaming Platform</title>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/video.js/8.10.0/video-js.min.css" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Audiowide&family=Rajdhani:wght@600;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        * { box-sizing: border-box; margin:0; padding:0; }
        body {
            background: {{ bg_url }}; color: #fff; font-family: 'Rajdhani', sans-serif;
            background-image: linear-gradient(to right, rgba(0,255,204,0.02) 1px, transparent 1px), linear-gradient(to bottom, rgba(255,0,85,0.02) 1px, transparent 1px);
            background-size: 35px 35px; overflow-x: hidden;
        }
        
        /* Anti-VPN Overlay Lock Box */
        #vpn-blockscreen {
            display: none; position: fixed; top: 0; left: 0; width: 100vw; height: 100vh;
            background: #04040c; z-index: 1000000; justify-content: center; align-items: center; text-align: center; padding: 20px;
        }
        .vpn-box { border: 2px dashed #ff0055; padding: 40px 20px; border-radius: 12px; box-shadow: 0 0 30px rgba(255,0,85,0.4); max-width: 450px; width: 100%; }

        .neon-bar { height: 4px; background: linear-gradient(90deg, #ff0055, #00ffcc, #ff0055); background-size: 200%; animation: moveG 3s linear infinite; }
        @keyframes moveG { 0% {background-position:0%} 100% {background-position:200%} }
        
        .container { max-width: 800px; margin: 15px auto; padding: 0 12px; text-align: center; }
        header h1 { font-family: 'Audiowide', sans-serif; font-size: 1.8rem; margin: 10px 0; text-shadow: 0 0 12px #00ffcc; letter-spacing: 1px; }
        
        .live-badge { display: inline-flex; align-items: center; gap: 8px; background: rgba(255,0,85,0.1); border: 1px solid #ff0055; padding: 4px 12px; border-radius: 50px; color: #ff0055; font-weight:700; animation: pulse 2s infinite; font-size:0.85rem;}
        @keyframes pulse { 0%, 100% { transform:scale(1); } 50% { transform:scale(1.03); box-shadow: 0 0 15px #ff0055; } }
        
        .tg-lock { background: rgba(8,8,20,0.95); border: 2px solid #ff0055; padding: 30px 15px; border-radius: 12px; margin: 20px auto; max-width: 400px; box-shadow: 0 0 25px rgba(255,0,85,0.3); }
        .btn-tg { display: inline-block; background: #0088cc; color: #fff; padding: 10px 22px; border-radius: 25px; text-decoration: none; font-weight: bold; margin-top: 15px; box-shadow: 0 0 12px #0088cc; }
        
        /* FIXED COMPACT VIDEO PLAYER FRAME */
        .video-wrapper { max-width: 580px; margin: 0 auto 15px; position: relative; }
        .player-header { display: flex; justify-content: space-between; align-items: center; background: #080816; border: 1px solid rgba(0,255,204,0.3); border-bottom: none; padding: 6px 12px; border-top-left-radius: 10px; border-top-right-radius: 10px; }
        .close-stream-btn { background: rgba(255, 0, 85, 0.15); border: 1px solid #ff0055; color: #ff0055; padding: 3px 10px; border-radius: 50px; cursor: pointer; font-weight: bold; text-decoration: none; font-size: 0.85rem; transition: 0.3s; }
        .close-stream-btn:hover { background: #ff0055; color: #fff; box-shadow: 0 0 8px #ff0055; }
        
        .video-box { background: #000; border: 2px solid #00ffcc; border-bottom-left-radius: 10px; border-bottom-right-radius: 10px; padding: 2px; box-shadow: 0 0 20px rgba(0,255,204,0.25); position: relative; overflow: hidden; width: 100%; max-height: 320px; }
        .video-js { width: 100% !important; height: 230px !important; border-radius: 6px; }
        @media(min-width: 600px) { .video-js { height: 310px !important; } }
        
        .video-watermark { position: absolute; top: 12px; right: 12px; z-index: 10; font-family: 'Audiowide'; font-size: 0.7rem; background: rgba(0,0,0,0.6); padding: 3px 8px; border-radius: 4px; border: 1px solid rgba(0,255,204,0.3); color: #00ffcc; pointer-events: none; }

        /* REACTION & FEEDBACK BOX */
        .feedback-box { max-width: 580px; margin: 15px auto; background: #0a0a1f; border: 1px solid rgba(255,0,85,0.2); padding: 12px; border-radius: 10px; text-align: left; }
        .stars { display: flex; gap: 8px; margin: 6px 0; }
        .stars i { font-size: 1.3rem; color: #444; cursor: pointer; transition: 0.2s; }
        .stars i.active, .stars i:hover { color: #ffcc00; text-shadow: 0 0 8px #ffcc00; }
        .feedback-box textarea { width: 100%; background: #12122b; border: 1px solid rgba(255,255,255,0.1); border-radius: 6px; padding: 8px; color: #fff; font-family: 'Rajdhani'; font-size: 0.95rem; height: 50px; resize: none; margin-top: 5px; }
        .submit-review-btn { background: #00ffcc; color: #000; font-weight: bold; padding: 6px 15px; border: none; border-radius: 4px; margin-top: 6px; cursor: pointer; font-family: 'Rajdhani'; transition: 0.3s; width: 100%; font-size:0.95rem; }
        .submit-review-btn:hover { box-shadow: 0 0 10px #00ffcc; }

        /* GRID SYSTEM */
        .channel-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(120px, 1fr)); gap: 10px; justify-content: center; margin-top: 15px; }
        .channel-card { background: #070716; border: 1px solid rgba(0,255,204,0.12); border-radius: 10px; padding: 12px; cursor: pointer; transition: 0.3s; text-decoration: none; color: #fff; display: block;}
        .channel-card:hover { border-color: #ff0055; transform: translateY(-3px); box-shadow: 0 4px 12px rgba(255,0,85,0.2); }
        .channel-logo { width: 50px; height: 50px; margin: 0 auto 6px; display: flex; align-items: center; justify-content: center; background: #0f0f26; border-radius: 50px; border: 1px solid rgba(255,255,255,0.06); overflow: hidden; }
        .channel-logo img { width: 100%; height: 100%; object-fit: cover; }
        .channel-logo i { font-size: 24px; color: #00ffcc; }
        .channel-name { font-size: 0.9rem; font-weight: bold; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
        
        .dev-popup { position: fixed; bottom: 12px; left: 12px; background: rgba(5,5,15,0.92); border: 1px solid #00ffcc; padding: 6px 10px; border-radius: 6px; display: flex; align-items: center; gap: 8px; box-shadow: 0 0 12px rgba(0,255,204,0.3); z-index: 9999; font-size: 0.8rem;}
        footer { margin-top: 40px; padding: 15px; border-top: 1px dashed rgba(255,255,255,0.06); font-family: 'Audiowide'; font-size: 0.8rem;}
        footer span { color: #ff0055; text-shadow: 0 0 8px #ff0055; }
    </style>
</head>
<body>
    <div id="vpn-blockscreen">
        <div class="vpn-box">
            <i class="fas fa-shield-virus" style="font-size: 55px; color: #ff0055; margin-bottom: 15px;"></i>
            <h2 style="color: #ff0055; letter-spacing: 1px; font-size: 1.5rem; margin-bottom: 10px;">VPN PROHIBITED!</h2>
            <p style="color: #fff; font-size: 1.1rem; line-height: 1.5; font-family:'Rajdhani'; font-weight:bold;">
                SECURITY DETECTED A PROXY/VPN CONNECTION.<br>
                <span style="color:#00ffcc;">PLEASE DISCONNECT YOUR VPN</span> TO RESTORE ACCESS TO THE LIVE STREAM.
            </p>
        </div>
    </div>

    <div class="neon-bar"></div>
    <div class="dev-popup">
        <i class="fa-solid fa-user-gear"></i>
        <span>Developer: <b style="color:#ff0055; text-shadow: 0 0 5px #ff0055;">SPEED_X</b></span>
    </div>

    <div class="container">
        <header>
            <div class="live-badge"><i class="fa-solid fa-bolt"></i> VIP SECURE CORE v4.0</div>
            <h1>{{ site_name }}</h1>
        </header>

        {% if not session.get('tg_joined') %}
        <div class="tg-lock">
            <i class="fa-brands fa-telegram" style="font-size: 50px; color: #0088cc;"></i>
            <h2 style="margin-top:10px;">Verification Lock!</h2>
            <p style="color: #aaa; margin-top: 5px; font-size: 0.9rem;">You must pass safety check by joining our official Telegram channel.</p>
            <a href="https://t.me/{{ tg_channel }}" target="_blank" class="btn-tg" onclick="verifyJoin()">👉 JOIN CHANNEL TO UNLOCK</a>
        </div>
        {% else %}
        
        {% if current_channel_id %}
        <div class="video-wrapper">
            <div class="player-header">
                <span style="color: #00ffcc; font-weight: bold; font-size:0.85rem;"><i class="fa-solid fa-satellite-dish"></i> Live Server Active</span>
                <a href="{{ url_for('home') }}" class="close-stream-btn"><i class="fa-solid fa-xmark"></i> Close</a>
            </div>
            <div class="video-box">
                <div class="video-watermark">SPEED_X SECURE</div>
                <video id="vip-player" class="video-js vjs-default-skin vjs-big-play-centered" controls preload="auto" data-setup='{}'>
                    <source src="/stream/{{ current_channel_id }}" type="application/x-mpegURL">
                </video>
            </div>
        </div>

        <div class="feedback-box">
            <h3 style="font-size:1rem; color:#00ffcc;"><i class="fa-solid fa-star-half-stroke"></i> Live Server Reaction Feed</h3>
            <div class="stars" id="star-rating-container">
                <i class="fa-solid fa-star" data-value="1"></i>
                <i class="fa-solid fa-star" data-value="2"></i>
                <i class="fa-solid fa-star" data-value="3"></i>
                <i class="fa-solid fa-star" data-value="4"></i>
                <i class="fa-solid fa-star" data-value="5"></i>
            </div>
            <textarea id="user-comment-input" placeholder="Say something about streaming quality or request issues..."></textarea>
            <button class="submit-review-btn" onclick="submitReview('{{ current_channel_id }}')">SUBMIT SYSTEM REACTION</button>
        </div>
        {% else %}
        <div style="background: rgba(0,255,204,0.02); padding: 15px; border-radius: 10px; border: 1px dashed rgba(0,255,204,0.3); margin-bottom: 20px; max-width: 580px; margin-left: auto; margin-right: auto;">
            <p style="font-size: 0.95rem; color: #00ffcc;"><i class="fa-solid fa-play"></i> Deploy any Streaming Server Channel Base Matrix Below!</p>
        </div>
        {% endif %}

        <h2 style="text-align: left; font-size: 1.1rem; margin-bottom: 12px; border-left: 4px solid #ff0055; padding-left: 8px; font-family:'Audiowide';">VIP ACCESS MATRIX SERVERS</h2>
        <div class="channel-grid">
            {% for ch in channels %}
            <a href="?ch_id={{ ch[0] }}" class="channel-card">
                <div class="channel-logo">
                    {% if ch[3] %}
                    <img src="{{ ch[3] }}" alt="logo">
                    {% else %}
                    <i class="fa-solid fa-tv"></i>
                    {% endif %}
                </div>
                <div class="channel-name">{{ ch[1] }}</div>
            </a>
            {% endfor %}
        </div>
        {% endif %}

        <footer>
            POWERED BY: <span>{{ site_name }}</span>
        </footer>
    </div>

    <script src="https://cdnjs.cloudflare.com/ajax/libs/video.js/8.10.0/video.min.js"></script>
    <script>
        // --- REAL-TIME NO REFRESH ANTI-VPN LOGIC ---
        function runAntiVPNDetection() {
            fetch('https://ipapi.co/json/')
                .then(res => res.json())
                .then(data => {
                    if (data.vpn === true || data.proxy === true || data.org === "Google LLC" || data.org.includes("Hosting") || data.org.includes("VPN") || data.org.includes("Proxy")) {
                        triggerBlockMode();
                    }
                })
                .catch(() => {
                    fetch('https://ipinfo.io/json')
                        .then(res => res.json())
                        .then(backupData => {
                            if(backupData.org && (backupData.org.includes("Hosting") || backupData.org.includes("VPN") || backupData.org.includes("Proxy"))){
                                triggerBlockMode();
                            }
                        });
                });
        }

        function triggerBlockMode() {
            const blockScreen = document.getElementById('vpn-blockscreen');
            if(blockScreen && blockScreen.style.display !== 'flex') {
                blockScreen.style.display = 'flex';
                const container = document.querySelector('.container');
                if(container) container.style.display = 'none';
                const player = document.getElementById('vip-player');
                if(player) player.pause();
            }
        }

        runAntiVPNDetection();
        setInterval(runAntiVPNDetection, 2000); // প্রতি ২ সেকেন্ডে নো-রিফ্রেশ অটো-চেক লুপ

        // --- FEEDBACK SYSTEM ---
        let selectedRating = 5;
        document.querySelectorAll('#star-rating-container i').forEach(star => {
            star.addEventListener('click', function() {
                selectedRating = this.getAttribute('data-value');
                document.querySelectorAll('#star-rating-container i').forEach(s => {
                    s.classList.toggle('active', s.getAttribute('data-value') <= selectedRating);
                });
            });
        });

        function submitReview(chId) {
            let comment = document.getElementById('user-comment-input').value;
            if(!comment.trim()){ alert("Please write a comment message!"); return;}
            fetch('/api/feedback', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ channel_id: chId, rating: selectedRating, msg: comment })
            }).then(res => res.json()).then(data => {
                alert("Reaction Transmitted Successfully!");
                document.getElementById('user-comment-input').value = '';
            });
        }

        function verifyJoin() {
            setTimeout(function() { window.location.href = "{{ url_for('bypass_tg') }}"; }, 2000);
        }

        {% if current_channel_id %}
        window.onload = function () {
            if (window.history && window.history.pushState) {
                window.history.pushState('forward', null, './');
                window.onpopstate = function () { window.location.href = "{{ url_for('home') }}"; };
            }
        }
        {% endif %}

        setInterval(function() {
            fetch('/api/heartbeat?ch={% if current_channel_id %}{{ current_channel_id }}{% else %}Home{% endif %}');
        }, 6000);
    </script>
</body>
</html>
"""

ADMIN_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>SPEED_X Controls Dashboard</title>
    <link href="https://fonts.googleapis.com/css2?family=Rajdhani:wght@600;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        body { background: #06060f; color: #fff; font-family: 'Rajdhani', sans-serif; padding: 25px; }
        .grid { display: grid; grid-template-columns: 1fr 1.8fr; gap: 25px; }
        .box { background: #0c0c1f; border: 1px solid #00ffcc; padding: 18px; border-radius: 10px; }
        h2 { margin-bottom: 12px; color: #00ffcc; border-bottom: 1px solid rgba(255,255,255,0.08); padding-bottom: 4px; font-size:1.2rem;}
        input, select, button { width: 100%; padding: 8px; margin-bottom: 10px; background: #13132e; border: 1px solid rgba(255,255,255,0.08); color: #fff; border-radius: 5px; font-weight: bold; font-family:'Rajdhani';}
        button { background: #ff0055; border: none; cursor: pointer; transition: 0.2s;}
        button:hover { background: #00ffcc; color: #000; box-shadow: 0 0 8px #00ffcc; }
        table { width: 100%; border-collapse: collapse; font-size:0.9rem; }
        th, td { padding: 8px; border: 1px solid rgba(255,255,255,0.04); text-align: left; }
        th { background: #12122d; color: #00ffcc; }
        .badge { background: #ff0055; padding: 2px 6px; border-radius: 4px; font-size: 0.75rem; }
    </style>
</head>
<body>
    <h1 style="color: #ff0055; margin-bottom: 15px;"><i class="fa-solid fa-terminal"></i> NIROB BBZ CONTROL INFRASTRUCTURE</h1>
    <div class="grid">
        <div>
            <div class="box" style="margin-bottom: 15px;">
                <h2>Add Streaming Node</h2>
                <form action="{{ url_for('admin_add') }}" method="POST">
                    <input type="text" name="name" placeholder="Channel Title Name" required>
                    <input type="text" name="link" placeholder="Streaming URL (M3U8 Link)" required>
                    <input type="text" name="logo" placeholder="Logo Image URL (Optional)">
                    <button type="submit"><i class="fa-solid fa-plus"></i> INJECT STREAM SERVER</button>
                </form>
            </div>
            <div class="box">
                <h2>Dynamic Site Configurations</h2>
                <form action="{{ url_for('admin_settings') }}" method="POST">
                    <label>Platform App Name</label>
                    <input type="text" name="site_name" value="{{ site_name }}" required>
                    <label>Telegram Channel Lock</label>
                    <input type="text" name="tg_channel" value="{{ tg_channel }}" required>
                    <label>Dashboard Gate Key (Password)</label>
                    <input type="password" name="admin_password" value="{{ admin_password }}" required>
                    <label>Global UI Background</label>
                    <input type="text" name="bg_url" value="{{ bg_url }}" required>
                    <label>System Switch Status</label>
                    <select name="site_status">
                        <option value="ON" {% if site_status == 'ON' %}selected{% endif %}>🟢 SYSTEM ONLINE WORKING</option>
                        <option value="OFF" {% if site_status == 'OFF' %}selected{% endif %}>🔴 SYSTEM MAINTENANCE DISABLE</option>
                    </select>
                    <button type="submit" style="background:#00ffcc; color:#000;"><i class="fa-solid fa-microchip"></i> RECORD NEW CONFIGS</button>
                </form>
                <a href="{{ url_for('logout') }}" style="color:#ff0055; text-decoration:none; font-weight:bold; display:block; text-align:center; margin-top:5px;">TERMINATE SESSION</a>
            </div>
        </div>
        <div>
            <div class="box" style="margin-bottom: 15px; background: #110d1c; border-color: #ff0055;">
                <h2><i class="fa-solid fa-users"></i> Live Watchers (<span id="user-count">{{ active_count }}</span>)</h2>
                <div style="max-height: 140px; overflow-y: auto;">
                    <table>
                        <thead><tr><th>Target Host IP</th><th>Navigation Status</th></tr></thead>
                        <tbody id="user-table-body">
                            {% for ip, data in active_users.items() %}
                            <tr><td>`{{ ip }}`</td><td><span class="badge">{{ data.channel }}</span></td></tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
            </div>
            <div class="box">
                <h2>Active Servers Operational Database</h2>
                <table>
                    <thead><tr><th>Icon</th><th>Server Designation</th><th>Operations</th></tr></thead>
                    <tbody>
                        {% for ch in channels %}
                        <tr>
                            <td>{% if ch[3] %}<img src="{{ ch[3] }}" width="24" height="24" style="border-radius:50%">{% else %}<i class="fa-solid fa-tv" style="color:#00ffcc"></i>{% endif %}</td>
                            <td><b>{{ ch[1] }}</b></td>
                            <td><a href="{{ url_for('admin_delete', id=ch[0]) }}" style="color:#ff0055; text-decoration:none;"><i class="fa-solid fa-trash-can"></i> Kill Node</a></td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
    </div>
    <script>
        setInterval(function() {
            fetch('/admin/api/users').then(res => res.json()).then(data => {
                document.getElementById('user-count').innerText = data.count;
                let tbody = document.getElementById('user-table-body'); tbody.innerHTML = '';
                for (let ip in data.users) { tbody.innerHTML += `<tr><td>\( {ip}</td><td><span class="badge"> \){data.users[ip].channel}</span></td></tr>`; }
            });
        }, 3000);
    </script>
</body>
</html>
"""

# --- ROUTING SYSTEMS LOGIC (BACKEND PROTECTION MATRIX) ---

@app.route('/')
def home():
    if get_setting('site_status') == 'OFF':
        return '''
        <body style="background:#04040c; color:#fff; font-family:sans-serif; display:flex; align-items:center; justify-content:center; height:100vh; margin:0; text-align:center;">
            <div style="border:1px dashed #ff0055; padding:40px; border-radius:12px; box-shadow:0 0 20px rgba(255,0,85,0.2); max-width:450px;">
                <i class="fas fa-tools" style="font-size:50px; color:#ff0055; margin-bottom:15px;"></i>
                <h2 style="letter-spacing:1px; margin-bottom:10px;">SYSTEM DOWNTIME ALERT</h2>
                <p style="color:#aaa; line-height:1.6;">Website is under maintenance. We will be back soon!</p>
            </div>
        </body>
        '''
    ch_id = request.args.get('ch_id')
    
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, '', logo FROM channels") # এইচটিএমএল সোর্সে এপিআই লিংক পাঠানো সম্পূর্ণ বন্ধ
    channels = cursor.fetchall()
    conn.close()
    
    current_channel_id = None
    if ch_id:
        current_channel_id = ch_id
        track_user(f"Streaming Node ID: {ch_id}")
    else:
        if session.get('tg_joined'):
            track_user("Browsing Dashboard Home")
            
    return render_template_string(
        BASE_HTML, channels=channels, current_channel_id=current_channel_id,
        site_name=get_setting('site_name'), tg_channel=get_setting('tg_channel'), bg_url=get_setting('bg_url')
    )

# ⭐ Anti-Crack API Masking Engine (Reverse Proxy Route)
# এই রুটটি ব্রাউজার থেকে আসল এপিআই লিংক লুকিয়ে ফেলে ডাটা রিভার্স করে প্লেয়ারে পাঠায়
@app.route('/stream/<int:channel_id>')
def stream_proxy(channel_id):
    if not session.get('tg_joined'):
        return "Access Denied", 403
        
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT link FROM channels WHERE id=?", (channel_id,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        return "Stream Not Found", 404
        
    actual_api_url = row[0]
    
    # পাইথন ব্যাকএন্ড নিজে আসল এপিআই কল করবে, ব্রাউজার বা ইউজার লিংক দেখতে পারবে না
    try:
        req = requests.get(actual_api_url, stream=True, timeout=5)
        return Response(req.iter_content(chunk_size=1024), content_type=req.headers.get('Content-Type'))
    except Exception as e:
        return f"Stream Initialization Error: {e}", 500

@app.route('/bypass-verification')
def bypass_tg():
    session['tg_joined'] = True
    return redirect(url_for('home'))

@app.route('/api/heartbeat')
def heartbeat():
    ch = request.args.get('ch', 'Active')
    ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    active_users[ip] = {'last_seen': time.time(), 'channel': f"Active: {ch}"}
    clean_inactive_users()
    return jsonify({"status": "synchronized"})

@app.route('/api/feedback', methods=['POST'])
def save_feedback():
    data = request.get_json()
    ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    stars = "⭐" * int(data.get('rating', 5))
    alert_msg = f"📝 *New User Reaction Report!*\n\nNode ID: {data.get('channel_id')}\nMetric: {stars}\nMessage: {data.get('msg')}\nIP: `{ip}`"
    send_telegram_alert(alert_msg)
    return jsonify({"status": "transmitted"})

# --- ADMIN GATEWAYS SECTION ---

@app.route('/admin')
def admin_dashboard():
    if not session.get('admin_logged'):
        return '''
        <body style="background:#04040a; color:#fff; font-family:sans-serif; display:flex; align-items:center; justify-content:center; height:100vh; margin:0;">
            <form action="/admin/login" method="POST" style="background:#090918; padding:30px; border-radius:10px; border:1px solid #00ffcc; width:280px; text-align:center;">
                <h3 style="color:#00ffcc; margin-bottom:15px;">SPEED_X CORE MATIX</h3>
                <input type="password" name="password" placeholder="Passphrase Entry Key" style="width:100%; padding:10px; background:#12122d; border:1px solid rgba(255,255,255,0.1); color:#fff; text-align:center;" required>
                <button type="submit" style="width:100%; padding:10px; background:#ff0055; color:#fff; margin-top:10px; font-weight:bold; cursor:pointer;">DECRYPT</button>
            </form>
        </body>
        '''
    clean_inactive_users()
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM channels")
    channels = cursor.fetchall()
    conn.close()
    
    return render_template_string(
        ADMIN_HTML, channels=channels, site_name=get_setting('site_name'),
        tg_channel=get_setting('tg_channel'), admin_password=get_setting('admin_password'),
        site_status=get_setting('site_status'), bg_url=get_setting('bg_url'),
        active_users=active_users, active_count=len(active_users)
    )

@app.route('/admin/login', methods=['POST'])
def admin_login():
    if request.form.get('password') == get_setting('admin_password'):
        session['admin_logged'] = True
        return redirect(url_for('admin_dashboard'))
    return '<script>alert("Refused!"); window.location.href="/admin";</script>'

@app.route('/admin/add', methods=['POST'])
def admin_add():
    if not session.get('admin_logged'): return redirect(url_for('admin_dashboard'))
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("INSERT INTO channels (name, link, logo) VALUES (?, ?, ?)", (request.form.get('name'), request.form.get('link'), request.form.get('logo')))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete/<int:id>')
def admin_delete(id):
    if not session.get('admin_logged'): return redirect(url_for('admin_dashboard'))
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM channels WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/settings', methods=['POST'])
def admin_settings():
    if not session.get('admin_logged'): return redirect(url_for('admin_dashboard'))
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE settings SET value=? WHERE key='site_name'", (request.form.get('site_name'),))
    cursor.execute("UPDATE settings SET value=? WHERE key='tg_channel'", (request.form.get('tg_channel'),))
    cursor.execute("UPDATE settings SET value=? WHERE key='admin_password'", (request.form.get('admin_password'),))
    cursor.execute("UPDATE settings SET value=? WHERE key='site_status'", (request.form.get('site_status'),))
    cursor.execute("UPDATE settings SET value=? WHERE key='bg_url'", (request.form.get('bg_url'),))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/api/users')
def admin_api_users():
    clean_inactive_users()
    return jsonify({"count": len(active_users), "users": active_users})

@app.route('/admin/logout')
def logout():
    session.pop('admin_logged', None)
    return redirect(url_for('admin_dashboard'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
