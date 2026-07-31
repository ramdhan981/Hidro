import json
import os
import requests
import time
import random
import sys
import re
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HUMAN_KEYWORDS = [
    "are you human", "captcha", "verify", "human verification",
    "bot detected", "please verify", "i think you're a bot",
    "prove you're human", "human check",
    "are you a real human",
    "please complete your captcha",
    "please complete the captcha",
    "complete your captcha",
    "verify that you are human",
    "banned for",
    "macros or botting",
    "please use the link",
    "complete this within",
    "result in a ban",
]

GEM_CODES = {
    "gem1": ["057","056","055","054","053","052","051"],
    "gem3": ["071","070","069","068","067","066","065"],
    "gem4": ["078","077","076","075","074","073","072"],
    "star": ["085","084","083","082","081","080","079"],
}

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
STORIES_FILE = os.path.join(SCRIPT_DIR, "stories.txt")

def load_stories():
    default_stories = [
        "It always seems impossible until it's done.",
        "Don't count the days, make the days count.",
    ]
    try:
        with open(STORIES_FILE, "r", encoding="utf-8") as f:
            lines = [l.strip() for l in f if l.strip()]
        if lines:
            return lines
    except FileNotFoundError:
        pass
    return default_stories

stories = load_stories()

SETTINGS_FILE = os.path.join(SCRIPT_DIR, "settings.txt")

def load_settings():
    defaults = {
        "PREFIX": "owo",
        "JEDA_MIN": "12",
        "JEDA_MAX": "16",
        "LONG_BREAK_TRIGGER": "200",
        "LONG_BREAK_MIN": "10",
        "LONG_BREAK_MAX": "17",
    }
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                key = key.strip().upper()
                val = val.strip()
                if key in defaults and val:
                    defaults[key] = val
    except FileNotFoundError:
        pass
    return defaults

SETTINGS = load_settings()
PREFIX = SETTINGS["PREFIX"]
JEDA_MIN = float(SETTINGS["JEDA_MIN"])
JEDA_MAX = float(SETTINGS["JEDA_MAX"])
LONG_BREAK_TRIGGER = int(SETTINGS["LONG_BREAK_TRIGGER"])
LONG_BREAK_MIN = float(SETTINGS["LONG_BREAK_MIN"])
LONG_BREAK_MAX = float(SETTINGS["LONG_BREAK_MAX"])

# ============================================================
# Dashboard terminal (status board ringkas, terpisah dari webhook)
# ============================================================
dashboard_lock = threading.Lock()
all_accounts_state = {}
shutdown_event = threading.Event()
panel_server = None

CONFIG_PATH = os.path.join(SCRIPT_DIR, "config.txt")
if not os.path.exists(CONFIG_PATH):
    CONFIG_PATH = os.path.join(os.path.expanduser("~"), "owobot", "config.txt")


def build_status_payload():
    with dashboard_lock:
        items = sorted(all_accounts_state.items())

    accounts = []
    for acc_id, info in items:
        state = info["state"]
        elapsed = str(datetime.now() - state["start_time"]).split(".")[0]
        gem_text = ", ".join(
            f"{g}:{v}" for g, v in state["gem_counter_state"].items()
        ) or "Belum terdeteksi"
        accounts.append({
            "id": acc_id,
            "label": info["label"],
            "profile_name": info["profile_name"],
            "status": state["pause_status"],
            "grand_total": state["grand_total"],
            "hunt_count": state["hunt_count"],
            "battle_count": state["battle_count"],
            "runtime": elapsed,
            "gems": gem_text,
            "vote": state["vote_status"],
            "pray": state["pray_status"],
            "daily": state["daily_status"],
            "logs": state["action_log"][-4:] or ["Belum ada aksi..."],
        })

    return {
        "running": not shutdown_event.is_set(),
        "timestamp": datetime.now().strftime("%H:%M:%S"),
        "accounts": accounts,
    }


