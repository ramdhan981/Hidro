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
pkg install curl -y -q 2>/dev/null
pkg install dialog -y -q 2>/dev/null
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
    echo "  Lanjutkan setup setelah itu dengan: bash ~/owobot/setup.sh"
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

    for AKUN_KE in 1 2 3 4 5 6; do
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

# Pengaturan bot (prefix, jeda H+B, long break, gem, pray)
SETTINGS_FILE=~/owobot/settings.txt
declare -A OLD_SET
if [ -f "$SETTINGS_FILE" ]; then
    while IFS='=' read -r k v; do
        [ -z "$k" ] && continue
        OLD_SET["$k"]="$v"
    done < "$SETTINGS_FILE"
fi

# Nilai default (dari settings.txt lama, atau default bawaan kalau belum ada)
D_PREFIX="${OLD_SET[PREFIX]:-owo}"
D_BOT_NAME="${OLD_SET[BOT_NAME]:-owo}"
D_JEDA_MIN="${OLD_SET[JEDA_MIN]:-12}"
D_JEDA_MAX="${OLD_SET[JEDA_MAX]:-16}"
D_LB_TRIGGER="${OLD_SET[LONG_BREAK_TRIGGER]:-200}"
D_LB_MIN="${OLD_SET[LONG_BREAK_MIN]:-10}"
D_LB_MAX="${OLD_SET[LONG_BREAK_MAX]:-17}"
D_GEM_INT="${OLD_SET[GEM_CHECK_INTERVAL]:-20}"
D_PRAY_SEC="${OLD_SET[PRAY_INTERVAL_SECONDS]:-300}"

echo "⚙️  Pengaturan Bot saat ini:"
echo "   Prefix=$D_PREFIX | Bot Name=$D_BOT_NAME | Jeda=$D_JEDA_MIN-$D_JEDA_MAX detik"
echo "   Long Break tiap $D_LB_TRIGGER H+B ($D_LB_MIN-$D_LB_MAX menit) | Cek Gem tiap $D_GEM_INT H+B | Pray tiap $D_PRAY_SEC detik"
echo ""
read -p "   Mau ubah pengaturan? (y/n, Enter=pakai yang tersimpan): " GANTI_SET

if [ "$GANTI_SET" == "y" ] || [ "$GANTI_SET" == "Y" ]; then
    if command -v dialog >/dev/null 2>&1; then
        exec 3>&1
        FORM_OUTPUT=$(dialog --backtitle "OWO Bot - Pengaturan" \
            --form "Edit semua pengaturan (TAB/Panah pindah kolom, Enter selesai):" 20 70 9 \
            "Prefix command:"                  1 1 "$D_PREFIX"    1 26 20 0 \
            "Nama bot game (Discord):"         2 1 "$D_BOT_NAME"  2 26 20 0 \
            "Jeda H+B min (detik):"            3 1 "$D_JEDA_MIN"  3 26 10 0 \
            "Jeda H+B max (detik):"            4 1 "$D_JEDA_MAX"  4 26 10 0 \
            "Long break tiap (H+B):"           5 1 "$D_LB_TRIGGER" 5 26 10 0 \
            "Long break min (menit):"          6 1 "$D_LB_MIN"    6 26 10 0 \
            "Long break max (menit):"          7 1 "$D_LB_MAX"    7 26 10 0 \
            "Cek gem tiap (H+B):"              8 1 "$D_GEM_INT"   8 26 10 0 \
            "Interval pray (detik, 300=5m):"   9 1 "$D_PRAY_SEC"  9 26 10 0 \
            2>&1 1>&3)
        FORM_STATUS=$?
        exec 3>&-
        clear
        if [ $FORM_STATUS -eq 0 ] && [ -n "$FORM_OUTPUT" ]; then
            mapfile -t FVALS <<< "$FORM_OUTPUT"
            SET_PREFIX="${FVALS[0]:-$D_PREFIX}"
            SET_BOT_NAME="${FVALS[1]:-$D_BOT_NAME}"
            SET_JEDA_MIN="${FVALS[2]:-$D_JEDA_MIN}"
            SET_JEDA_MAX="${FVALS[3]:-$D_JEDA_MAX}"
            SET_LB_TRIGGER="${FVALS[4]:-$D_LB_TRIGGER}"
            SET_LB_MIN="${FVALS[5]:-$D_LB_MIN}"
            SET_LB_MAX="${FVALS[6]:-$D_LB_MAX}"
            SET_GEM_INTERVAL="${FVALS[7]:-$D_GEM_INT}"
            SET_PRAY_SEC="${FVALS[8]:-$D_PRAY_SEC}"
        else
            echo "   Dibatalkan, pengaturan lama tetap dipakai."
            SET_PREFIX="$D_PREFIX"; SET_BOT_NAME="$D_BOT_NAME"
            SET_JEDA_MIN="$D_JEDA_MIN"; SET_JEDA_MAX="$D_JEDA_MAX"
            SET_LB_TRIGGER="$D_LB_TRIGGER"; SET_LB_MIN="$D_LB_MIN"; SET_LB_MAX="$D_LB_MAX"
            SET_GEM_INTERVAL="$D_GEM_INT"; SET_PRAY_SEC="$D_PRAY_SEC"
        fi
    else
        echo "   ⚠️  'dialog' tidak tersedia, pakai mode tanya satu-satu:"
        read -e -i "$D_PREFIX" -p "   Prefix command: " SET_PREFIX
        read -e -i "$D_BOT_NAME" -p "   Nama bot game: " SET_BOT_NAME
        read -e -i "$D_JEDA_MIN" -p "   Jeda H+B minimal (detik): " SET_JEDA_MIN
        read -e -i "$D_JEDA_MAX" -p "   Jeda H+B maksimal (detik): " SET_JEDA_MAX
        read -e -i "$D_LB_TRIGGER" -p "   Long break setiap berapa H+B: " SET_LB_TRIGGER
        read -e -i "$D_LB_MIN" -p "   Long break minimal (menit): " SET_LB_MIN
        read -e -i "$D_LB_MAX" -p "   Long break maksimal (menit): " SET_LB_MAX
        read -e -i "$D_GEM_INT" -p "   Cek/pasang gem setiap berapa H+B: " SET_GEM_INTERVAL
        read -e -i "$D_PRAY_SEC" -p "   Interval pray (detik): " SET_PRAY_SEC
    fi

    cat > "$SETTINGS_FILE" << SETEOF
