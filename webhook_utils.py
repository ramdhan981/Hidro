"""
Fungsi pengiriman status & alert ke webhook Discord.
Dipisah dari owobot.py supaya file utama lebih ringkas.

Semua fungsi di sini menerima 'state' (dict) dan konteks akun sebagai
parameter eksplisit — tidak bergantung pada variabel global/closure,
supaya bisa dipanggil dari akun manapun tanpa saling tabrakan.
"""
from datetime import datetime


def build_embed(state, label, profile_name):
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


def send_webhook(state, WEBHOOK_URL, label, profile_name, safe_request):
    try:
        embed = build_embed(state, label, profile_name)
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


def send_alert(state, msg_content, WEBHOOK_URL, PING_USER_ID, label, profile_name, safe_request, is_test=False):
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