class OwoStatusHandler(BaseHTTPRequestHandler):
    def _send(self, payload, status=200, content_type="application/json"):
        body = payload.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/api/status":
            self._send(json.dumps(build_status_payload()))
            return

        if self.path == "/":
            html = """
            <!doctype html>
            <html lang=\"id\">
            <head>
              <meta charset=\"utf-8\">
              <meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">
              <title>OWO Bot Status</title>
              <style>
                body { font-family: Arial, sans-serif; margin: 0; background: #0f172a; color: #f8fafc; }
                .wrap { max-width: 1200px; margin: 0 auto; padding: 24px; }
                .card { background: #111827; border: 1px solid #334155; border-radius: 12px; padding: 16px; margin-bottom: 16px; }
                .top { display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap; }
                .btn { background: #2563eb; color: white; border: none; border-radius: 8px; padding: 8px 12px; cursor: pointer; margin: 4px; font-size: 0.9em; }
                .btn.secondary { background: #475569; }
                .btn.danger { background: #dc2626; }
                .btn.small { padding: 6px 10px; font-size: 0.8em; }
                .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; }
                .small { color: #94a3b8; font-size: 0.92em; }
                pre { background: #020617; padding: 10px; border-radius: 8px; overflow-x: auto; white-space: pre-wrap; }
                .status-ok { color: #4ade80; }
                .status-warn { color: #fbbf24; }
                .btn-group { display: flex; gap: 4px; flex-wrap: wrap; }
                .acc-summary { padding: 8px; background: #1e293b; border-radius: 8px; margin-bottom: 8px; }
              </style>
            </head>
            <body>
              <div class=\"wrap\">
                <div class=\"card\">
                  <div class=\"top\">
                    <div>
                      <h2 style=\"margin:0\">OWO Bot Status Panel</h2>
                      <div class=\"small\">Private local panel — only accessible on this computer via localhost</div>
                    </div>
                    <div>
                      <button class=\"btn secondary\" onclick=\"sendCommand('pause', null)\">⏸️ Pause Semua</button>
                      <button class=\"btn\" onclick=\"sendCommand('resume', null)\">▶️ Resume Semua</button>
                      <button class=\"btn danger\" onclick=\"sendCommand('stop', null)\">⛔ Stop Semua</button>
                    </div>
                  </div>
                </div>
                <div class=\"card\">
                  <h3 style=\"margin-top:0\">Status Bot</h3>
                  <div id=\"summary\">Memuat...</div>
                </div>
                <div id=\"accounts\"></div>
              </div>
              <script>
                function escapeHtml(value) {
                  return String(value)
                    .replace(/&/g, '&amp;')
                    .replace(/</g, '&lt;')
                    .replace(/>/g, '&gt;')
                    .replace(/\"/g, '&quot;');
                }
                async function loadStatus() {
                  try {
                    const res = await fetch('/api/status');
                    const data = await res.json();
                    const summary = document.getElementById('summary');
                    summary.innerHTML = '<strong>Status:</strong> ' + (data.running ? '<span class=\"status-ok\">Berjalan</span>' : '<span class=\"status-warn\">Dihentikan</span>') + ' <span class=\"small\">• Total Akun: ' + data.accounts.length + ' • Terakhir diperbarui ' + data.timestamp + '</span>';
                    const accounts = document.getElementById('accounts');
                    if (!data.accounts.length) {
                      accounts.innerHTML = '<div class=\"card\"><strong>Belum ada akun aktif.</strong></div>';
                      return;
                    }
                    accounts.innerHTML = data.accounts.map(acc => `
                      <div class=\"card\">
                        <div style=\"display: flex; justify-content: space-between; align-items: start; gap: 12px;\">
                          <div style=\"flex: 1;\">
                            <h4 style=\"margin-top:0;margin-bottom:8px\">${escapeHtml(acc.label)} — ${escapeHtml(acc.profile_name)}</h4>
                            <div class=\"grid\">
                              <div><strong>Status</strong><br>${escapeHtml(acc.status)}</div>
                              <div><strong>H+B</strong><br>${escapeHtml(acc.grand_total)}</div>
                              <div><strong>Hunt</strong><br>${escapeHtml(acc.hunt_count)}</div>
                              <div><strong>Battle</strong><br>${escapeHtml(acc.battle_count)}</div>
                            </div>
                            <div class=\"small\" style=\"margin-top:8px\">Runtime: ${escapeHtml(acc.runtime)}</div>
                            <div class=\"small\">Gem: ${escapeHtml(acc.gems)}</div>
                            <div class=\"small\">Vote: ${escapeHtml(acc.vote)}</div>
                            <div class=\"small\">Pray: ${escapeHtml(acc.pray)}</div>
                            <div class=\"small\">Daily: ${escapeHtml(acc.daily)}</div>
                            <pre>${escapeHtml(acc.logs.join('\\n'))}</pre>
                          </div>
                          <div style=\"min-width: 120px;\">
                            <div class=\"btn-group\" style=\"flex-direction: column;\">
                              <button class=\"btn secondary btn-small\" onclick=\"sendCommand('pause', ${acc.id})\">⏸️ Pause</button>
                              <button class=\"btn btn-small\" onclick=\"sendCommand('resume', ${acc.id})\">▶️ Resume</button>
                              <button class=\"btn danger btn-small\" onclick=\"sendCommand('stop', ${acc.id})\">⛔ Stop</button>
                            </div>
                          </div>
                        </div>
                      </div>
                    `).join('');
                  } catch (err) {
                    document.getElementById('summary').innerHTML = '<span class=\"status-warn\">Gagal memuat status. Coba refresh.</span>';
                    console.error(err);
                  }
                }
                async function sendCommand(action, accId) {
                  try {
                    const payload = {action: action};
                    if (accId !== null) payload.acc_id = accId;
                    await fetch('/api/command', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload)});
                    await loadStatus();
                  } catch (err) {
                    console.error(err);
                  }
                }
                setInterval(loadStatus, 2000);
                loadStatus();
              </script>
            </body>
            </html>
            """
            self._send(html, content_type="text/html; charset=utf-8")
            return

        self._send("Not found", status=404, content_type="text/plain; charset=utf-8")

    def do_POST(self):
        if self.path == "/api/command":
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length).decode("utf-8", "ignore")
            try:
                data = json.loads(body) if body else {}
            except Exception:
                data = {}

            action = (data.get("action") or "").lower()
            acc_id = data.get("acc_id")  # Akun ID untuk kontrol per akun

            if action == "pause":
                with dashboard_lock:
                    if acc_id:
                        # Pause satu akun
                        if acc_id in all_accounts_state:
                            st = all_accounts_state[acc_id]["state"]
                            st["is_paused"] = True
                            st["pause_status"] = "⏸️ Pause"
                            st["embed_color"] = 0xFF0000
                    else:
                        # Pause semua akun
                        for info in all_accounts_state.values():
                            st = info["state"]
                            st["is_paused"] = True
                            st["pause_status"] = "⏸️ Pause"
                            st["embed_color"] = 0xFF0000
            elif action == "resume":
                with dashboard_lock:
                    if acc_id:
                        # Resume satu akun
                        if acc_id in all_accounts_state:
                            st = all_accounts_state[acc_id]["state"]
                            st["is_paused"] = False
                            st["pause_status"] = "🟢 Aktif"
                            st["embed_color"] = 0x57F287
                    else:
                        # Resume semua akun
                        for info in all_accounts_state.values():
                            st = info["state"]
                            st["is_paused"] = False
                            st["pause_status"] = "🟢 Aktif"
                            st["embed_color"] = 0x57F287
            elif action == "stop":
                if acc_id:
                    # Stop satu akun (tandai untuk dihentikan)
                    with dashboard_lock:
                        if acc_id in all_accounts_state:
                            st = all_accounts_state[acc_id]["state"]
                            st["is_paused"] = True
                            st["pause_status"] = "⛔ Bot telah dihentikan"
                            st["embed_color"] = 0xFF0000
                else:
                    # Stop semua
                    with dashboard_lock:
                        for info in all_accounts_state.values():
                            st = info["state"]
                            st["pause_status"] = "⛔ Bot telah dihentikan"
                            st["embed_color"] = 0xFF0000
                    shutdown_event.set()

            self._send(json.dumps({"ok": True, "action": action, "acc_id": acc_id}))
            return

        self._send("Bad request", status=400, content_type="text/plain; charset=utf-8")

    def log_message(self, format, *args):
        return


