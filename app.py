from flask import Flask, request, jsonify
import os
import hashlib
import time
from datetime import datetime, timezone

import psycopg2
from psycopg2.extras import RealDictCursor

app = Flask(__name__)

# ---------------------- DB BAĞLANTISI ----------------------

DATABASE_URL = os.environ.get("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL ortam değişkeni ayarlı değil (Supabase bağlantısı yok).")


def get_conn():
    """
    Her istek için yeni bir DB bağlantısı açar.
    Render + Supabase için basit ve güvenli yöntem.
    """
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)


ONLINE_THRESHOLD = 60 * 2  # son 2 dakika içinde ping geldiyse ONLINE say


@app.route("/")
def home():
    return "TRX Goblin Server Çalışıyor!"


# ==========================================================
# REGISTER
# ==========================================================
@app.post("/register")
def register():
    data = request.json or {}
    username = data.get("username")
    password = data.get("password")      # uygulama içi şifre (plain)
    email = data.get("email")            # kullanıcı e-postası
    device_model = data.get("device_model")  # PC / telefon modeli (opsiyonel)

    if not username or not password or not email:
        return jsonify({"error": "missing_fields"}), 400

    password_hash = hashlib.sha256(password.encode()).hexdigest()

    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                # Kullanıcı adı var mı?
                cur.execute("SELECT 1 FROM users WHERE username = %s", (username,))
                if cur.fetchone():
                    return jsonify({"error": "user_exists"}), 409

                cur.execute(
                    """
                    INSERT INTO users (
                        username, password_hash, email, device_model,
                        hashrate, threads, accepted_daily, trx_daily, last_seen
                    )
                    VALUES (%s, %s, %s, %s, 0, 0, 0, 0, NULL)
                    """,
                    (username, password_hash, email, device_model),
                )

        return jsonify({"status": "ok"}), 201

    except Exception as e:
        # Render loglarında görebilesin diye:
        print("REGISTER DB ERROR:", e, flush=True)
        return jsonify({"error": "server_error"}), 500


# ==========================================================
# LOGIN
# ==========================================================
@app.post("/login")
def login():
    data = request.json or {}
    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return jsonify({"ok": False, "error": "missing_fields"}), 400

    password_hash = hashlib.sha256(password.encode()).hexdigest()

    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT password_hash FROM users WHERE username = %s",
                    (username,),
                )
                row = cur.fetchone()
                if not row:
                    return jsonify({"ok": False}), 200

                if row["password_hash"] != password_hash:
                    return jsonify({"ok": False}), 200

                # login başarılı → last_seen güncelle
                cur.execute(
                    "UPDATE users SET last_seen = NOW() WHERE username = %s",
                    (username,),
                )

        return jsonify({"ok": True}), 200

    except Exception as e:
        print("LOGIN DB ERROR:", e, flush=True)
        return jsonify({"ok": False, "error": "server_error"}), 500


# ==========================================================
# GET USERS (JSON – Admin API)
# ==========================================================
@app.get("/get_users")
def get_users():
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        username,
                        email,
                        device_model,
                        password_hash,
                        hashrate,
                        threads,
                        accepted_daily,
                        trx_daily,
                        last_seen
                    FROM users
                    ORDER BY id ASC
                    """
                )
                rows = cur.fetchall()

        now = datetime.now(timezone.utc)
        safe = []

        for u in rows:
            last_seen = u["last_seen"]
            if last_seen:
                diff = (now - last_seen).total_seconds()
                online = diff < ONLINE_THRESHOLD
                last_seen_ts = last_seen.timestamp()
            else:
                online = False
                last_seen_ts = 0

            safe.append(
                {
                    "username": u["username"],
                    "email": u["email"],
                    "device_model": u["device_model"],
                    "password_hash": u["password_hash"],
                    "hashrate": float(u["hashrate"] or 0.0),
                    "threads": int(u["threads"] or 0),
                    "accepted_daily": int(u["accepted_daily"] or 0),
                    "trx_daily": float(u["trx_daily"] or 0.0),
                    "online": online,
                    "last_seen": last_seen_ts,
                }
            )

        return jsonify(safe)

    except Exception as e:
        print("GET_USERS DB ERROR:", e, flush=True)
        return jsonify([]), 500


# ==========================================================
# UPDATE STATS
# ==========================================================
@app.post("/update_stats")
def update_stats():
    """
    İstemci (miner) buraya:
      - username
      - hashrate
      - threads
      - accepted_daily
      - trx_daily
    gönderir.
    """
    data = request.json or {}

    username = data.get("username")
    hashrate = data.get("hashrate")
    threads = data.get("threads")
    accepted_daily = data.get("accepted_daily")
    trx_daily = data.get("trx_daily")

    if not username:
        return jsonify({"error": "username missing"}), 400

    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE users
                    SET
                        hashrate = COALESCE(%s, hashrate),
                        threads = COALESCE(%s, threads),
                        accepted_daily = COALESCE(%s, accepted_daily),
                        trx_daily = COALESCE(%s, trx_daily),
                        last_seen = NOW()
                    WHERE username = %s
                    RETURNING id
                    """,
                    (hashrate, threads, accepted_daily, trx_daily, username),
                )
                row = cur.fetchone()

        if not row:
            return jsonify({"error": "user_not_found"}), 404

        return jsonify({"status": "ok"})

    except Exception as e:
        print("UPDATE_STATS DB ERROR:", e, flush=True)
        return jsonify({"error": "server_error"}), 500


