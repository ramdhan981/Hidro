import os
import requests
import time
import random
import sys
import re
import threading
from datetime import datetime

HUMAN_KEYWORDS = [
    "are you human", "human verification",
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

def extract_components_text(components):
    """Ambil semua teks dari struktur Discord 'Components V2' (rekursif),
    karena beberapa bot (misal UwU) kirim pesan captcha lewat format ini,
    bukan lewat 'content' atau 'embeds' biasa."""
    text = ""
    if not components:
        return text
    for comp in components:
        if not isinstance(comp, dict):
            continue
        if "content" in comp:
            text += " " + str(comp.get("content", ""))
        if comp.get("components"):
            text += " " + extract_components_text(comp["components"])
        if comp.get("accessory") and isinstance(comp["accessory"], dict) and "content" in comp["accessory"]:
            text += " " + str(comp["accessory"].get("content", ""))
    return text


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
        "BOT_NAME": "owo",
        "JEDA_MIN": "12",
        "JEDA_MAX": "16",
        "LONG_BREAK_TRIGGER": "200",
        "LONG_BREAK_MIN": "10",
        "LONG_BREAK_MAX": "17",
        "GEM_CHECK_INTERVAL": "20",
        "PRAY_INTERVAL_SECONDS": "300",
        "VOTE_ENABLED": "y",
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
BOT_NAME = SETTINGS["BOT_NAME"].lower()
JEDA_MIN = float(SETTINGS["JEDA_MIN"])
JEDA_MAX = float(SETTINGS["JEDA_MAX"])
LONG_BREAK_TRIGGER = int(SETTINGS["LONG_BREAK_TRIGGER"])
LONG_BREAK_MIN = float(SETTINGS["LONG_BREAK_MIN"])
LONG_BREAK_MAX = float(SETTINGS["LONG_BREAK_MAX"])
GEM_CHECK_INTERVAL = int(SETTINGS["GEM_CHECK_INTERVAL"])
PRAY_INTERVAL_SECONDS = int(SETTINGS["PRAY_INTERVAL_SECONDS"])
VOTE_ENABLED = SETTINGS["VOTE_ENABLED"].strip().lower() == "y"

# ============================================================
# Web panel (owoweb) & webhook Discord — dipindah ke file terpisah
# ============================================================
from webpanel import dashboard_lock, all_accounts_state, shutdown_event, start_web_panel
import webhook_utils

CONFIG_PATH = os.path.join(SCRIPT_DIR, "config.txt")
if not os.path.exists(CONFIG_PATH):
    CONFIG_PATH = os.path.join(os.path.expanduser("~"), "owobot", "config.txt")


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
        lines.append(f"  Cash       : {state['cash_status']}")

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
        "vote_status": "Belum dicek" if VOTE_ENABLED else "🚫 Dinonaktifkan",
        "last_pray_time": None,
        "pray_status": "Belum dicek",
        "daily_done": False,
        "daily_status": "Belum dicek",
        "cash_status": "Belum dicek",
        "pause_status": "🟢 Aktif",
        "pause_seconds": 0,
        "embed_color": 0x57F287,
        "webhook_msg_url": None,
    }

    label = f"[AKUN-{acc_id}]"

    profile_name = f"Akun #{acc_id}"
    avatar_url = None
    token_valid = False
    token_error_reason = ""
    try:
        resp = requests.get("https://discord.com/api/v10/users/@me", headers={"Authorization": TOKEN}, timeout=10)
        if resp.status_code == 200:
            user_data = resp.json()
            profile_name = f"{user_data.get('username', 'Unknown')}#{user_data.get('discriminator', '0000')} (Akun {acc_id})"
            user_id = user_data.get("id")
            avatar_hash = user_data.get("avatar")
            if user_id and avatar_hash:
                ext = "gif" if avatar_hash.startswith("a_") else "png"
                avatar_url = f"https://cdn.discordapp.com/avatars/{user_id}/{avatar_hash}.{ext}?size=64"
            elif user_id:
                default_idx = int(user_data.get("discriminator", "0")) % 5 if user_data.get("discriminator", "0").isdigit() else 0
                avatar_url = f"https://cdn.discordapp.com/embed/avatars/{default_idx}.png"
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
            "avatar_url": avatar_url,
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

    def send_webhook():
        webhook_utils.send_webhook(state, WEBHOOK_URL, label, profile_name, safe_request, GEM_CHECK_INTERVAL, VOTE_ENABLED)

    def send_alert(msg_content, is_test=False):
        webhook_utils.send_alert(
            state, msg_content, WEBHOOK_URL, PING_USER_ID, label, profile_name,
            safe_request, is_test
        )

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
                        if author.get("bot") and BOT_NAME in author.get("username", "").lower():
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
                    raw_content = msg.get("content", "")
                    embed_text = ""
                    for emb in msg.get("embeds", []):
                        embed_text += " " + emb.get("title", "")
                        embed_text += " " + emb.get("description", "")
                        footer = emb.get("footer", {}) or {}
                        embed_text += " " + footer.get("text", "")
                        author_blk = emb.get("author", {}) or {}
                        embed_text += " " + author_blk.get("name", "")
                        for field in emb.get("fields", []):
                            embed_text += " " + field.get("name", "") + " " + field.get("value", "")

                    component_text = extract_components_text(msg.get("components", []))

                    msg_content = (raw_content + " " + embed_text + " " + component_text).strip()
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

                    if "type the code from the image in this channel" in msg_lower:
                        return True, msg_content

                    if "ketik code dari gambar di channel ini" in msg_lower:
                        return True, msg_content

                    for kw in HUMAN_KEYWORDS:
                        if kw in msg_lower:
                            return True, msg_content
        except Exception:
            pass
        return False, ""

    def handle_captcha_check():
        """True kalau captcha terdeteksi & sudah ditangani (loop utama harus 'continue')."""
        detected, tmsg = check_human()
        if not detected:
            return False
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
        return True

    def check_discord_cmd():
        try:
            r = safe_request("GET", f"{URL}?limit=5", headers=headers, timeout=10, max_wait=20)
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
                        if not (author.get("bot") and BOT_NAME in author.get("username", "").lower()):
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
            log(f"⚠️ Inv: {BOT_NAME.upper()} tidak balas")
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
            if (datetime.now() - state["last_pray_time"]).total_seconds() < PRAY_INTERVAL_SECONDS:
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

    def auto_check_cash():
        before_id = get_last_msg_id()
        time.sleep(random.uniform(1, 2))
        safe_request("POST", URL, json={"content": f"{PREFIX} cash"}, headers=headers)
        time.sleep(3)
        resp = get_owo_response(before_id, timeout=6)
        ts = datetime.now().strftime("%H:%M:%S")
        if resp:
            m = re.search(r"have\s*[*_\s]*([\d,]+)[*_\s]*cowoncy", resp, re.IGNORECASE)
            if m:
                amount = m.group(1)
                state["cash_status"] = f"{amount} cowoncy ({ts})"
                log(f"💰 Cash: {amount}")
            else:
                state["cash_status"] = f"Format tidak dikenali ({ts})"
                log("💰 Cash: format tidak dikenali")
        else:
            state["cash_status"] = f"{BOT_NAME.upper()} tidak balas ({ts})"
            log(f"💰 Cash: {BOT_NAME.upper()} tidak balas")
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
    auto_check_cash()

    try:
        while not shutdown_event.is_set():
            if handle_captcha_check():
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
            state["grand_total"] += 1
            state["total_actions"] = state.get("total_actions", 0) + 1
            state["counter"] += 1

            log(f"✅ H+B #{state['grand_total']}")
            time.sleep(1)

            hunt_resp = get_owo_response(before_id, timeout=4)
            if hunt_resp:
                check_gem_expiry(hunt_resp)

            if handle_captcha_check():
                if shutdown_event.is_set():
                    break
                continue

            try:
                safe_request("POST", URL, json={"content": random.choice(stories)}, headers=headers)
            except Exception:
                pass

            send_webhook()

            if state.get("total_actions", 0) >= LONG_BREAK_TRIGGER:
                auto_check_cash()
                break_minutes = round(random.uniform(LONG_BREAK_MIN, LONG_BREAK_MAX), 1)
                break_secs = int(break_minutes * 60)
                log(f"☕ Long Break ({break_minutes} menit)...")
                send_webhook()
                system_pause(break_secs, "LONG BREAK", send_story=False)
                state["total_actions"] = 0
            else:
                pause_secs = round(random.uniform(JEDA_MIN, JEDA_MAX), 1)
                system_pause(pause_secs, "Jeda H+B", show_status=False)

            if state["grand_total"] % GEM_CHECK_INTERVAL == 0 and state["grand_total"] > 0:
                log(f"🎒 Cek inventory rutin (setiap {GEM_CHECK_INTERVAL} H+B)...")
                send_webhook()
                state["gems_need"] = list(GEM_CODES.keys())
                get_inventory_and_equip(force=True)
                system_pause(random.randint(5, 8), "Jeda Inventory", show_status=False)

            auto_pray()
            if VOTE_ENABLED:
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
print(f"  • Cek Gem    : Setiap {GEM_CHECK_INTERVAL} H+B")
print(f"  • Pray       : Setiap {PRAY_INTERVAL_SECONDS} detik ({round(PRAY_INTERVAL_SECONDS/60, 1)} menit)")
print(f"  • Prefix     : {PREFIX}")
print(f"  • Bot Name   : {BOT_NAME} (dipakai untuk deteksi balasan)")
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