def start_web_panel(port=8765):
    global panel_server
    try:
        panel_server = ThreadingHTTPServer(("0.0.0.0", port), OwoStatusHandler)
        panel_server.daemon_threads = True
        thread = threading.Thread(target=panel_server.serve_forever, daemon=True)
        thread.start()
        print(f"[WEB] Panel status siap di http://0.0.0.0:{port}/")
        print(f"[WEB] Buka lewat IP lokal Anda, misalnya http://<IP-TERMUX>:{port}/")
        return True
    except OSError as exc:
        print(f"[WEB] Gagal start panel status: {exc}")
        return False


def render_dashboard():
    lines = []
    lines.append("=" * 58)
    lines.append(f"   OWO BOT - DASHBOARD   ({datetime.now().strftime('%H:%M:%S')})")
    lines.append("=" * 58)

    with dashboard_lock:
        items = sorted(all_accounts_state.items())

    if not items:
        lines.append("  Menunggu akun aktif...")

    for acc_id, info in items:
        state = info["state"]
        profile_name = info["profile_name"]
        label = info["label"]
        elapsed = str(datetime.now() - state["start_time"]).split(".")[0]

        gem_text = ", ".join(
            f"{g}:{v}" for g, v in state["gem_counter_state"].items()
        ) or "Belum terdeteksi"

        lines.append(f"\n{label} {profile_name}")
        lines.append(f"  Status     : {state['pause_status']}")
        lines.append(
            f"  Total H+B  : {state['grand_total']}   "
            f"Hunt: {state['hunt_count']}   Battle: {state['battle_count']}"
        )
        lines.append(f"  Runtime    : {elapsed}")
        lines.append(f"  Gem        : {gem_text}")
        lines.append(f"  Vote       : {state['vote_status']}")
        lines.append(f"  Pray       : {state['pray_status']}")
        lines.append(f"  Daily      : {state['daily_status']}")

        log_lines = state["action_log"][-3:] or ["Belum ada aksi..."]
        lines.append("  Log Terbaru:")
        for l in log_lines:
            lines.append(f"    {l}")

        lines.append("-" * 58)

    return "\n".join(lines)


def dashboard_loop():
    # Hanya tampilkan dashboard kalau dijalankan langsung di terminal
    # (kalau output diarahkan ke bot.log via nohup, dilewati biar log tidak penuh escape code)
    if not sys.stdout.isatty():
        return
    while True:
        try:
            output = render_dashboard()
            sys.stdout.write("\033[2J\033[H")  # clear screen + cursor ke atas
            sys.stdout.write(output + "\n")
            sys.stdout.flush()
        except Exception:
            pass
        time.sleep(2)


def command_loop():
    # Hanya baca input kalau memang ada terminal interaktif
    if not sys.stdin.isatty():
        return
    for raw in sys.stdin:
        cmd = raw.strip().lower()
        if cmd in (".stopbot", "stop"):
            with dashboard_lock:
                for info in all_accounts_state.values():
                    st = info["state"]
                    if not st["is_paused"]:
                        st["is_paused"] = True
                        st["pause_status"] = "🔴 PAUSED (terminal)"
                        st["embed_color"] = 0xFF0000
            print("[CMD] Semua akun di-pause. Ketik .startbot untuk lanjut, exit untuk keluar.")
        elif cmd in (".startbot", "start"):
            with dashboard_lock:
                for info in all_accounts_state.values():
                    st = info["state"]
                    st["is_paused"] = False
                    st["pause_status"] = "🟢 Aktif"
                    st["embed_color"] = 0x57F287
            print("[CMD] Semua akun dilanjutkan.")
        elif cmd in ("exit", "quit", ".exit", ".quit"):
            print("[CMD] Menghentikan semua akun...")
            shutdown_event.set()
            break