# ==========================================================
# HTML ADMIN PANEL
# ==========================================================
@app.get("/admin")
def admin_panel():
    """
    /admin → HTML tablo halinde kullanıcı listesi (Supabase'ten)
    """
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        username,
                        email,
                        device_model,
                        password_hash,
                        hashrate,
                        threads,
                        accepted_daily,
                        trx_daily,
                        last_seen
                    FROM users
                    ORDER BY id ASC
                    """
                )
                rows = cur.fetchall()
    except Exception as e:
        print("ADMIN DB ERROR:", e, flush=True)
        return "<h1>DB error</h1>", 500

    now = datetime.now(timezone.utc)

    rows_html = ""
    for u in rows:
        last_seen = u["last_seen"]
        if last_seen:
            diff = int((now - last_seen).total_seconds())
            if diff < 60:
                last_seen_str = f"{diff} sn önce"
            elif diff < 3600:
                last_seen_str = f"{diff // 60} dk önce"
            else:
                last_seen_str = f"{diff // 3600} saat önce"
            online = diff < ONLINE_THRESHOLD
        else:
            last_seen_str = "bilinmiyor"
            online = False

        online_text = "ONLINE" if online else "OFFLINE"
        online_color = "#00cc44" if online else "#cc0033"

        rows_html += f"""
        <tr>
            <td>{u["username"]}</td>
            <td>{u["email"]}</td>
            <td>{u["device_model"] or ""}</td>
            <td><code>{u["password_hash"]}</code></td>
            <td>{float(u["hashrate"] or 0.0)}</td>
            <td>{int(u["threads"] or 0)}</td>
            <td>{int(u["accepted_daily"] or 0)}</td>
            <td>{float(u["trx_daily"] or 0.0)}</td>
            <td style="color:{online_color}; font-weight:bold;">{online_text}</td>
            <td>{last_seen_str}</td>
        </tr>
        """

    html = f"""
    <!doctype html>
    <html lang="tr">
    <head>
        <meta charset="utf-8">
        <title>TRX Goblin Admin Panel</title>
        <style>
            body {{
                background-color: #111;
                color: #eee;
                font-family: Arial, sans-serif;
            }}
            h1 {{
                color: #00ff88;
            }}
            table {{
                border-collapse: collapse;
                width: 100%;
                margin-top: 10px;
            }}
            th, td {{
                border: 1px solid #333;
                padding: 6px 8px;
                font-size: 13px;
            }}
            th {{
                background-color: #222;
            }}
            tr:nth-child(even) {{
                background-color: #181818;
            }}
            tr:nth-child(odd) {{
                background-color: #141414;
            }}
            code {{
                font-size: 11px;
            }}
        </style>
    </head>
    <body>
        <h1>TRX Goblin Admin Panel</h1>
        <table>
            <thead>
                <tr>
                    <th>Kullanıcı Adı</th>
                    <th>E-posta</th>
                    <th>Cihaz Modeli</th>
                    <th>Parola SHA-256</th>
                    <th>Hashrate (H/s)</th>
                    <th>Thread</th>
                    <th>Günlük Accepted</th>
                    <th>Günlük TRX</th>
                    <th>Durum</th>
                    <th>Son Görülme</th>
                </tr>
            </thead>
            <tbody>
                {rows_html}
            </tbody>
        </table>
    </body>
    </html>
    """

    return html


if __name__ == "__main__":
    # Lokal test için:
    app.run(host="0.0.0.0", port=5000)