PREFIX=${SET_PREFIX:-owo}
BOT_NAME=${SET_BOT_NAME:-owo}
JEDA_MIN=${SET_JEDA_MIN:-12}
JEDA_MAX=${SET_JEDA_MAX:-16}
LONG_BREAK_TRIGGER=${SET_LB_TRIGGER:-200}
LONG_BREAK_MIN=${SET_LB_MIN:-10}
LONG_BREAK_MAX=${SET_LB_MAX:-17}
GEM_CHECK_INTERVAL=${SET_GEM_INTERVAL:-20}
PRAY_INTERVAL_SECONDS=${SET_PRAY_SEC:-300}
SETEOF
    echo "   ✅ Pengaturan tersimpan!"
elif [ ! -f "$SETTINGS_FILE" ]; then
    # Belum pernah ada settings.txt sama sekali -> tulis default
    cat > "$SETTINGS_FILE" << SETEOF
PREFIX=$D_PREFIX
BOT_NAME=$D_BOT_NAME
JEDA_MIN=$D_JEDA_MIN
JEDA_MAX=$D_JEDA_MAX
LONG_BREAK_TRIGGER=$D_LB_TRIGGER
LONG_BREAK_MIN=$D_LB_MIN
LONG_BREAK_MAX=$D_LB_MAX
GEM_CHECK_INTERVAL=$D_GEM_INT
PRAY_INTERVAL_SECONDS=$D_PRAY_SEC
SETEOF
    echo "   ✅ Pengaturan default dibuat (belum ada sebelumnya)."
else
    echo "   ➡️  Pengaturan lama dipakai (tidak diubah)."
fi
echo ""

echo "[4/4] Ambil owobot.py, webpanel.py, webhook_utils.py & stories.txt dari GitHub (ramdhan981/Hidro)..."
GITHUB_USER="ramdhan981"
GITHUB_REPO="Hidro"
GITHUB_BRANCH="main"
RAW_BASE="https://raw.githubusercontent.com/$GITHUB_USER/$GITHUB_REPO/$GITHUB_BRANCH"

if curl -sL -f "$RAW_BASE/owobot.py" -o ~/owobot/owobot.py 2>/dev/null; then
    echo "      ✅ owobot.py diambil dari GitHub!"
elif [ -f /sdcard/Download/owobot.py ]; then
    cp /sdcard/Download/owobot.py ~/owobot/owobot.py
    echo "      owobot.py diambil dari Download (GitHub gagal/offline)"