def jalankan_bot(acc_id, TOKEN, CHANNEL_ID, WEBHOOK_URL, PING_USER_ID):

    URL = f"https://discord.com/api/v10/channels/{CHANNEL_ID}/messages"
    headers = {"Authorization": TOKEN, "Content-Type": "application/json"}

    state = {
        "counter": 0,
        "total_actions": 0,
        "grand_total": 0,
        "hunt_count": 0,
        "battle_count": 0,
        "start_time": datetime.now(),
        "action_log": [],
        "gem_counter_state": {},
        "gems_need": list(GEM_CODES.keys()),
        "gems_use": "",
        "is_paused": False,
        "last_vote_time": None,
        "vote_status": "Belum dicek",
        "last_pray_time": None,
        "pray_status": "Belum dicek",
        "daily_done": False,
        "daily_status": "Belum dicek",
        "pause_status": "🟢 Aktif",
        "pause_seconds": 0,
        "embed_color": 0x57F287,
        "webhook_msg_url": None,
    }

    label = f"[AKUN-{acc_id}]"

    profile_name = f"Akun #{acc_id}"
    token_valid = False
    token_error_reason = ""
    try:
        resp = requests.get("https://discord.com/api/v10/users/@me", headers={"Authorization": TOKEN}, timeout=10)
        if resp.status_code == 200:
            user_data = resp.json()
            profile_name = f"{user_data.get('username', 'Unknown')}#{user_data.get('discriminator', '0000')} (Akun {acc_id})"
            token_valid = True
        elif resp.status_code == 401:
            token_error_reason = "Token tidak valid / salah (401 Unauthorized)"
        else:
            token_error_reason = f"Gagal verifikasi token (HTTP {resp.status_code})"
    except Exception as e:
        token_error_reason = f"Tidak bisa menghubungi Discord: {e}"

    if not token_valid:
        state["pause_status"] = "❌ TOKEN SALAH"
        with dashboard_lock:
            all_accounts_state[acc_id] = {
                "state": state,
                "profile_name": f"Akun #{acc_id} (TOKEN SALAH)",
                "label": label,
            }
        print("")
        print("=" * 58)
        print(f"❌ {label} TOKEN SALAH — akun ini TIDAK dijalankan!")
        print(f"   Alasan  : {token_error_reason}")
        print(f"   Cek ulang token di config.txt untuk akun {acc_id}.")
        print("=" * 58)
        print("")
        return

    with dashboard_lock:
        all_accounts_state[acc_id] = {
            "state": state,
            "profile_name": profile_name,
            "label": label,
        }

    def safe_request(method, url, max_wait=600, **kwargs):
        kwargs.setdefault("timeout", 15)
        attempt = 0
        while True:
            try:
                resp = requests.request(method, url, **kwargs)
                if attempt > 0:
                    log("✅ Sinyal kembali! Lanjut...")
                    state["pause_status"] = "🟢 Aktif"
                return resp
            except Exception:
                attempt += 1
                wait = min(30, 5 * attempt)
                state["pause_status"] = f"📵 No signal (retry #{attempt})"
                time.sleep(wait)
                if attempt * wait >= max_wait:
                    log("⚠️ Koneksi gagal terlalu lama, skip request ini")
                    return None

    def log(msg):
        entry = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
        state["action_log"].append(entry)
        if len(state["action_log"]) > 6:
            state["action_log"].pop(0)

    def build_embed():
        elapsed = str(datetime.now() - state["start_time"]).split(".")[0]
        log_text = "".join(f"{l}\n" for l in state["action_log"]) or "Belum ada aksi..."
        gem_text = ""
        for g, v in state["gem_counter_state"].items():
            gem_text += f"{g[:14].ljust(14)}: {v}\n"
        gem_text = gem_text or "Belum terdeteksi"

        next_check = 20 - (state["grand_total"] % 20)
        if state["grand_total"] % 20 == 0 and state["grand_total"] > 0:
            next_check = 20

        return {
            "title": f"🤖 OWO BOT — {profile_name}",
            "color": state["embed_color"],
            "description": f"**🆔 Akun:** `{label}`\n**👤 Profil:** {profile_name}",
            "fields": [
                {"name": "📊 Statistik", "value": (
                    f"```\nTotal H+B  : {state['grand_total']}\n"
                    f"Hunt       : {state['hunt_count']}\n"
                    f"Battle     : {state['battle_count']}\n"
                    f"Runtime    : {elapsed}\n"
                    f"Next Check : {next_check} H+B lagi\n```"
                ), "inline": False},
                {"name": "⏱️ Status", "value": (
                    f"```\nStatus : {state['pause_status']}\n```"
                ), "inline": False},
                {"name": "💎 Gem Status", "value": f"```\n{gem_text}```", "inline": False},
                {"name": "🗳️ Vote", "value": f"```\n{state['vote_status']}\n```", "inline": False},
                {"name": "🙏 Pray", "value": f"```\n{state['pray_status']}\n```", "inline": False},
                {"name": "📅 Daily", "value": f"```\n{state['daily_status']}\n```", "inline": False},
                {"name": "📋 Log Terbaru", "value": f"```\n{log_text}```", "inline": False},
            ],
            "footer": {"text": f"🕒 {datetime.now().strftime('%H:%M:%S')} • {label}"}
        }

    def send_webhook():
        try:
            embed = build_embed()
            if state["webhook_msg_url"] is None:
                resp = safe_request("POST", WEBHOOK_URL + "?wait=true", json={"embeds": [embed]})
                if resp and resp.status_code in (200, 201):
                    data = resp.json()
                    msg_id = data.get("id")
                    parts = WEBHOOK_URL.rstrip("/").split("/")
                    wh_id, wh_token = parts[-2], parts[-1]
                    state["webhook_msg_url"] = f"https://discord.com/api/v10/webhooks/{wh_id}/{wh_token}/messages/{msg_id}"
            else:
                safe_request("PATCH", state["webhook_msg_url"], json={"embeds": [embed]})
        except Exception:
            pass

    def send_alert(msg_content, is_test=False):
        try:
            if is_test:
                title = "🧪 TES ALERT (.testalert)"
                desc_intro = f"**{label} - {profile_name}** — ini PERCOBAAN, bot TIDAK dihentikan.\n\n"
                content_text = f"<@{PING_USER_ID}> @everyone 🧪 **{label} - {profile_name} TES ALERT — abaikan jika ini disengaja**"
                next_steps = (
                    f"**ℹ️ Catatan:**\n"
                    f"Ini hanya tes notifikasi dari command `.testalert`.\n"
                    f"Kalau ping <@USER_ID> dan @everyone masuk, sistem alert berjalan normal."
                )
            else:
                title = "🚨 CAPTCHA / BAN DETECTED!"
                desc_intro = f"**{label} - {profile_name}** dihentikan otomatis!\n\n"
                content_text = f"<@{PING_USER_ID}> @everyone 🚨 **{label} - {profile_name} KENA CAPTCHA! BOT DIHENTIKAN!**"
                next_steps = (
                    f"**✅ Langkah selanjutnya:**\n"
                    f"1. Selesaikan captcha di Discord\n"
                    f"2. Ketik `.startbot` di channel ini, ATAU\n"
                    f"3. Tekan tombol ▶️ Resume di panel web (`owoweb`)"
                )

            embed = {
                "title": title,
                "description": (
                    desc_intro +
                    f"**📩 Pesan OWO:**\n```{msg_content[:200]}```\n"
                    f"**📊 Total H/B:** `{state['grand_total']}`\n"
                    f"**⏱️ Waktu:** `{datetime.now().strftime('%H:%M:%S')}`\n\n"
                    f"{next_steps}"
                ),
                "color": 0xFF0000,
                "footer": {"text": f"{label} - Segera cek akun!"}
            }
            safe_request("POST", WEBHOOK_URL, json={
                "content": content_text,
                "embeds": [embed],
                "allowed_mentions": {"parse": ["everyone", "users"]}
            })
        except Exception:
            pass

    def get_last_msg_id():
        try:
            r = safe_request("GET", f"{URL}?limit=1", headers=headers, timeout=10)
            if r and r.status_code == 200 and r.json():
                return r.json()[0].get("id", "0")
        except Exception:
            pass
        return "0"

    def get_owo_response(before_id, timeout=5):
        try:
            deadline = time.time() + timeout
            while time.time() < deadline:
                r = safe_request("GET", f"{URL}?limit=8", headers=headers, timeout=10)
                if r and r.status_code == 200:
                    for msg in r.json():
                        if msg.get("id", "0") <= before_id:
                            continue
                        author = msg.get("author", {})
                        if author.get("bot") and "owo" in author.get("username", "").lower():
                            text = msg.get("content", "")
                            for emb in msg.get("embeds", []):
                                text += " " + emb.get("description", "")
                                text += " " + emb.get("title", "")
                                for f in emb.get("fields", []):
                                    text += " " + f.get("value", "")
                            return text
                time.sleep(1)
        except Exception:
            pass
        return ""

    def check_human():
        import unicodedata as _ud
        try:
            r = safe_request("GET", f"{URL}?limit=10", headers=headers, timeout=10)
            if r and r.status_code == 200:
                for msg in r.json():
                    msg_content = msg.get("content", "")
                    if not msg_content:
                        continue
                    msg_clean = _ud.normalize("NFKC", msg_content)
                    msg_clean = re.sub(r'[\u200B-\u200D\uFEFF]', '', msg_clean)
                    msg_lower = msg_clean.lower()

                    if "captcha" in msg_lower and "verify" in msg_lower:
                        warning_pattern = r'[\(\[\{]?\s*(\d+)\s*[\/／]\s*5\s*[\)\]\}]?'
                        match = re.search(warning_pattern, msg_lower)
                        if match:
                            if int(match.group(1)) >= 1:
                                return True, msg_content

                    if "are you a real human" in msg_lower and "please use the link" in msg_lower:
                        return True, msg_content

                    if "please complete this within" in msg_lower and "result in a ban" in msg_lower:
                        return True, msg_content

                    if "please complete your captcha" in msg_lower and "verify that you are human" in msg_lower:
                        return True, msg_content

                    if "banned for" in msg_lower or "macros or botting" in msg_lower:
                        return True, msg_content

                    for kw in HUMAN_KEYWORDS:
                        if kw in msg_lower:
                            return True, msg_content
        except Exception:
            pass
        return False, ""

    def check_discord_cmd():
        try:
            r = safe_request("GET", f"{URL}?limit=5", headers=headers, timeout=10)
            if r and r.status_code == 200:
                for msg in r.json():
                    text = msg.get("content", "").strip().lower()
                    uid = msg.get("author", {}).get("id", "")
                    if uid == PING_USER_ID:
                        if text == ".stopbot": return "stop"
                        if text == ".startbot": return "start"
                        if text == ".testalert": return "testalert"
        except Exception:
            pass
        return None

    def get_inventory_and_equip(force=False):
        if not state["gems_need"] and not force:
            return
        if force:
            for gem in GEM_CODES.keys():
                if gem not in state["gems_need"]:
                    state["gems_need"].append(gem)

        before_id = get_last_msg_id()
        time.sleep(random.uniform(1, 2))
        safe_request("POST", URL, json={"content": f"{PREFIX} inv"}, headers=headers)

        inv_text = ""
        deadline = time.time() + 10
        while time.time() < deadline:
            time.sleep(1)
            try:
                r = safe_request("GET", f"{URL}?limit=5", headers=headers, timeout=10)
                if r and r.status_code == 200:
                    for msg in r.json():
                        if msg.get("id", "0") <= before_id:
                            continue
                        author = msg.get("author", {})
                        if not (author.get("bot") and "owo" in author.get("username", "").lower()):
                            continue
                        text = msg.get("content", "")
                        if "inventory" in text.lower() or "=" in text:
                            inv_text = text
                            break
                    if inv_text:
                        break
            except Exception:
                pass

        if not inv_text:
            log("⚠️ Inv: OWO tidak balas")
            send_webhook()
            return

        values = re.findall(r"`([^`]+)`", inv_text)
        if not values:
            values = re.findall(r"\b(0[5-8][0-9])\b", inv_text)
        if not values:
            log("⚠️ Inv: Format tidak dikenali")
            send_webhook()
            return

        state["gems_use"] = ""
        for gem in list(state["gems_need"]):
            if gem not in GEM_CODES:
                continue
            for code in GEM_CODES[gem]:
                if code in values:
                    item_num = str(int(code))
                    state["gems_use"] += f"{item_num} "
                    state["gem_counter_state"][gem] = f"🔄 {item_num}"
                    break

        if state["gems_use"].strip():
            time.sleep(random.uniform(1, 2))
            cmd = f"{PREFIX} use {state['gems_use'].strip()}"
            safe_request("POST", URL, json={"content": cmd}, headers=headers)
            log(f"💎 {cmd}")
            time.sleep(3)
            state["gems_need"] = []
            state["gems_use"] = ""
            for gem in GEM_CODES.keys():
                if gem in state["gem_counter_state"] and "🔄" in str(state["gem_counter_state"][gem]):
                    state["gem_counter_state"][gem] = "✅ equipped"
        else:
            log("⚠️ Tidak ada gem di inventory!")

        send_webhook()

    def check_gem_expiry(hunt_response):
        if not hunt_response or len(hunt_response.strip()) < 10:
            return
        matches = re.findall(r"\[(\d+)/(\d+)\]", hunt_response)
        current_count = len(matches)
        gem_keys = list(GEM_CODES.keys())
        for i, match in enumerate(matches):
            cur, total = int(match[0]), int(match[1])
            pct = int((cur / total) * 100) if total > 0 else 0
            if i < len(gem_keys):
                state["gem_counter_state"][gem_keys[i]] = f"🟢 {cur}/{total} ({pct}%)"
        prev = state.get("last_active_gem_count", None)
        state["last_active_gem_count"] = current_count
        if prev is None:
            return
        if current_count < prev:
            expired_count = prev - current_count
            for gem in list(GEM_CODES.keys()):
                if gem not in state["gems_need"]:
                    state["gems_need"].append(gem)
                    state["gem_counter_state"][gem] = "❌ habis"
            log(f"💎 {expired_count} gem habis! Equip ulang...")
            send_webhook()
            get_inventory_and_equip(force=False)

    def auto_pray():
        if state["last_pray_time"] is not None:
            if (datetime.now() - state["last_pray_time"]).total_seconds() < 302:
                return
        before_id = get_last_msg_id()
        time.sleep(random.uniform(0.5, 1))
        safe_request("POST", URL, json={"content": f"{PREFIX} pray"}, headers=headers)
        state["last_pray_time"] = datetime.now()
        time.sleep(2)
        resp = get_owo_response(before_id, timeout=5)
        ts = datetime.now().strftime("%H:%M:%S")
        if resp and any(k in resp.lower() for k in ["prayed", "pray", "blessed", "bless"]):
            state["pray_status"] = f"✅ Selesai ({ts})"
            log("🙏 Pray: Berhasil")
        else:
            state["pray_status"] = f"Dicek ({ts})"
            log("🙏 Pray: Dicek")
        send_webhook()
        time.sleep(1)

    def auto_vote():
        if state["last_vote_time"] is not None:
            if (datetime.now() - state["last_vote_time"]).total_seconds() < 43200:
                return
        before_id = get_last_msg_id()
        time.sleep(random.uniform(1, 2))
        safe_request("POST", URL, json={"content": f"{PREFIX} vote"}, headers=headers)
        time.sleep(3)
        resp = get_owo_response(before_id, timeout=6)
        state["last_vote_time"] = datetime.now()
        ts = datetime.now().strftime("%H:%M:%S")
        if resp and any(k in resp.lower() for k in ["you can vote", "vote now", "ready", "available"]):
            state["vote_status"] = f"✅ Siap vote! ({ts})"
            log("🗳️ Vote: Siap vote!")
        elif resp and any(k in resp.lower() for k in ["already voted", "come back", "voted"]):
            state["vote_status"] = f"⏳ Sudah vote ({ts})"
            log("🗳️ Vote: Sudah vote")
        else:
            state["vote_status"] = f"Dicek ({ts})"
            log("🗳️ Vote: Dicek")
        send_webhook()
        time.sleep(2)

    def auto_daily():
        if state["daily_done"]:
            return
        before_id = get_last_msg_id()
        time.sleep(random.uniform(1, 2))
        safe_request("POST", URL, json={"content": f"{PREFIX} daily"}, headers=headers)
        time.sleep(3)
        resp = get_owo_response(before_id, timeout=6)
        state["daily_done"] = True
        ts = datetime.now().strftime("%H:%M:%S")
        if resp and any(k in resp.lower() for k in ["daily", "streak", "reward", "claimed"]):
            state["daily_status"] = f"✅ Diklaim ({ts})"
            log("📅 Daily: Diklaim")
        else:
            state["daily_status"] = f"Dicek ({ts})"
            log("📅 Daily: Dicek")
        send_webhook()
        time.sleep(2)

    def system_pause(seconds, label_text="Waiting", send_story=False, show_status=True):
        remaining = int(seconds)
        total_secs = remaining
        if show_status:
            state["pause_status"] = f"⏸️ {label_text}"
        while remaining > 0:
            if shutdown_event.is_set():
                return
            state["pause_seconds"] = remaining
            elapsed = total_secs - remaining
            if send_story and elapsed > 0 and elapsed % 60 == 0:
                try:
                    safe_request("POST", URL, json={"content": random.choice(stories)}, headers=headers)
                except Exception:
                    pass
            if remaining % 10 == 0:
                send_webhook()
                detected, tmsg = check_human()
                if detected:
                    send_alert(tmsg)
                    sys.exit()
            time.sleep(1)
            remaining -= 1
        state["pause_status"] = "🟢 Aktif"
        state["pause_seconds"] = 0

    # ========================================================
    print(f"{label} ({profile_name}) Mulai berjalan...")
    get_inventory_and_equip()
    auto_daily()

    try:
        while not shutdown_event.is_set():
            detected, tmsg = check_human()
            if detected:
                send_alert(tmsg)
                state["is_paused"] = True
                state["pause_status"] = "🚨 CAPTCHA - Verifikasi manual dulu!"
                state["embed_color"] = 0xFF0000
                send_webhook()
                while state["is_paused"] and not shutdown_event.is_set():
                    time.sleep(5)
                    send_webhook()
                    if check_discord_cmd() == "start":
                        state["is_paused"] = False
                        state["pause_status"] = "🟢 Aktif"
                        state["embed_color"] = 0x57F287
                        safe_request("POST", URL, json={"content": "▶️ Bot dilanjutkan setelah verifikasi captcha!"}, headers=headers)
                        send_webhook()
                        break
                if shutdown_event.is_set():
                    break
                continue

            cmd = check_discord_cmd()
            if cmd == "stop" and not state["is_paused"]:
                state["is_paused"] = True
                state["pause_status"] = "🔴 PAUSED"
                state["embed_color"] = 0xFF0000
                safe_request("POST", URL, json={"content": "⏸️ Bot di-pause! Ketik `.startbot` untuk lanjut."}, headers=headers)
                send_webhook()

            if cmd == "testalert":
                log("🧪 .testalert diterima — mengirim alert percobaan...")
                send_alert(
                    "[TES] Ini adalah pesan percobaan dari .testalert — "
                    "bukan captcha asli. Bot TIDAK dihentikan.",
                    is_test=True
                )
                safe_request("POST", URL, json={
                    "content": "🧪 Alert percobaan terkirim ke webhook! Cek apakah ping <@USER> dan @everyone masuk."
                }, headers=headers)

            while state["is_paused"] and not shutdown_event.is_set():
                time.sleep(5)
                send_webhook()
                if check_discord_cmd() == "start":
                    state["is_paused"] = False
                    state["pause_status"] = "🟢 Aktif"
                    state["embed_color"] = 0x57F287
                    safe_request("POST", URL, json={"content": "▶️ Bot dilanjutkan!"}, headers=headers)
                    send_webhook()
                    break

            if shutdown_event.is_set():
                break

            before_id = get_last_msg_id()

            safe_request("POST", URL, json={"content": f"{PREFIX} hunt"}, headers=headers)
            time.sleep(random.uniform(0.5, 1))
            safe_request("POST", URL, json={"content": f"{PREFIX} battle"}, headers=headers)

            state["hunt_count"] += 1
            state["battle_count"] += 1
            state["grand_total"] += 2
            state["total_actions"] = state.get("total_actions", 0) + 2
            state["counter"] += 1

            log(f"✅ H+B #{state['grand_total']}")
            time.sleep(1)

            hunt_resp = get_owo_response(before_id, timeout=4)
            if hunt_resp:
                check_gem_expiry(hunt_resp)

            try:
                safe_request("POST", URL, json={"content": random.choice(stories)}, headers=headers)
            except Exception:
                pass

            send_webhook()

            if state.get("total_actions", 0) >= LONG_BREAK_TRIGGER:
                break_minutes = round(random.uniform(LONG_BREAK_MIN, LONG_BREAK_MAX), 1)
                break_secs = int(break_minutes * 60)
                log(f"☕ Long Break ({break_minutes} menit)...")
                send_webhook()
                system_pause(break_secs, "LONG BREAK", send_story=False)
                state["total_actions"] = 0
            else:
                pause_secs = round(random.uniform(JEDA_MIN, JEDA_MAX), 1)
                system_pause(pause_secs, "Jeda H+B", show_status=False)

            if state["grand_total"] % 20 == 0 and state["grand_total"] > 0:
                log("🎒 Cek inventory rutin (setiap 20 H+B)...")
                send_webhook()
                state["gems_need"] = list(GEM_CODES.keys())
                get_inventory_and_equip(force=True)
                system_pause(random.randint(5, 8), "Jeda Inventory", show_status=False)

            auto_pray()
            auto_vote()

        if shutdown_event.is_set():
            state["pause_status"] = "⛔ Bot telah dihentikan"
            state["embed_color"] = 0xFF0000
            send_webhook()
            print(f"\n{label} Dihentikan (perintah exit/CTRL+C).")

    except KeyboardInterrupt:
        state["pause_status"] = "⛔ Bot telah dihentikan"
        state["embed_color"] = 0xFF0000
        send_webhook()
        print(f"\n{label} Dihentikan.")
    except Exception as e:
        print(f"\n{label} Error: {e}")


