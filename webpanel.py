"""
Panel web (owoweb) — status board & kontrol pause/resume/stop lewat browser.
Dipisah dari owobot.py supaya file utama lebih ringkas.
"""
import json
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# State bersama antar semua akun & thread — jangan di-reassign, cuma dibaca/diisi.
dashboard_lock = threading.Lock()
all_accounts_state = {}
shutdown_event = threading.Event()
panel_server = None


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
            "cash": state["cash_status"],
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
                            <div class=\"small\">Cash: ${escapeHtml(acc.cash)}</div>
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

