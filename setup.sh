#!/bin/bash

clear
echo "=================================="
echo "     OWO BOT - AUTO SETUP"
echo "=================================="
echo ""

# Cek argumen — kalau "start" langsung jalankan bot tanpa setup
if [ "$1" == "start" ]; then
    if [ -f ~/owobot/owobot.py ]; then
        echo "▶️  Melanjutkan bot di latar belakang..."
        termux-wake-lock
        cd ~/owobot && nohup python owobot.py > ~/owobot/bot.log 2>&1 &
        echo "✅ Bot berjalan di latar belakang!"
        echo "   Lihat log  : tail -f ~/owobot/bot.log"
        echo "   Stop bot   : pkill -f owobot.py"
        exit 0
    else
        echo "⚠️  File owobot.py tidak ditemukan!"
        exit 1
    fi
fi

# Install
echo "[1/4] Install Python, requests & Termux tools..."
pkg update -y -q 2>/dev/null
pkg install python -y -q 2>/dev/null
pkg install termux-tools -y -q 2>/dev/null
pip install requests -q 2>/dev/null
mkdir -p ~/owobot
mkdir -p ~/.termux/boot
echo "      Selesai!"
echo ""

# Setup background (wake lock + boot script)
echo "[2/4] Setup background mode..."

# Buat script auto-start saat HP nyala
cat > ~/.termux/boot/owobot.sh << 'BOOTEOF'
#!/data/data/com.termux/files/usr/bin/bash
sleep 10
termux-wake-lock
cd ~/owobot && python owobot.py
BOOTEOF
chmod +x ~/.termux/boot/owobot.sh

echo "      ✅ Auto-start saat HP nyala: OK"
echo "      ✅ Wake lock (layar mati tetap jalan): OK"
echo ""
echo "  ⚠️  PENTING: Matikan Battery Optimization untuk Termux!"
echo "  Caranya:"
echo "  1. Buka Settings HP"
echo "  2. Battery → Battery Optimization"
echo "  3. Cari Termux → pilih 'Don't optimize'"
echo "  4. Ulangi untuk Termux:Boot"
echo ""
read -p "  Sudah matikan battery optimization? (Y/n, Enter=lanjut): " BATT
if [ "$BATT" == "n" ] || [ "$BATT" == "N" ]; then
    echo ""
    echo "  ⚠️  Silakan matikan dulu agar bot tidak terhenti!"
    echo "  Lanjutkan setup setelah itu dengan: bash ~/setup.sh"
    echo ""
    exit 1
fi
echo ""