# ============================================================
# Fungsi untuk membaca config.txt
# ============================================================
def load_config():
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            lines = [l.strip() for l in f.read().splitlines() if l.strip()]
        return lines
    except Exception:
        return []


# ============================================================
# Fungsi untuk menu konfigurasi interaktif
# ============================================================
def interactive_config():
    print("\n" + "=" * 58)
    print("   OWO BOT - KONFIGURASI AKUN")
    print("=" * 58)
    print("Isi data akun Discord Anda (maksimal 6 akun)")
    print("⚠️ AKUN 1 WAJIB DIISI LENGKAP! Jika ingin skip, tekan Ctrl+C.\n")

    accounts = []
    
    for i in range(1, 7):
        print(f"\n{'='*58}")
        if i == 1:
            print(f"--- AKUN {i} (WAJIB) ---")
        else:
            print(f"--- AKUN {i} (OPSIONAL) ---")
        print(f"{'='*58}")

        token = input(f"  [{i}] Token Discord: ").strip()
        if not token:
            if i == 1:
                print("  ❌ AKUN 1: TOKEN HARUS DIISI! Setup dibatalkan.")
                return None
            else:
                print("  ⏭️  Akun ini dilewati (token kosong).")
                break

        channel = input(f"  [{i}] Channel ID: ").strip()
        webhook = input(f"  [{i}] Webhook URL: ").strip()
        userid = input(f"  [{i}] User ID (untuk ping): ").strip()
        
        # Cek apakah ada field yang kosong
        if not channel or not webhook or not userid:
            if i == 1:
                print("  ❌ AKUN 1: Semua field WAJIB diisi! Setup dibatalkan.")
                return None
            else:
                # Untuk akun opsional, tanyakan apakah ingin skip atau ulangi
                missing = []
                if not channel: missing.append("Channel ID")
                if not webhook: missing.append("Webhook URL")
                if not userid: missing.append("User ID")
                
                print(f"  ⚠️  Akun {i}: Field yang kosong: {', '.join(missing)}")
                lanjut = input(f"  Lanjutkan ke akun berikutnya? (y/n): ").strip().lower()
                if lanjut == 'n':
                    print(f"  Ulangi akun {i}...\n")
                    i -= 1  # Ulangi akun ini
                    continue
                else:
                    print(f"  ⏭️  Akun {i} dilewati.")
                    break

        accounts.append((token, channel, webhook, userid))
        print(f"  ✅ Akun {i} tersimpan!")

    if not accounts:
        print("\n❌ Minimal 1 akun harus diisi!")
        return None

    print(f"\n✅ Total {len(accounts)} akun berhasil dikonfigurasi.\n")
    return accounts


