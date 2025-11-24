from flask import Flask, request, jsonify
import json
import os

app = Flask(__name__)

DB = os.path.join(os.path.dirname(__file__), "users.json")


# --- Kullanıcıları Yükle ---
def load_users():
    if not os.path.exists(DB):
        return []

    with open(DB, "r") as f:
        try:
            return json.load(f)
        except:
            return []


# --- Kullanıcıları Kaydet ---
def save_users(users):
    with open(DB, "w") as f:
        json.dump(users, f, indent=4)


# --- Kullanıcı Listeleme (ADMIN PANEL) ---
@app.get("/get_users")
def get_users():
    users = load_users()
    return jsonify(users)


# --- İstatistik Güncelleme ---
@app.post("/update_stats")
def update_stats():
    data = request.json

    username = data.get("username")
    hashrate = data.get("hashrate")
    threads = data.get("threads")

    if not username:
        return jsonify({"error": "username missing"}), 400

    users = load_users()
    found = False

    for u in users:
        if u["username"] == username:
            u["hashrate"] = hashrate
            u["threads"] = threads
            found = True

    if not found:
        users.append({
            "username": username,
            "hashrate": hashrate,
            "threads": threads
        })

    save_users(users)

    return jsonify({"status": "ok"})


# --- TEST ---
@app.get("/")
def home():
    return "Goblin Server Çalışıyor"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
