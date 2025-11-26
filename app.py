from flask import Flask, request, jsonify
import os
import time
import hashlib
import traceback

import psycopg2
import psycopg2.extras

app = Flask(__name__)

# -------------------------------------------------
# Supabase Postgres bağlantısı
# Render'da Environment -> DATABASE_URL
# ÖRNEK (transaction pooler):
# postgresql://postgres.rqbuhsoiqhapbxrugdha:PAROLA@aws-1-eu-central-2.pooler.supabase.com:6543/postgres
# -------------------------------------------------
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL environment değişkeni yok! Render panelinden ekle.")

ONLINE_THRESHOLD = 60 * 2  # 2 dakika içinde ping geldiyse ONLINE say


def get_conn():
    """Her istekte yeni bir Postgres bağlantısı aç."""
    return psycopg2.connect(DATABASE_URL)


def init_db():
    """users tablosu yoksa oluştur (varsa dokunmaz)."""
    try:
        conn = get_conn()
    except Exception as e:
        print("[init_db] DB bağlantı hatası:", e)
        return

    cur = conn.cursor()
    try:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id BIGSERIAL PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                email TEXT NOT NULL,
                device_model TEXT,
                hashrate DOUBLE PRECISION DEFAULT 0,
                threads INTEGER DEFAULT 0,
                accepted_daily INTEGER DEFAULT 0,
                trx_daily DOUBLE PRECISION DEFAULT 0,
                last_seen TIMESTAMPTZ
            );
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_users_username
            ON users (username);
            """
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        print("[init_db] tablo oluşturma hatası:", e)
    finally:
        cur.close()
        conn.close()


# Uygulama ayağa kalkarken tabloyu garantiye al
init_db()

# -------------------------------------------------
# HEALTH CHECK
# -------------------------------------------------
@app.get("/health_db")
def health_db():
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT NOW();")
        now = cur.fetchone()[0]
        cur.close()
        conn.close()
        return jsonify({"ok": True, "now": str(now)})
    except Exception as e:
        print("[health_db] hata:", e)
        return jsonify({"ok": False, "error": str(e)}), 500


# -------------------------------------------------
# KÖK
# -------------------------------------------------
@app.get("/")
def home():
    return "TRX Goblin Supabase Server Çalışıyor!"


# -------------------------------------------------
# REGISTER (kayıt ol)
# Body: { username, password, email, device_model(optional) }
# -------------------------------------------------
@app.post("/register")
def register():
    data = request.get_json(silent=True) or {}

    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    email = (data.get("email") or "").strip()
    device_model = (data.get("device_model") or "").strip()

    if not username or not password or not email:
        return jsonify({"ok": False, "error": "missing_fields"}), 400

    # Şifreyi SHA-256 ile hashle
    pw_hash = hashlib.sha256(password.encode("utf-8")).hexdigest()

    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    try:
        # Kullanıcı var mı?
        cur.execute("SELECT id FROM users WHERE username = %s", (username,))
        row = cur.fetchone()
        if row:
            return jsonify({"ok": False, "error": "user_exists"}), 409

        # Yeni kullanıcı ekle
        cur.execute(
            """
            INSERT INTO users (username, password_hash, email, device_model, last_seen)
            VALUES (%s, %s, %s, %s, NOW())
            RETURNING id;
            """,
            (username, pw_hash, email, device_model),
        )
        conn.commit()
        return jsonify({"ok": True}), 201
    except Exception as e:
        conn.rollback()
        print("[register] hata:", e)
        return jsonify({"ok": False, "error": "server_error", "detail": str(e)}), 500
    finally:
        cur.close()
        conn.close()


# -------------------------------------------------
# LOGIN
# Body: { username, password }
# Cevap: { ok: True/False }
# -------------------------------------------------
@app.post("/login")
def login():
    data = request.get_json(silent=True) or {}

    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    if not username or not password:
        return jsonify({"ok": False, "error": "missing_fields"}), 400

    pw_hash = hashlib.sha256(password.encode("utf-8")).hexdigest()

    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    try:
        cur.execute(
            "SELECT id FROM users WHERE username = %s AND password_hash = %s",
            (username, pw_hash),
        )
        row = cur.fetchone()

        if not row:
            return jsonify({"ok": False}), 200

        # login başarılı → last_seen güncelle
        cur.execute("UPDATE users SET last_seen = NOW() WHERE id = %s", (row["id"],))
        conn.commit()
        return jsonify({"ok": True})
    except Exception as e:
        conn.rollback()
        print("[login] hata:", e)
        return jsonify({"ok": False, "error": "server_error", "detail": str(e)}), 500
    finally:
        cur.close()
        conn.close()


# -------------------------------------------------
# UPDATE_STATS
# Body: { username, hashrate, threads, accepted_daily, trx_daily }
# -------------------------------------------------
@app.post("/update_stats")
def update_stats():
    conn = None
    cur = None

    try:
        data = request.get_json(silent=True)
        print("[update_stats] RAW PAYLOAD:", repr(data))

        # JSON dict değilse (string, liste vs) 400 dön
        if not isinstance(data, dict):
            return jsonify({
                "error": "invalid_payload",
                "detail": "JSON dict bekleniyordu"
            }), 400

        username = str(data.get("username") or "").strip()
        if not username:
            return jsonify({"error": "username_missing"}), 400

        # Güvenli parse helper'ları
        def safe_float(v):
            if v is None:
                return None
            try:
                return float(v)
            except (ValueError, TypeError):
                return None

        def safe_int(v):
            if v is None:
                return None
            try:
                return int(v)
            except (ValueError, TypeError):
                return None

        hashrate = safe_float(data.get("hashrate"))
        threads = safe_int(data.get("threads"))
        accepted_daily = safe_int(data.get("accepted_daily"))
        trx_daily = safe_float(data.get("trx_daily"))

        conn = get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # kullanıcı var mı?
        cur.execute("SELECT id FROM users WHERE username = %s", (username,))
        row = cur.fetchone()
        if not row:
            return jsonify({"error": "user_not_found"}), 404

        fields = []
        params = []

        if hashrate is not None:
            fields.append("hashrate = %s")
            params.append(hashrate)

        if threads is not None:
            fields.append("threads = %s")
            params.append(threads)

        if accepted_daily is not None:
            fields.append("accepted_daily = %s")
            params.append(accepted_daily)

        if trx_daily is not None:
            fields.append("trx_daily = %s")
            params.append(trx_daily)

        # last_seen her güncellemede yenilensin
        fields.append("last_seen = NOW()")
        params.append(row["id"])

        sql = "UPDATE users SET " + ", ".join(fields) + " WHERE id = %s"
        cur.execute(sql, params)
        conn.commit()

        return jsonify({"status": "ok"})

    except Exception:
        tb = traceback.format_exc()
        print("[update_stats] FATAL hata:", tb)
        return jsonify({"error": "server_error", "detail": tb}), 500

    finally:
        try:
            if cur is not None:
                cur.close()
        except Exception:
            pass
        try:
            if conn is not None:
                conn.close()
        except Exception:
            pass


# -------------------------------------------------
# GET_USERS (JSON) – Admin API
# -------------------------------------------------
@app.get("/get_users")
def get_users():
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    try:
        cur.execute(
            """
            SELECT id, username, email, device_model, password_hash,
                   hashrate, threads, accepted_daily, trx_daily, last_seen
            FROM users
            ORDER BY id ASC;
            """
        )
        rows = cur.fetchall()
    finally:
        cur.close()
        conn.close()

    now_ts = time.time()
    result = []

    for u in rows:
        last_seen_dt = u.get("last_seen")
        if last_seen_dt:
            last_seen_ts = last_seen_dt.timestamp()
            diff = now_ts - last_seen_ts
            online = diff < ONLINE_THRESHOLD
        else:
            last_seen_ts = None
            online = False

        result.append(
            {
                "username": u.get("username"),
                "email": u.get("email"),
                "device_model": u.get("device_model"),
                "password_hash": u.get("password_hash"),
                "hashrate": float(u.get("hashrate") or 0.0),
                "threads": int(u.get("threads") or 0),
                "accepted_daily": int(u.get("accepted_daily") or 0),
                "trx_daily": float(u.get("trx_daily") or 0.0),
                "online": online,
                "last_seen": last_seen_ts,
            }
        )

    return jsonify(result)


# -------------------------------------------------
# HTML ADMIN PANEL (/admin)
# -------------------------------------------------
@app.get("/admin")
def admin_panel():
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    try:
        cur.execute(
            """
            SELECT id, username, email, device_model, password_hash,
                   hashrate, threads, accepted_daily, trx_daily, last_seen
            FROM users
            ORDER BY id ASC;
            """
        )
        rows = cur.fetchall()
    finally:
        cur.close()
        conn.close()

    now_ts = time.time()
    rows_html = ""

    for u in rows:
        last_seen_dt = u.get("last_seen")
        if last_seen_dt:
            last_seen_ts = last_seen_dt.timestamp()
            diff = int(now_ts - last_seen_ts)
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
            <td>{u.get("username","")}</td>
            <td>{u.get("email","")}</td>
            <td>{u.get("device_model","")}</td>
            <td><code>{u.get("password_hash","")}</code></td>
            <td>{u.get("hashrate",0.0)}</td>
            <td>{u.get("threads",0)}</td>
            <td>{u.get("accepted_daily",0)}</td>
            <td>{u.get("trx_daily",0.0)}</td>
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
    app.run(host="0.0.0.0", port=5000, debug=True)