# ============================================================
# Load config atau tampilkan menu interaktif
# ============================================================
lines = load_config()

accounts = []
for i in range(0, len(lines), 4):
    if i + 4 <= len(lines):
        accounts.append((lines[i], lines[i+1], lines[i+2], lines[i+3]))

# Kalau config kosong atau tidak ada, tampilkan menu interaktif
if not accounts:
    print(f"\n[INFO] Config.txt tidak ditemukan atau kosong di {CONFIG_PATH}")
    print("[INFO] Silakan isi konfigurasi akun Anda.\n")
    
    accounts = interactive_config()
    
    if accounts is None:
        print("[ERROR] Setup dibatalkan karena konfigurasi tidak lengkap.")
        sys.exit(1)
    
    # Simpan ke config.txt
    try:
        os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            for acc in accounts:
                f.write("\n".join(acc) + "\n")
        print(f"✅ Konfigurasi tersimpan di: {CONFIG_PATH}\n")
    except Exception as e:
        print(f"❌ Gagal menyimpan config: {e}")
        sys.exit(1)

# Batasi maksimal 6 akun
if len(accounts) > 6:
    print(f"[PERINGATAN] Ditemukan {len(accounts)} akun di config.txt, hanya 6 pertama yang akan dipakai.")
accounts = accounts[:6]