elif [ -f ~/owobot/owobot.py ]; then
    echo "      owobot.py pakai yang sudah ada"
else
    echo ""
    echo "  ⚠️  owobot.py tidak ditemukan (GitHub gagal & tidak ada di Download)!"
    echo "  Cek koneksi internet, atau taruh manual di /sdcard/Download/"
    echo ""
    exit 1
fi

if curl -sL -f "$RAW_BASE/webpanel.py" -o ~/owobot/webpanel.py 2>/dev/null; then
    echo "      ✅ webpanel.py diambil dari GitHub!"
elif [ -f /sdcard/Download/webpanel.py ]; then
    cp /sdcard/Download/webpanel.py ~/owobot/webpanel.py
    echo "      webpanel.py diambil dari Download (GitHub gagal/offline)"
elif [ -f ~/owobot/webpanel.py ]; then
    echo "      webpanel.py pakai yang sudah ada"
else
    echo ""
    echo "  ⚠️  webpanel.py tidak ditemukan! Bot butuh file ini untuk jalan."
    echo "  Cek koneksi internet, atau taruh manual di /sdcard/Download/"
    echo ""
    exit 1
fi

if curl -sL -f "$RAW_BASE/webhook_utils.py" -o ~/owobot/webhook_utils.py 2>/dev/null; then
    echo "      ✅ webhook_utils.py diambil dari GitHub!"
elif [ -f /sdcard/Download/webhook_utils.py ]; then
    cp /sdcard/Download/webhook_utils.py ~/owobot/webhook_utils.py
    echo "      webhook_utils.py diambil dari Download (GitHub gagal/offline)"
elif [ -f ~/owobot/webhook_utils.py ]; then
    echo "      webhook_utils.py pakai yang sudah ada"
else
    echo ""
    echo "  ⚠️  webhook_utils.py tidak ditemukan! Bot butuh file ini untuk jalan."
    echo "  Cek koneksi internet, atau taruh manual di /sdcard/Download/"
    echo ""
    exit 1
fi

if curl -sL -f "$RAW_BASE/stories.txt" -o ~/owobot/stories.txt 2>/dev/null; then
    echo "      ✅ stories.txt diambil dari GitHub!"
elif [ -f /sdcard/Download/stories.txt ]; then
    cp /sdcard/Download/stories.txt ~/owobot/stories.txt
    echo "      stories.txt diambil dari Download (GitHub gagal/offline)"
elif [ -f ~/owobot/stories.txt ]; then
    echo "      stories.txt pakai yang sudah ada"
else
    echo "      ⚠️  stories.txt tidak ditemukan, bot akan pakai 2 cerita default saja."
fi

# Buat command asli di $PREFIX/bin (selalu ada di PATH, tidak bergantung .bashrc/login-shell)
BIN_DIR="$PREFIX/bin"
mkdir -p "$BIN_DIR"

cat > "$BIN_DIR/owo" << 'EOF'
#!/data/data/com.termux/files/usr/bin/bash
mkdir -p ~/owobot
curl -sL -f "https://raw.githubusercontent.com/ramdhan981/Hidro/main/setup.sh" -o ~/owobot/setup.sh 2>/dev/null
bash ~/owobot/setup.sh
EOF

cat > "$BIN_DIR/owostart" << 'EOF'
#!/data/data/com.termux/files/usr/bin/bash
mkdir -p ~/owobot
curl -sL -f "https://raw.githubusercontent.com/ramdhan981/Hidro/main/setup.sh" -o ~/owobot/setup.sh 2>/dev/null
bash ~/owobot/setup.sh start
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
am start -a android.intent.action.VIEW -d http://127.0.0.1:8765/
EOF

chmod +x "$BIN_DIR/owo" "$BIN_DIR/owostart" "$BIN_DIR/owolog" "$BIN_DIR/owostop" "$BIN_DIR/oworeset" "$BIN_DIR/owoweb"

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
echo ""
echo "=================================="
echo "  📋 SHORTCUT YANG BISA DIPAKAI:"
echo "=================================="
echo "   owo       → setup + jalankan bot"
echo "   owostart  → langsung lanjut bot di background"
echo "   owolog    → lihat log bot live"
echo "   owostop   → hentikan bot"
echo "   oworeset  → reset config dan log bot"
echo "   owoweb    → buka panel web di browser"
echo ""