# Helper: tampilkan token secara ringkas (tidak full, biar aman dilihat)
mask_token() {
    local t="$1"
    local len=${#t}
    if [ -z "$t" ]; then
        echo "(kosong)"
    elif [ $len -le 10 ]; then
        echo "******"
    else
        echo "${t:0:6}...${t: -4}"
    fi
}

# Load config lama (kalau ada) ke dalam array per akun
declare -a OLD_TOKEN OLD_CHANNEL OLD_WEBHOOK OLD_USERID
AKUN_LAMA=0
if [ -f ~/owobot/config.txt ]; then
    mapfile -t CFG_LINES < ~/owobot/config.txt
    AKUN_LAMA=$(( ${#CFG_LINES[@]} / 4 ))
    for ((i=1; i<=AKUN_LAMA; i++)); do
        idx=$(( (i-1)*4 ))
        OLD_TOKEN[$i]="${CFG_LINES[$idx]}"
        OLD_CHANNEL[$i]="${CFG_LINES[$((idx+1))]}"
        OLD_WEBHOOK[$i]="${CFG_LINES[$((idx+2))]}"
        OLD_USERID[$i]="${CFG_LINES[$((idx+3))]}"
    done
fi

# Tampilkan tabel config saat ini (kalau ada)
if [ $AKUN_LAMA -gt 0 ]; then
    echo "✅ Config tersimpan saat ini ($AKUN_LAMA akun):"
    echo ""
    printf "  %-5s | %-17s | %-20s | %-45s | %-20s\n" "AKUN" "TOKEN" "CHANNEL ID" "WEBHOOK URL" "USER ID"
    printf "  %s\n" "------+-------------------+----------------------+-----------------------------------------------+----------------------"
    for ((i=1; i<=AKUN_LAMA; i++)); do
        wh="${OLD_WEBHOOK[$i]}"
        if [ ${#wh} -gt 45 ]; then
            wh="${wh:0:42}..."
        fi
        printf "  %-5s | %-17s | %-20s | %-45s | %-20s\n" "$i" "$(mask_token "${OLD_TOKEN[$i]}")" "${OLD_CHANNEL[$i]}" "$wh" "${OLD_USERID[$i]}"
    done
    echo ""
    read -p "   Mau ubah config? (y/n) (y=ya, n=tetap pakai yang ada): " GANTI
    echo ""
    if [ "$GANTI" != "y" ] && [ "$GANTI" != "Y" ]; then
        SKIP_CONFIG=true
    fi
fi

# Helper: input dengan nilai lama sudah terisi (bisa diedit langsung, atau dihapus & ganti baru)
read_with_default() {
    local prompt="$1"
    local default_val="$2"
    local result
    if [ -n "$default_val" ]; then
        read -e -i "$default_val" -p "$prompt" result
    else
        read -p "$prompt" result
    fi
    printf '%s' "$result"
}

if [ "$SKIP_CONFIG" != "true" ]; then
    echo "[3/4] Isi konfigurasi akun:"
    echo "      Nilai lama sudah terisi otomatis. Edit langsung kalau perlu diganti,"
    echo "      atau tekan Enter saja untuk pakai yang sudah ada."
    echo ""
    > ~/owobot/config.txt
    AKUN_TERSIMPAN=0

    for AKUN_KE in 1 2 3 4 5; do
        HAS_OLD=false
        if [ $AKUN_KE -le $AKUN_LAMA ] && [ -n "${OLD_TOKEN[$AKUN_KE]}" ]; then
            HAS_OLD=true
        fi
        DO_EDIT=true

        if [ $AKUN_KE -eq 1 ]; then
            echo "  --- AKUN $AKUN_KE (Wajib) ---"
        else
            echo "  --- AKUN $AKUN_KE (Opsional) ---"
            if [ "$HAS_OLD" == "true" ]; then
                read -p "  Akun $AKUN_KE sudah ada, mau diubah? (y/n, n=biarkan seperti sekarang): " LAGI
                if [ "$LAGI" != "y" ] && [ "$LAGI" != "Y" ]; then
                    DO_EDIT=false
                fi
            else
                read -p "  Tambah akun $AKUN_KE baru? (y/n): " LAGI
                if [ "$LAGI" != "y" ] && [ "$LAGI" != "Y" ]; then
                    break
                fi
            fi
        fi

        if [ "$HAS_OLD" == "true" ] && [ "$DO_EDIT" == "false" ]; then
            printf "%s\n%s\n%s\n%s\n" "${OLD_TOKEN[$AKUN_KE]}" "${OLD_CHANNEL[$AKUN_KE]}" "${OLD_WEBHOOK[$AKUN_KE]}" "${OLD_USERID[$AKUN_KE]}" >> ~/owobot/config.txt
            AKUN_TERSIMPAN=$AKUN_KE
            echo "  ➡️  Akun $AKUN_KE dibiarkan seperti semula."
            echo ""
            continue
        fi

        TOKEN=$(read_with_default "  Token Discord  : " "${OLD_TOKEN[$AKUN_KE]}")
        CHANNEL=$(read_with_default "  Channel ID     : " "${OLD_CHANNEL[$AKUN_KE]}")
        WEBHOOK=$(read_with_default "  Webhook URL    : " "${OLD_WEBHOOK[$AKUN_KE]}")
        USERID=$(read_with_default "  User ID (ping) : " "${OLD_USERID[$AKUN_KE]}")

        if [ -z "$TOKEN" ] || [ -z "$CHANNEL" ] || [ -z "$WEBHOOK" ] || [ -z "$USERID" ]; then
            if [ $AKUN_KE -eq 1 ]; then
                echo "  ⚠️  Akun 1 wajib diisi lengkap! Setup dibatalkan."
                exit 1
            else
                echo "  ⚠️  Data akun $AKUN_KE belum lengkap, dilewati."
                echo ""
                break
            fi
        fi

        printf "%s\n%s\n%s\n%s\n" "$TOKEN" "$CHANNEL" "$WEBHOOK" "$USERID" >> ~/owobot/config.txt
        AKUN_TERSIMPAN=$AKUN_KE
        echo "  ✅ Akun $AKUN_KE tersimpan!"
        echo ""
    done

    echo ""
    echo "      Config tersimpan permanen! ($AKUN_TERSIMPAN akun)"
    echo ""
else
    echo "[3/4] Config dilewati (sudah ada)."
    echo ""
fi

# Setup password panel web
PANEL_PW_FILE=~/owobot/panel_password.txt
OLD_PANEL_PW=""
if [ -f "$PANEL_PW_FILE" ]; then
    OLD_PANEL_PW=$(cat "$PANEL_PW_FILE")
fi
echo "🔒 Password untuk panel web (owoweb) — biar tidak sembarang orang di WiFi yang sama bisa pause/stop bot kamu."
if [ -n "$OLD_PANEL_PW" ]; then
    read -e -i "$OLD_PANEL_PW" -p "   Password panel (Enter=pakai yang lama): " PANEL_PW
else
    read -p "   Buat password panel (Enter=pakai default 'owobot123'): " PANEL_PW
fi
if [ -z "$PANEL_PW" ]; then
    PANEL_PW="${OLD_PANEL_PW:-owobot123}"
fi
echo "$PANEL_PW" > "$PANEL_PW_FILE"
echo "   ✅ Password panel: $PANEL_PW (dipakai saat buka owoweb)"
echo ""
echo "[4/4] Copy file owobot.py & stories.txt..."
if [ -f /sdcard/Download/owobot.py ]; then
    cp /sdcard/Download/owobot.py ~/owobot/owobot.py
    echo "      owobot.py ditemukan & disalin!"
elif [ -f ~/owobot/owobot.py ]; then
    echo "      owobot.py sudah ada!"
else
    echo ""
    echo "  ⚠️  File owobot.py tidak ditemukan!"
    echo "  Download owobot.py lalu kirim ke /sdcard/Download/"
    echo "  Lalu jalankan lagi: bash ~/setup.sh"
    echo ""
    exit 1
fi

if [ -f /sdcard/Download/stories.txt ]; then
    cp /sdcard/Download/stories.txt ~/owobot/stories.txt
    echo "      stories.txt ditemukan & disalin!"
elif [ -f ~/owobot/stories.txt ]; then
    echo "      stories.txt sudah ada!"
else
    echo "      ⚠️  stories.txt tidak ditemukan, bot akan pakai 2 cerita default saja."
fi

# Buat command asli di $PREFIX/bin (selalu ada di PATH, tidak bergantung .bashrc/login-shell)
BIN_DIR="$PREFIX/bin"
mkdir -p "$BIN_DIR"

cat > "$BIN_DIR/owo" << 'EOF'
#!/data/data/com.termux/files/usr/bin/bash
bash ~/setup.sh
EOF

cat > "$BIN_DIR/owostart" << 'EOF'
#!/data/data/com.termux/files/usr/bin/bash
bash ~/setup.sh start
EOF

cat > "$BIN_DIR/owolog" << 'EOF'
#!/data/data/com.termux/files/usr/bin/bash
tail -f ~/owobot/bot.log
EOF

cat > "$BIN_DIR/owostop" << 'EOF'
#!/data/data/com.termux/files/usr/bin/bash
pkill -f owobot.py && echo "Bot dihentikan!"
EOF

cat > "$BIN_DIR/oworeset" << 'EOF'
#!/data/data/com.termux/files/usr/bin/bash
rm -f ~/owobot/config.txt ~/owobot/owobot.py ~/owobot/bot.log
echo "Reset selesai. Jalankan owo untuk setup ulang."
EOF

cat > "$BIN_DIR/owoweb" << 'EOF'
#!/data/data/com.termux/files/usr/bin/bash
if [ -f ~/owobot/panel_password.txt ]; then
    echo "🔒 Password panel: $(cat ~/owobot/panel_password.txt)"
else
    echo "🔒 Password panel: owobot123 (default)"
fi
am start -a android.intent.action.VIEW -d http://127.0.0.1:8765/
EOF

chmod +x "$BIN_DIR/owo" "$BIN_DIR/owostart" "$BIN_DIR/owolog" "$BIN_DIR/owostop" "$BIN_DIR/oworeset" "$BIN_DIR/owoweb"

echo "✅ Command berhasil dibuat!"
echo "   owo       → setup + jalankan bot"
echo "   owostart  → langsung lanjut bot di background"
echo "   owolog    → lihat log bot live"
echo "   owostop   → hentikan bot"
echo "   oworeset  → reset config dan log bot"
echo "   owoweb    → buka panel web di browser"
echo ""

echo ""
echo "=================================="
echo "  Setup selesai! Memulai bot..."
echo "=================================="
echo ""
termux-wake-lock
cd ~/owobot && nohup python owobot.py > ~/owobot/bot.log 2>&1 &
echo ""
echo "✅ Bot berjalan di latar belakang!"
echo "   Termux bisa ditutup, bot tetap jalan!"
echo ""
echo "   Lihat log  : tail -f ~/owobot/bot.log"
echo "   Stop bot   : pkill -f owobot.py"