# ============================================================
# VALIDASI KRITIS: Akun pertama WAJIB ada dan token tidak boleh kosong
# ============================================================
if not accounts or not accounts[0][0]:
    print("\n" + "="*58)
    print("❌ ERROR KRITIS: AKUN PERTAMA (TOKEN) TIDAK BOLEH KOSONG!")
    print("="*58)
    print("\nBot tidak dapat dimulai. Pastikan akun 1 memiliki token yang valid.\n")
    sys.exit(1)

# ============================================================
# Validasi format tiap field (Token, Channel ID, Webhook URL, User ID)
# ============================================================
def validasi_akun(idx, token, channel, webhook, userid):
    masalah = []

    if not token or len(token) < 50:
        masalah.append("Token Discord sepertinya tidak valid (terlalu pendek/kosong)")

    if not channel.isdigit() or not (15 <= len(channel) <= 25):
        masalah.append(f"Channel ID '{channel}' sepertinya bukan ID yang valid (harus angka 15-25 digit)")

    if not re.match(r"^https://discord\.com/api/webhooks/\d+/[\w-]+$", webhook):
        masalah.append(f"Webhook URL '{webhook}' formatnya tidak sesuai (harus https://discord.com/api/webhooks/.../...)")

    if not userid.isdigit() or not (15 <= len(userid) <= 25):
        masalah.append(f"User ID '{userid}' sepertinya bukan ID yang valid (harus angka 15-25 digit)")

    if masalah:
        print(f"[PERINGATAN] AKUN {idx} - konfigurasi bermasalah:")
        for m in masalah:
            print(f"   - {m}")
        print(f"   Cek kembali config.txt untuk akun {idx}.")
        print("")

    return len(masalah) == 0


