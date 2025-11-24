from flask import Flask, request, jsonify

app = Flask(__name__)

# Basit veritabanı (Render üzerinde JSON saklanırsa kalıcı olmaz!)
# Test amaçlı RAM içinde durur. İstersen JSON dosyasına kaydedebiliriz.
users = {}  # { "username": {"password": "...", "wallet": "..."} }
stats = {}  # { "username": {"hashrate": 0, "threads": 0} }


# ----------------------------------------------------------
# Sunucu çalışıyor mu testi
# ----------------------------------------------------------
@app.get("/")
def home():
    return "TRX Goblin Server Çalışıyor!"


# ----------------------------------------------------------
# KAYIT OL
# POST /register
# JSON: { "username": "abc", "password": "123456" }
# ----------------------------------------------------------
@app.post("/register")
def register():
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")
    wallet = data.get("wallet", "-")

    if not username or not password:
        return jsonify({"error": "Eksik bilgi"}), 400

    if username in users:
        return jsonify({"error": "Bu kullanıcı zaten var"}), 409

    users[username] = {
        "password": password,
        "wallet": wallet
    }

    return jsonify({"status": "ok"}), 200


# ----------------------------------------------------------
# GİRİŞ
# POST /login
# JSON: { "username": "abc", "password": "123456" }
# ----------------------------------------------------------
@app.post("/login")
def login():
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")

    if username not in users:
        return jsonify({"error": "Kullanıcı bulunamadı"}), 404

    if users[username]["password"] != password:
        return jsonify({"error": "Şifre yanlış"}), 403

    return jsonify({"status": "ok"}), 200


# ----------------------------------------------------------
# İSTATİSTİK GÖNDER
# POST /update_stats
# JSON: {"username": "...", "hashrate": 100, "threads": 4}
# ----------------------------------------------------------
@app.post("/update_stats")
def update_stats():
    data = request.get_json()
    username = data.get("username")
    h = data.get("hashrate")
    t = data.get("threads")

    if username not in users:
        return jsonify({"error": "kullanıcı bulunamadı"}), 404

    stats[username] = {
        "hashrate": h,
        "threads": t
    }

    return jsonify({"status": "ok"}), 200


# ----------------------------------------------------------
# TÜM KULLANICILARI AL
# GET /get_users
# ----------------------------------------------------------
@app.get("/get_users")
def get_users():
    return jsonify(users), 200


# ----------------------------------------------------------
# Render için gunicorn çalıştırır
# ----------------------------------------------------------
if __name__ == "server":
    app.run(host="0.0.0.0", port=10000)