semua_valid = True
for idx, acc in enumerate(accounts, start=1):
    ok = validasi_akun(idx, acc[0], acc[1], acc[2], acc[3])
    if not ok:
        semua_valid = False

if not semua_valid:
    print("[INFO] Bot tetap akan dijalankan, tapi akun di atas mungkin gagal/error.")
    print("")

print("=" * 55)
print(f"  OWO BOT — {len(accounts)} Akun Terdeteksi")
print("=" * 55)
print("  • Jeda H+B   : 12-16 detik (random)")
print("  • Cek Gem    : Setiap 20 H+B")
print(f"  • Prefix     : {PREFIX}")
print(f"  • Jeda H+B   : {JEDA_MIN}-{JEDA_MAX} detik acak")
print(f"  • Long Break : {LONG_BREAK_MIN}-{LONG_BREAK_MAX} menit acak (tiap {LONG_BREAK_TRIGGER} H+B), tidak kirim cerita saat break")
print("  • .stopbot / .startbot di Discord (per akun)")
print("  • .testalert di Discord untuk tes notifikasi captcha (per akun)")
print("  • .stopbot / .startbot / exit di terminal (semua akun)")
print("  • CTRL+C juga bisa untuk berhenti")
print("=" * 55)

threads = []
for idx, acc in enumerate(accounts):
    t = threading.Thread(
        target=jalankan_bot,
        args=(idx + 1, acc[0], acc[1], acc[2], acc[3]),
        daemon=True
    )
    threads.append(t)
    t.start()
    if idx < len(accounts) - 1:
        time.sleep(5)

if sys.stdout.isatty():
    dashboard_thread = threading.Thread(target=dashboard_loop, daemon=True)
    dashboard_thread.start()
else:
    print("[INFO] Dashboard terminal dilewati (output bukan terminal interaktif).")
    print("[INFO] Status tetap dikirim ke webhook seperti biasa.")

if sys.stdin.isatty():
    cmd_thread = threading.Thread(target=command_loop, daemon=True)
    cmd_thread.start()

start_web_panel(8765)

try:
    while not shutdown_event.is_set():
        time.sleep(1)
except KeyboardInterrupt:
    print("\n[STOPPED] CTRL+C diterima, menghentikan semua akun...")
    shutdown_event.set()

if panel_server is not None:
    panel_server.shutdown()
    panel_server.server_close()
    panel_server = None

# Beri waktu sebentar agar tiap thread akun keluar dari loop dengan rapi
time.sleep(2)
print("[STOPPED] Semua akun dihentikan.")
